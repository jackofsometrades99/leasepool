from __future__ import annotations

import asyncio
import logging
import math
import multiprocessing
import threading
import time
import uuid
from collections import deque
from collections.abc import Callable
from concurrent.futures import Executor, Future
from dataclasses import dataclass
from typing import Any

from ._process_logging import (
    ProcessLoggingConfig,
    build_queue_listener,
    coerce_log_level,
    process_worker_initializer,
)
from .backends import ExecutorBackend, build_executor, normalize_backend
from .exceptions import (
    LeaseExpiredError,
    LeasePoolNotStartedError,
    LeaseUnavailableError,
)
from .types import SizeProvider


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _LeaseRecord:
    lease_id: str
    executor: Executor
    owner: str | None
    leased_at: float
    lease_seconds: float
    grace_seconds: float

    @property
    def soft_expires_at(self) -> float:
        return self.leased_at + self.lease_seconds

    @property
    def hard_expires_at(self) -> float:
        return self.soft_expires_at + self.grace_seconds


class _LeasedExecutorProxy(Executor):
    """Proxy handed to callers instead of the raw executor.

    The raw executor remains private inside LeasedExecutorManager. Once the lease
    is released or revoked, new submissions through this proxy fail.
    """

    def __init__(self, manager: LeasedExecutorManager, lease_id: str):
        """Init module-level initializer for ProcessPoolExecutor workers.

        Args:
            manager (LeasedExecutorManager): _description_
            lease_id (str): _description_
        """
        self._manager = manager
        self._lease_id = lease_id

    def submit(self, fn: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Future:
        return self._manager._submit_for_lease(self._lease_id, fn, *args, **kwargs)

    def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
        raise RuntimeError(
            "Do not shut down a leased executor directly. "
            "Return the lease with `await lease.release()`."
        )


class ExecutorLease:
    """Lease object returned by LeasedExecutorManager.acquire()."""

    def __init__(
        self,
        *,
        manager: LeasedExecutorManager,
        lease_id: str,
        owner: str | None,
        lease_seconds: float,
        grace_seconds: float,
        leased_at: float,
    ):
        self._manager = manager
        self.lease_id = lease_id
        self.owner = owner
        self.lease_seconds = lease_seconds
        self.grace_seconds = grace_seconds
        self.leased_at = leased_at
        self.executor: Executor = _LeasedExecutorProxy(manager, lease_id)
        self._released = False

    @property
    def soft_expires_at(self) -> float:
        return self.leased_at + self.lease_seconds

    @property
    def hard_expires_at(self) -> float:
        return self.soft_expires_at + self.grace_seconds

    async def run(self, fn: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Any:
        """Run a synchronous callable in this leased executor."""
        loop = asyncio.get_running_loop()

        if kwargs:
            import functools

            call = functools.partial(fn, *args, **kwargs)
            return await loop.run_in_executor(self.executor, call)

        return await loop.run_in_executor(self.executor, fn, *args)

    async def release(self) -> None:
        if self._released:
            return

        self._released = True
        await self._manager.release(self.lease_id)

    async def __aenter__(self) -> ExecutorLease:
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        await self.release()


class LeasedExecutorManager:
    """Bounded async manager for leased Executor instances.

    The manager supports ThreadPoolExecutor and ProcessPoolExecutor on Python 3.11.
    Python 3.14+ can add InterpreterPoolExecutor through the same backend hook.

    Sizing rule:
        desired executors =
            max(min_pools, ceil(size_provider() / units_per_pool))

        desired executors is capped at max_pools.
    """

    def __init__(
        self,
        *,
        backend: ExecutorBackend | str = ExecutorBackend.THREAD,
        max_pools: int,
        min_pools: int = 1,
        units_per_pool: int = 10,
        size_provider: SizeProvider | None = None,
        check_interval: float = 120.0,
        default_lease_seconds: float = 300.0,
        lease_grace_seconds: float = 15.0,
        workers_per_pool: int = 4,
        name_prefix: str = "leasepool",
        logger: logging.Logger | None = None,
        process_logging: ProcessLoggingConfig | None = None,
        forward_process_logs: bool = False,
        process_log_level: int | str = logging.INFO,
        process_log_target_logger: logging.Logger | None = None,
        clear_process_log_handlers: bool = True,
        **executor_kwargs: Any,
    ):
        if max_pools <= 0:
            raise ValueError("max_pools must be > 0")
        if min_pools <= 0:
            raise ValueError("min_pools must be > 0")
        if units_per_pool <= 0:
            raise ValueError("units_per_pool must be > 0")
        if workers_per_pool <= 0:
            raise ValueError("workers_per_pool must be > 0")
        if min_pools > max_pools:
            raise ValueError("min_pools cannot be greater than max_pools")

        self._backend = normalize_backend(backend)
        self._logger = logger or logging.getLogger(__name__)

        if process_logging is not None and (
            forward_process_logs
            or process_log_level != logging.INFO
            or process_log_target_logger is not None
            or clear_process_log_handlers is not True
        ):
            raise ValueError(
                "Pass either process_logging or the forward_process_logs/process_log_* "
                "arguments, not both."
            )

        if process_logging is None:
            process_logging = ProcessLoggingConfig(
                enabled=forward_process_logs,
                level=process_log_level,
                target_logger=process_log_target_logger,
                clear_child_handlers=clear_process_log_handlers,
            )

        if process_logging.enabled and self._backend is not ExecutorBackend.PROCESS:
            raise ValueError(
                "process log forwarding is only supported for process backend"
            )

        self._process_logging = process_logging
        self._process_log_level = coerce_log_level(process_logging.level)
        self._process_log_queue: Any | None = None
        self._process_log_listener: Any | None = None
        self._process_log_mp_context: multiprocessing.context.BaseContext | None = None

        self._max_pools = int(max_pools)
        self._min_pools = int(min_pools)
        self._units_per_pool = int(units_per_pool)
        self._size_provider = size_provider
        self._check_interval = float(check_interval)
        self._default_lease_seconds = float(default_lease_seconds)
        self._lease_grace_seconds = float(lease_grace_seconds)
        self._workers_per_pool = int(workers_per_pool)
        self._name_prefix = name_prefix
        self._executor_kwargs = executor_kwargs

        self._available: deque[Executor] = deque()
        self._leased: dict[str, _LeaseRecord] = {}

        # Synchronous lock because Executor.submit() is synchronous.
        self._lock = threading.RLock()

        self._availability_event: asyncio.Event | None = None
        self._scale_change_event: asyncio.Event | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._checker_task: asyncio.Task[None] | None = None

        self._started = False
        self._stopping = False
        self._executor_seq = 0

    @property
    def backend(self) -> ExecutorBackend:
        return self._backend

    async def start(self) -> None:
        if self._started:
            return

        self._loop = asyncio.get_running_loop()
        self._availability_event = asyncio.Event()
        self._scale_change_event = asyncio.Event()

        self._start_process_logging_if_needed()

        try:
            with self._lock:
                self._stopping = False
                self._ensure_minimum_locked()

            self._checker_task = asyncio.create_task(
                self._checker_loop(),
                name="leasepool-checker",
            )
            self._started = True
        except Exception:
            executors: list[Executor] = []
            with self._lock:
                executors.extend(self._available)
                executors.extend(record.executor for record in self._leased.values())
                self._available.clear()
                self._leased.clear()

            for executor in executors:
                self._shutdown_executor(executor)

            self._stop_process_logging_if_needed()
            raise

        self._logger.info(
            "LeasedExecutorManager started backend=%s total=%s available=%s "
            "leased=%s target=%s",
            self._backend.value,
            self.total_count,
            self.available_count,
            self.leased_count,
            self.desired_executor_count(),
        )

    async def stop(self) -> None:
        self._stopping = True

        if self._checker_task:
            self._checker_task.cancel()
            try:
                await self._checker_task
            except asyncio.CancelledError:
                pass
            finally:
                self._checker_task = None

        executors: list[Executor] = []
        with self._lock:
            executors.extend(self._available)
            executors.extend(record.executor for record in self._leased.values())
            self._available.clear()
            self._leased.clear()
            self._started = False

        for executor in executors:
            self._shutdown_executor(executor)

        self._stop_process_logging_if_needed()
        self._wake_waiters()
        self._logger.info("LeasedExecutorManager stopped")

    async def acquire(
        self,
        *,
        lease_seconds: float | None = None,
        owner: str | None = None,
        wait: bool = True,
        timeout: float | None = None,
    ) -> ExecutorLease:
        """Acquire an executor lease.

        Args:
            lease_seconds (float | None, optional): The duration of the lease in seconds. Defaults to None.
            owner (str | None, optional): The owner of the lease. Defaults to None.
            wait (bool, optional): Whether to wait for an available executor. Defaults to True.
            timeout (float | None, optional): The maximum time to wait for an available executor in seconds. Defaults to None.

        Raises:
            LeasePoolNotStartedError: If the lease pool is not started.
            ValueError: If the lease_seconds is not positive.
            LeaseUnavailableError: If no executor is available and wait is False.
            TimeoutError: If the timeout is reached while waiting for an executor.
            LeasePoolNotStartedError: If the lease pool is not started.
            TimeoutError: If the timeout is reached while waiting for an executor.

        Returns:
            ExecutorLease: The acquired executor lease.
        """
        if not self._started:
            raise LeasePoolNotStartedError("LeasedExecutorManager is not started")

        if lease_seconds is None:
            lease_seconds = self._default_lease_seconds

        lease_seconds = float(lease_seconds)
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be > 0")

        started_at = time.monotonic()

        while True:
            with self._lock:
                self._revoke_expired_leases_locked()

                executor = self._take_or_create_available_locked()
                if executor is not None:
                    lease_id = uuid.uuid4().hex
                    leased_at = time.monotonic()

                    self._leased[lease_id] = _LeaseRecord(
                        lease_id=lease_id,
                        executor=executor,
                        owner=owner,
                        leased_at=leased_at,
                        lease_seconds=lease_seconds,
                        grace_seconds=self._lease_grace_seconds,
                    )

                    self._logger.info(
                        "Leased executor backend=%s lease_id=%s owner=%s "
                        "seconds=%s grace=%s",
                        self._backend.value,
                        lease_id,
                        owner,
                        lease_seconds,
                        self._lease_grace_seconds,
                    )

                    return ExecutorLease(
                        manager=self,
                        lease_id=lease_id,
                        owner=owner,
                        lease_seconds=lease_seconds,
                        grace_seconds=self._lease_grace_seconds,
                        leased_at=leased_at,
                    )

            if not wait:
                raise LeaseUnavailableError(
                    f"No executor available; max_pools={self._max_pools} reached"
                )

            remaining: float | None
            if timeout is not None:
                elapsed = time.monotonic() - started_at
                remaining = timeout - elapsed
                if remaining <= 0:
                    raise TimeoutError(
                        f"Timed out waiting for an executor after {timeout}s"
                    )
            else:
                remaining = None

            if self._availability_event is None:
                raise LeasePoolNotStartedError("LeasedExecutorManager is not started")

            try:
                await asyncio.wait_for(
                    self._availability_event.wait(),
                    timeout=remaining,
                )
            except asyncio.TimeoutError as exc:
                raise TimeoutError(
                    f"Timed out waiting for an executor after {timeout}s"
                ) from exc
            finally:
                self._availability_event.clear()

    async def release(self, lease_id: str) -> None:
        """Release an executor lease.

        Args:
            lease_id (str): The ID of the lease to release.
        """
        executor: Executor | None = None
        should_keep = False

        with self._lock:
            record = self._leased.pop(lease_id, None)
            if record is None:
                return

            executor = record.executor

            if self._stopping:
                should_keep = False
            else:
                target = self._desired_executor_count_locked()
                projected_total = self._current_count_locked() + 1
                should_keep = projected_total <= target

                if should_keep:
                    self._available.append(executor)

            self._logger.info(
                "Released executor lease_id=%s owner=%s kept=%s",
                lease_id,
                record.owner,
                should_keep,
            )

            self._ensure_minimum_locked()

        if executor is not None and not should_keep:
            self._shutdown_executor(executor)

        self._wake_waiters()

    def notify_scale_changed(self) -> None:
        """Inform the checker that the size signal changed."""
        self._wake_scale_checker()

    def desired_executor_count(self) -> int:
        with self._lock:
            return self._desired_executor_count_locked()

    @property
    def available_count(self) -> int:
        with self._lock:
            return len(self._available)

    @property
    def leased_count(self) -> int:
        with self._lock:
            return len(self._leased)

    @property
    def total_count(self) -> int:
        with self._lock:
            return self._current_count_locked()

    def stats(self) -> dict[str, Any]:
        """Get statistics about the executor manager.

        Returns:
            dict[str, Any]: A dictionary containing statistics about the executor manager.
        """
        with self._lock:
            now = time.monotonic()

            return {
                "backend": self._backend.value,
                "desired": self._desired_executor_count_locked(),
                "max_pools": self._max_pools,
                "min_pools": self._min_pools,
                "available": len(self._available),
                "leased": len(self._leased),
                "total": self._current_count_locked(),
                "workers_per_pool": self._workers_per_pool,
                "leases": [
                    {
                        "lease_id": record.lease_id,
                        "owner": record.owner,
                        "seconds_until_soft_expiry": max(
                            0.0,
                            record.soft_expires_at - now,
                        ),
                        "seconds_until_hard_expiry": max(
                            0.0,
                            record.hard_expires_at - now,
                        ),
                    }
                    for record in self._leased.values()
                ],
            }

    async def _checker_loop(self) -> None:
        """Checker loop for managing executor leases."""
        try:
            while True:
                with self._lock:
                    self._revoke_expired_leases_locked()
                    self._ensure_minimum_locked()
                    self._shrink_idle_if_above_target_locked()
                    next_expiry_delay = self._seconds_until_next_hard_expiry_locked()

                self._wake_waiters()

                wait_seconds = self._check_interval
                if next_expiry_delay is not None:
                    wait_seconds = min(wait_seconds, max(0.0, next_expiry_delay))

                assert self._scale_change_event is not None

                try:
                    await asyncio.wait_for(
                        self._scale_change_event.wait(),
                        timeout=wait_seconds,
                    )
                except asyncio.TimeoutError:
                    pass
                finally:
                    self._scale_change_event.clear()

        except asyncio.CancelledError:
            raise
        except Exception:
            self._logger.exception("LeasedExecutorManager checker crashed")

    def _submit_for_lease(
        self,
        lease_id: str,
        fn: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Future:
        """Submit a task for execution under a lease.

        Args:
            lease_id (str): _description_
            fn (Callable[..., Any]): _description_

        Raises:
            LeaseExpiredError: _description_
            LeaseExpiredError: _description_

        Returns:
            Future: _description_
        """
        executor_to_shutdown: Executor | None = None

        with self._lock:
            record = self._leased.get(lease_id)
            if record is None:
                raise LeaseExpiredError("Executor lease is no longer active")

            now = time.monotonic()

            if now >= record.hard_expires_at:
                self._leased.pop(lease_id, None)
                executor_to_shutdown = record.executor
                self._ensure_minimum_locked()
            else:
                return record.executor.submit(fn, *args, **kwargs)

        if executor_to_shutdown is not None:
            self._shutdown_executor(executor_to_shutdown)
            self._wake_waiters()

        raise LeaseExpiredError("Executor lease expired and was revoked")

    def _take_or_create_available_locked(self) -> Executor | None:
        """Take an available executor or create a new one if possible.

        Returns:
            Executor | None: An available executor or None if the maximum number of pools is reached.
        """
        if self._available:
            return self._available.popleft()

        if self._current_count_locked() < self._max_pools:
            return self._create_executor_locked()

        return None

    def _ensure_minimum_locked(self) -> None:
        """Ensure the minimum number of executors are available."""
        target = self._desired_executor_count_locked()

        while self._current_count_locked() < target:
            self._available.append(self._create_executor_locked())

    def _shrink_idle_if_above_target_locked(self) -> None:
        """Shrink idle executors if the current count is above the target."""
        target = self._desired_executor_count_locked()

        while self._available and self._current_count_locked() > target:
            executor = self._available.pop()
            self._shutdown_executor(executor)

    def _revoke_expired_leases_locked(self) -> None:
        """Revoke expired executor leases."""
        now = time.monotonic()

        expired_ids = [
            lease_id
            for lease_id, record in self._leased.items()
            if now >= record.hard_expires_at
        ]

        for lease_id in expired_ids:
            record = self._leased.pop(lease_id)

            self._logger.warning(
                "Revoking expired executor lease_id=%s owner=%s "
                "lease_seconds=%s grace=%s",
                lease_id,
                record.owner,
                record.lease_seconds,
                record.grace_seconds,
            )

            self._shutdown_executor(record.executor)

        if expired_ids:
            self._ensure_minimum_locked()

    def _seconds_until_next_hard_expiry_locked(self) -> float | None:
        """Calculate the seconds until the next hard expiry of any leased executor.

        Returns:
            float | None: The number of seconds until the next hard expiry, or None if there are no leased executors.
        """
        if not self._leased:
            return None

        now = time.monotonic()
        return min(record.hard_expires_at - now for record in self._leased.values())

    def _desired_executor_count_locked(self) -> int:
        """Calculate the desired number of executors based on the current unit count.

        Returns:
            int: The desired number of executors.
        """
        unit_count = self._unit_count_locked()
        unit_based = math.ceil(unit_count / self._units_per_pool)

        desired = max(self._min_pools, unit_based)
        return min(self._max_pools, desired)

    def _unit_count_locked(self) -> int:
        """Get the current unit count from the size provider.

        Returns:
            int: The current unit count.
        """
        if self._size_provider is None:
            return 0
        try:
            return max(0, int(self._size_provider()))
        except Exception:
            self._logger.debug("Could not read size_provider", exc_info=True)
            return 0

    def _current_count_locked(self) -> int:
        """Get the current count of executors.

        Returns:
            int: The current count of executors.
        """
        return len(self._available) + len(self._leased)

    def _start_process_logging_if_needed(self) -> None:
        """Start the parent-side process logging bridge, if configured."""
        if self._backend is not ExecutorBackend.PROCESS:
            return
        if not self._process_logging.enabled:
            return
        if self._process_log_listener is not None:
            return

        mp_context = self._executor_kwargs.get("mp_context")
        if mp_context is None:
            # ProcessPoolExecutor uses spawn automatically when
            # max_tasks_per_child is supplied. I will use the same context for the
            # logging queue to avoid cross-context SemLock errors.
            if self._executor_kwargs.get("max_tasks_per_child") is not None:
                mp_context = multiprocessing.get_context("spawn")
            else:
                mp_context = multiprocessing.get_context()

        self._process_log_mp_context = mp_context
        self._process_log_queue = mp_context.Queue(-1)

        target_logger = self._process_logging.target_logger or self._logger
        self._process_log_listener = build_queue_listener(
            log_queue=self._process_log_queue,
            target_logger=target_logger,
        )
        self._process_log_listener.start()

        self._logger.debug(
            "Process log forwarding started target_logger=%s level=%s",
            target_logger.name,
            self._process_log_level,
        )

    def _stop_process_logging_if_needed(self) -> None:
        """Stop the parent-side process logging bridge, if running."""
        listener = self._process_log_listener
        if listener is not None:
            try:
                listener.stop()
            finally:
                self._process_log_listener = None

        queue = self._process_log_queue
        if queue is not None:
            try:
                queue.close()
            except Exception:
                self._logger.debug("Could not close process log queue", exc_info=True)
            try:
                queue.join_thread()
            except Exception:
                self._logger.debug(
                    "Could not join process log queue thread",
                    exc_info=True,
                )
            finally:
                self._process_log_queue = None
                self._process_log_mp_context = None

    def _executor_kwargs_for_new_executor(self) -> dict[str, Any]:
        """Build executor kwargs, composing process-log initializer if needed."""
        kwargs = dict(self._executor_kwargs)

        if self._backend is not ExecutorBackend.PROCESS:
            return kwargs
        if not self._process_logging.enabled:
            return kwargs

        log_queue = self._process_log_queue
        if log_queue is None:
            raise RuntimeError("process log forwarding has not been started")

        user_initializer = kwargs.pop("initializer", None)
        user_initargs = tuple(kwargs.pop("initargs", ()))

        kwargs["initializer"] = process_worker_initializer
        kwargs["initargs"] = (
            log_queue,
            self._process_log_level,
            self._process_logging.clear_child_handlers,
            user_initializer,
            user_initargs,
        )

        if "mp_context" not in kwargs and self._process_log_mp_context is not None:
            kwargs["mp_context"] = self._process_log_mp_context

        return kwargs


    def _create_executor_locked(self) -> Executor:
        """Create a new executor instance.

        Returns:
            Executor: The newly created executor.
        """
        self._executor_seq += 1

        executor = build_executor(
            backend=self._backend,
            max_workers=self._workers_per_pool,
            name_prefix=self._name_prefix,
            executor_seq=self._executor_seq,
            executor_kwargs=self._executor_kwargs_for_new_executor(),
        )

        self._logger.info(
            "Created executor backend=%s seq=%s workers=%s",
            self._backend.value,
            self._executor_seq,
            self._workers_per_pool,
        )

        return executor

    @staticmethod
    def _shutdown_executor(executor: Executor) -> None:
        """Shutdown the given executor.

        Args:
            executor (Executor): The executor to shutdown.
        """
        executor.shutdown(wait=False, cancel_futures=True)

    def _wake_waiters(self) -> None:
        """Wake up any waiters waiting for an available executor."""
        event = self._availability_event
        loop = self._loop

        if event is None or loop is None or loop.is_closed():
            return

        loop.call_soon_threadsafe(event.set)

    def _wake_scale_checker(self) -> None:
        """Wake up the scale checker to re-evaluate the desired executor count."""
        event = self._scale_change_event
        loop = self._loop

        if event is None or loop is None or loop.is_closed():
            return

        loop.call_soon_threadsafe(event.set)
