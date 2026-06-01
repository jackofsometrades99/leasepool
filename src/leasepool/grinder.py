from __future__ import annotations

import uuid
import asyncio
import logging
import functools
from collections import deque
from dataclasses import dataclass
from collections.abc import Callable
from concurrent.futures import Future as ConcurrentFuture
from typing import Any

from .manager import LeasedExecutorManager


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _WorkItem:
    work_id: str
    fn: Callable[..., Any]
    args: tuple[Any, ...]
    kwargs: dict[str, Any]
    result_future: asyncio.Future[Any]
    submitted_at: float
    owner: str | None


class WorkGrinder:
    """Async work batcher backed by leased executors.

    Multiple async callers submit sync work. The grinder starts processing a batch
    when either:

    - the oldest pending work has waited at least max_wait_seconds, or
    - pending work count reaches batch_size_threshold.

    Once a batch is ready, it leases one executor and submits the whole batch.
    """
    def __init__(
        self,
        *,
        executor_manager: LeasedExecutorManager,
        max_wait_seconds: float = 10.0,
        batch_size_threshold: int = 20,
        lease_seconds: float = 60.0,
        owner_prefix: str = "work-grinder",
        logger: logging.Logger | None = None,
    ):
        """Initialize a WorkGrinder instance.

        Args:
            executor_manager (LeasedExecutorManager): The executor manager to lease executors from.
            max_wait_seconds (float, optional): The maximum time to wait before processing a batch. Defaults to 10.0.
            batch_size_threshold (int, optional): The number of pending work items to trigger batch processing. Defaults to 20.
            lease_seconds (float, optional): The duration to lease an executor for each batch. Defaults to 60.0.
            owner_prefix (str, optional): The prefix for the owner identifier of each batch. Defaults to "work-grinder".

        Raises:
            ValueError: If max_wait_seconds is not greater than 0.
            ValueError: If batch_size_threshold is not greater than 0.
            ValueError: If lease_seconds is not greater than 0.
        """
        if max_wait_seconds <= 0:
            raise ValueError("max_wait_seconds must be > 0")
        if batch_size_threshold <= 0:
            raise ValueError("batch_size_threshold must be > 0")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be > 0")

        self._executor_manager = executor_manager
        self._logger = logger or logging.getLogger(__name__)
        self._max_wait_seconds = float(max_wait_seconds)
        self._batch_size_threshold = int(batch_size_threshold)
        self._lease_seconds = float(lease_seconds)
        self._owner_prefix = owner_prefix

        self._pending: deque[_WorkItem] = deque()
        self._condition = asyncio.Condition()

        self._loop: asyncio.AbstractEventLoop | None = None
        self._task: asyncio.Task[None] | None = None

        self._started = False
        self._stopping = False
        self._batch_seq = 0

    async def start(self) -> None:
        """Start the WorkGrinder.

        This method initializes the event loop and starts the grinder loop task.
        """
        running_loop = asyncio.get_running_loop()

        if self._started:
            if self._loop is not running_loop:
                raise RuntimeError(
                    "WorkGrinder is already started on a different event loop"
                )
            return

        self._loop = running_loop
        self._stopping = False
        self._task = asyncio.create_task(
            self._grinder_loop(),
            name="leasepool-work-grinder",
        )
        self._started = True

        self._logger.info(
            "WorkGrinder started max_wait_seconds=%s batch_size_threshold=%s "
            "lease_seconds=%s",
            self._max_wait_seconds,
            self._batch_size_threshold,
            self._lease_seconds,
        )

    async def stop(self, *, cancel_pending: bool = False) -> None:
        """Stop the WorkGrinder.

        Args:
            cancel_pending (bool, optional): Whether to cancel pending work items. Defaults to False.
        """
        if not self._started:
            return

        _ = self._require_owner_loop()
        self._stopping = True

        async with self._condition:
            if cancel_pending:
                while self._pending:
                    item = self._pending.popleft()
                    if not item.result_future.done():
                        item.result_future.cancel()

            self._condition.notify_all()

        task = self._task
        if task is not None:
            if cancel_pending:
                task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                if not cancel_pending:
                    raise
            finally:
                self._task = None

        self._started = False
        self._stopping = False
        self._loop = None
        self._logger.info("WorkGrinder stopped")

    async def submit(
        self,
        fn: Callable[..., Any],
        /,
        *args: Any,
        owner: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """Submit a work item to the WorkGrinder.

        Args:
            fn (Callable[..., Any]): The function to execute.
            owner (str | None, optional): The owner of the work item. Defaults to None.

        Returns:
            Any: The result of the work item.
        """
        future = await self.enqueue(fn, *args, owner=owner, **kwargs)
        return await future

    async def enqueue(
        self,
        fn: Callable[..., Any],
        /,
        *args: Any,
        owner: str | None = None,
        **kwargs: Any,
    ) -> asyncio.Future[Any]:
        """Enqueue a work item to the WorkGrinder.

        Args:
            fn (Callable[..., Any]): The function to execute.
            owner (str | None, optional): The owner of the work item. Defaults to None.

        Raises:
            RuntimeError: If the WorkGrinder is not started.
            RuntimeError: If the WorkGrinder is stopping.

        Returns:
            asyncio.Future[Any]: A future representing the result of the work item.
        """
        loop = self._require_owner_loop()

        if self._stopping:
            raise RuntimeError("WorkGrinder is stopping")

        result_future: asyncio.Future[Any] = loop.create_future()

        item = _WorkItem(
            work_id=uuid.uuid4().hex,
            fn=fn,
            args=args,
            kwargs=kwargs,
            result_future=result_future,
            submitted_at=loop.time(),
            owner=owner,
        )

        async with self._condition:
            self._pending.append(item)
            pending_count = len(self._pending)

            self._logger.debug(
                "Queued work work_id=%s owner=%s pending=%s",
                item.work_id,
                owner,
                pending_count,
            )

            if pending_count >= self._batch_size_threshold:
                self._condition.notify_all()
            else:
                self._condition.notify()

        return result_future

    def submit_from_thread(
        self,
        fn: Callable[..., Any],
        /,
        *args: Any,
        owner: str | None = None,
        **kwargs: Any,
    ) -> ConcurrentFuture[Any]:
        """Submit a work item to the WorkGrinder from a different thread.

        Args:
            fn (Callable[..., Any]): The function to execute.
            owner (str | None, optional): The owner of the work item. Defaults to None.

        Raises:
            RuntimeError: If the WorkGrinder is not started.

        Returns:
            ConcurrentFuture[Any]: A future representing the result of the work item.
        """
        loop = self._loop

        if not self._started or loop is None or loop.is_closed():
            raise RuntimeError("WorkGrinder is not started")

        if self._stopping:
            raise RuntimeError("WorkGrinder is stopping")

        return asyncio.run_coroutine_threadsafe(
            self.submit(fn, *args, owner=owner, **kwargs),
            loop,
        )

    def stats(self) -> dict[str, Any]:
        """Get the current statistics of the WorkGrinder.

        This method must be called from the WorkGrinder event-loop thread while
        the grinder is running. Use stats_from_thread() from other threads.
        It is also safe before start or after stop.
        """
        oldest_wait_seconds = 0.0

        if self._started:
            loop = self._require_owner_loop()

            if self._pending:
                oldest_wait_seconds = max(
                    0.0,
                    loop.time() - self._pending[0].submitted_at,
                )

        return {
            "started": self._started,
            "stopping": self._stopping,
            "pending": len(self._pending),
            "batch_size_threshold": self._batch_size_threshold,
            "max_wait_seconds": self._max_wait_seconds,
            "lease_seconds": self._lease_seconds,
            "oldest_wait_seconds": oldest_wait_seconds,
        }

    async def astats(self) -> dict[str, Any]:
        """Get the current statistics of the WorkGrinder asynchronously.

        Returns:
            dict[str, Any]: A dictionary containing the current statistics.
        """
        loop = self._require_owner_loop()
        async with self._condition:
            oldest_wait_seconds = 0.0

            if self._pending:
                oldest_wait_seconds = max(
                    0.0,
                    loop.time() - self._pending[0].submitted_at,
                )

            return {
                "started": self._started,
                "stopping": self._stopping,
                "pending": len(self._pending),
                "batch_size_threshold": self._batch_size_threshold,
                "max_wait_seconds": self._max_wait_seconds,
                "lease_seconds": self._lease_seconds,
                "oldest_wait_seconds": oldest_wait_seconds,
            }


    def stats_from_thread(self, timeout: float | None = None) -> dict[str, Any]:
        """Get the current statistics of the WorkGrinder from a different thread.

        Args:
            timeout (float | None, optional): The maximum time to wait for the statistics.
                Defaults to None.

        Raises:
            RuntimeError: If the WorkGrinder is not started.

        Returns:
            dict[str, Any]: A dictionary containing the current statistics.
        """
        loop = self._loop

        if not self._started or loop is None or loop.is_closed():
            raise RuntimeError("WorkGrinder is not started")

        future = asyncio.run_coroutine_threadsafe(self.astats(), loop)
        return future.result(timeout=timeout)

    def _require_owner_loop(self) -> asyncio.AbstractEventLoop:
        """Return the owning loop or raise if called from the wrong loop."""
        owner_loop = self._loop

        if not self._started or owner_loop is None:
            raise RuntimeError("WorkGrinder is not started")

        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError as exc:
            raise RuntimeError(
                "WorkGrinder async methods must be called from its owning "
                "event loop; use submit_from_thread() or stats_from_thread() "
                "from other threads."
            ) from exc

        if running_loop is not owner_loop:
            raise RuntimeError(
                "WorkGrinder async methods must be called from its owning "
                "event loop; use submit_from_thread() or stats_from_thread() "
                "from other threads."
            )

        return owner_loop

    async def _grinder_loop(self) -> None:
        """The main loop of the WorkGrinder.

        This loop continuously waits for the next batch of work items and processes them.
        It exits when the WorkGrinder is stopping and there are no more pending work items.
        """
        try:
            while True:
                batch = await self._wait_for_next_batch()

                if not batch:
                    if self._stopping:
                        break
                    continue

                await self._process_batch(batch)

                if self._stopping:
                    async with self._condition:
                        if not self._pending:
                            break

        except asyncio.CancelledError:
            raise
        except Exception:
            self._logger.exception("WorkGrinder loop crashed")

            async with self._condition:
                while self._pending:
                    item = self._pending.popleft()
                    if not item.result_future.done():
                        item.result_future.set_exception(
                            RuntimeError("WorkGrinder loop crashed")
                        )

    async def _wait_for_next_batch(self) -> list[_WorkItem]:
        """Wait for the next batch of work items.

        Returns:
            list[_WorkItem]: A list of work items for the next batch.
        """
        assert self._loop is not None

        async with self._condition:
            while True:
                if self._pending:
                    now = self._loop.time()
                    oldest_wait_seconds = now - self._pending[0].submitted_at

                    threshold_reached = len(self._pending) >= self._batch_size_threshold
                    timeout_reached = oldest_wait_seconds >= self._max_wait_seconds

                    if threshold_reached or timeout_reached or self._stopping:
                        return self._drain_pending_locked()

                    remaining = self._max_wait_seconds - oldest_wait_seconds

                    try:
                        await asyncio.wait_for(
                            self._condition.wait(),
                            timeout=remaining,
                        )
                    except asyncio.TimeoutError:
                        pass

                else:
                    if self._stopping:
                        return []

                    await self._condition.wait()

    def _drain_pending_locked(self) -> list[_WorkItem]:
        """Drain all pending work items.

        Returns:
            list[_WorkItem]: A list of all pending work items.
        """
        batch = list(self._pending)
        self._pending.clear()
        return batch

    async def _process_batch(self, batch: list[_WorkItem]) -> None:
        """Process a batch of work items.

        Args:
            batch (list[_WorkItem]): The batch of work items to process.
        """
        live_batch = [item for item in batch if not item.result_future.cancelled()]

        if not live_batch:
            return

        self._batch_seq += 1
        batch_id = self._batch_seq

        lease_owner = f"{self._owner_prefix}-batch-{batch_id}"

        self._logger.info(
            "Processing batch batch_id=%s size=%s lease_seconds=%s",
            batch_id,
            len(live_batch),
            self._lease_seconds,
        )

        lease = None
        executor_futures: list[asyncio.Future[Any]] = []

        try:
            lease = await self._executor_manager.acquire(
                lease_seconds=self._lease_seconds,
                owner=lease_owner,
                wait=True,
            )

            loop = asyncio.get_running_loop()

            for item in live_batch:
                call = functools.partial(item.fn, *item.args, **item.kwargs)

                executor_future = loop.run_in_executor(
                    lease.executor,
                    call,
                )

                executor_futures.append(executor_future)

            results = await asyncio.gather(
                *executor_futures,
                return_exceptions=True,
            )

            for item, result in zip(live_batch, results, strict=True):
                if item.result_future.done():
                    continue

                if isinstance(result, BaseException):
                    item.result_future.set_exception(result)
                else:
                    item.result_future.set_result(result)

            self._logger.info(
                "Finished batch batch_id=%s size=%s",
                batch_id,
                len(live_batch),
            )

        except asyncio.CancelledError:
            self._logger.info(
                "Cancelled batch batch_id=%s size=%s",
                batch_id,
                len(live_batch),
            )

            for executor_future in executor_futures:
                executor_future.cancel()

            for item in live_batch:
                if not item.result_future.done():
                    item.result_future.cancel()

            raise

        except Exception as exc:
            self._logger.exception(
                "Batch failed batch_id=%s size=%s",
                batch_id,
                len(live_batch),
            )

            for item in live_batch:
                if not item.result_future.done():
                    item.result_future.set_exception(exc)

        finally:
            if lease is not None:
                await lease.release()
