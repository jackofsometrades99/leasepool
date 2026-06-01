# Test 17: A broken worker initializer causes the pool to be retired
# and the broken executor to be shut down from the callback, not immediately from submit()
# This tests the behavior of both the process and interpreter backends, which share the same
# initializer failure handling logic. The test verifies that a broken executor is not returned
# to the available pool and that deferred shutdown from the callback is used instead
# of immediate shutdown from submit().


from __future__ import annotations

import asyncio
import concurrent.futures
import multiprocessing
from collections.abc import Callable
from concurrent.futures import BrokenExecutor, Executor
from typing import Any

import pytest

from leasepool import ExecutorBackend, LeasedExecutorManager


def bad_initializer() -> None:
    """Top-level initializer so process/interpreter workers can import it."""
    raise RuntimeError("intentional worker initializer failure")


def simple_task(value: int) -> int:
    """Top-level callable so process/interpreter workers can import it."""
    return value + 1


async def wait_until(
    predicate: Callable[[], bool],
    *,
    timeout: float = 5.0,
    interval: float = 0.01,
) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout

    while loop.time() < deadline:
        if predicate():
            return
        await asyncio.sleep(interval)

    raise AssertionError("condition was not met before timeout")


async def assert_broken_backend_is_retired_and_deferred_shutdown_is_used(
    *,
    backend: ExecutorBackend,
    executor_kwargs: dict[str, Any] | None = None,
) -> None:
    shutdown_called = asyncio.Event()
    shutdown_executor_types: list[str] = []

    manager = LeasedExecutorManager(
        backend=backend,
        max_pools=1,
        min_pools=1,
        workers_per_pool=1,
        initializer=bad_initializer,
        **(executor_kwargs or {}),
    )

    original_shutdown_from_callback = manager._shutdown_executor_from_callback

    def wrapped_shutdown_from_callback(executor: Executor) -> None:
        shutdown_executor_types.append(type(executor).__name__)
        shutdown_called.set()
        original_shutdown_from_callback(executor)

    manager._shutdown_executor_from_callback = wrapped_shutdown_from_callback  # type: ignore[method-assign]

    await manager.start()

    try:
        lease = await manager.acquire(owner=f"broken-{backend.value}")

        # submit() should succeed first. The worker initializer failure should
        # then break the pool and complete this Future with a BrokenExecutor
        # subclass. That exercises _on_lease_future_done(), not only the
        # immediate submit-failure path.
        future = lease.executor.submit(simple_task, 1)

        with pytest.raises(BrokenExecutor):
            future.result(timeout=5.0)

        await asyncio.wait_for(shutdown_called.wait(), timeout=5.0)

        await wait_until(
            lambda: manager.leased_count == 0 and manager.available_count == 1,
            timeout=5.0,
        )

        # Releasing the old lease must be a no-op. The broken executor must not
        # be reinserted into the available pool.
        await lease.release()

        assert manager.leased_count == 0
        assert manager.available_count == 1
        assert shutdown_executor_types

    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_broken_process_pool_is_retired_and_shutdown_from_callback() -> None:
    await assert_broken_backend_is_retired_and_deferred_shutdown_is_used(
        backend=ExecutorBackend.PROCESS,
        executor_kwargs={
            # Use spawn so the test does not depend on fork-only behavior.
            "mp_context": multiprocessing.get_context("spawn"),
        },
    )


@pytest.mark.skipif(
    not hasattr(concurrent.futures, "InterpreterPoolExecutor"),
    reason="InterpreterPoolExecutor is available on Python 3.14+ only",
)
@pytest.mark.asyncio
async def test_broken_interpreter_pool_is_retired_and_shutdown_from_callback() -> None:
    await assert_broken_backend_is_retired_and_deferred_shutdown_is_used(
        backend=ExecutorBackend.INTERPRETER,
    )