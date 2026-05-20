from __future__ import annotations

import asyncio

import pytest

from helpers import add, raise_value_error
from leasepool import LeasedExecutorManager, WorkGrinder


@pytest.mark.asyncio
async def test_submit_before_start_raises() -> None:
    manager = LeasedExecutorManager(max_pools=1)
    grinder = WorkGrinder(executor_manager=manager)

    with pytest.raises(RuntimeError, match="not started"):
        await grinder.submit(add, 1, 2)


@pytest.mark.asyncio
async def test_enqueue_before_start_raises() -> None:
    manager = LeasedExecutorManager(max_pools=1)
    grinder = WorkGrinder(executor_manager=manager)

    with pytest.raises(RuntimeError, match="not started"):
        await grinder.enqueue(add, 1, 2)


@pytest.mark.asyncio
async def test_stop_before_start_is_safe() -> None:
    manager = LeasedExecutorManager(max_pools=1)
    grinder = WorkGrinder(executor_manager=manager)

    await grinder.stop()

    assert grinder.stats()["started"] is False


@pytest.mark.asyncio
async def test_start_is_idempotent() -> None:
    manager = LeasedExecutorManager(max_pools=1, min_pools=1)
    grinder = WorkGrinder(executor_manager=manager)

    await manager.start()

    try:
        await grinder.start()
        await grinder.start()

        assert grinder.stats()["started"] is True
    finally:
        await grinder.stop(cancel_pending=True)
        await manager.stop()


@pytest.mark.asyncio
async def test_submit_raises_when_grinder_is_stopping() -> None:
    manager = LeasedExecutorManager(max_pools=1, min_pools=1)
    grinder = WorkGrinder(
        executor_manager=manager,
        max_wait_seconds=10,
        batch_size_threshold=10,
    )

    await manager.start()
    await grinder.start()

    try:
        stop_task = asyncio.create_task(grinder.stop(cancel_pending=False))
        await asyncio.sleep(0)

        with pytest.raises(RuntimeError, match="stopping"):
            await grinder.submit(add, 1, 2)

        await stop_task
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_stats_contains_expected_fields() -> None:
    manager = LeasedExecutorManager(max_pools=1, min_pools=1)
    grinder = WorkGrinder(
        executor_manager=manager,
        max_wait_seconds=3,
        batch_size_threshold=7,
        lease_seconds=11,
    )

    stats = grinder.stats()

    assert stats["started"] is False
    assert stats["stopping"] is False
    assert stats["pending"] == 0
    assert stats["batch_size_threshold"] == 7
    assert stats["max_wait_seconds"] == 3
    assert stats["lease_seconds"] == 11
    assert stats["oldest_wait_seconds"] == 0.0


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"max_wait_seconds": 0}, "max_wait_seconds must be > 0"),
        ({"batch_size_threshold": 0}, "batch_size_threshold must be > 0"),
        ({"lease_seconds": 0}, "lease_seconds must be > 0"),
    ],
)
def test_constructor_validation(kwargs: dict[str, object], message: str) -> None:
    manager = LeasedExecutorManager(max_pools=1)

    with pytest.raises(ValueError, match=message):
        WorkGrinder(executor_manager=manager, **kwargs)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_enqueue_returns_future_that_resolves() -> None:
    manager = LeasedExecutorManager(max_pools=1, min_pools=1, workers_per_pool=2)
    grinder = WorkGrinder(
        executor_manager=manager,
        max_wait_seconds=1,
        batch_size_threshold=1,
    )

    await manager.start()
    await grinder.start()

    try:
        future = await grinder.enqueue(add, 20, 22)

        assert await future == 42
    finally:
        await grinder.stop(cancel_pending=True)
        await manager.stop()


@pytest.mark.asyncio
async def test_batch_processes_when_threshold_is_reached() -> None:
    manager = LeasedExecutorManager(max_pools=1, min_pools=1, workers_per_pool=4)
    grinder = WorkGrinder(
        executor_manager=manager,
        max_wait_seconds=60,
        batch_size_threshold=5,
    )

    await manager.start()
    await grinder.start()

    try:
        results = await asyncio.gather(*(grinder.submit(add, i, i) for i in range(5)))

        assert results == [0, 2, 4, 6, 8]
    finally:
        await grinder.stop(cancel_pending=True)
        await manager.stop()


@pytest.mark.asyncio
async def test_batch_processes_when_oldest_item_times_out() -> None:
    manager = LeasedExecutorManager(max_pools=1, min_pools=1, workers_per_pool=2)
    grinder = WorkGrinder(
        executor_manager=manager,
        max_wait_seconds=0.05,
        batch_size_threshold=100,
    )

    await manager.start()
    await grinder.start()

    try:
        assert await grinder.submit(add, 1, 2) == 3
    finally:
        await grinder.stop(cancel_pending=True)
        await manager.stop()


@pytest.mark.asyncio
async def test_callable_exception_is_propagated_to_submitter() -> None:
    manager = LeasedExecutorManager(max_pools=1, min_pools=1)
    grinder = WorkGrinder(
        executor_manager=manager,
        max_wait_seconds=1,
        batch_size_threshold=1,
    )

    await manager.start()
    await grinder.start()

    try:
        with pytest.raises(ValueError, match="grinder boom"):
            await grinder.submit(raise_value_error, "grinder boom")
    finally:
        await grinder.stop(cancel_pending=True)
        await manager.stop()


@pytest.mark.asyncio
async def test_cancel_pending_stop_cancels_queued_futures() -> None:
    manager = LeasedExecutorManager(max_pools=1, min_pools=1)
    grinder = WorkGrinder(
        executor_manager=manager,
        max_wait_seconds=60,
        batch_size_threshold=100,
    )

    await manager.start()
    await grinder.start()

    try:
        future = await grinder.enqueue(add, 1, 2)

        await grinder.stop(cancel_pending=True)

        assert future.cancelled()
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_stop_without_cancel_drains_pending_work() -> None:
    manager = LeasedExecutorManager(max_pools=1, min_pools=1)
    grinder = WorkGrinder(
        executor_manager=manager,
        max_wait_seconds=60,
        batch_size_threshold=100,
    )

    await manager.start()
    await grinder.start()

    try:
        future = await grinder.enqueue(add, 10, 32)

        await grinder.stop(cancel_pending=False)

        assert await future == 42
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_cancelled_work_item_is_skipped_but_other_items_complete() -> None:
    manager = LeasedExecutorManager(max_pools=1, min_pools=1, workers_per_pool=2)
    grinder = WorkGrinder(
        executor_manager=manager,
        max_wait_seconds=1,
        batch_size_threshold=2,
    )

    await manager.start()
    await grinder.start()

    try:
        cancelled = await grinder.enqueue(add, 1, 1)
        active = await grinder.enqueue(add, 20, 22)

        cancelled.cancel()

        assert await active == 42
        assert cancelled.cancelled()
    finally:
        await grinder.stop(cancel_pending=True)
        await manager.stop()


@pytest.mark.asyncio
async def test_submit_from_thread_returns_concurrent_future() -> None:
    manager = LeasedExecutorManager(max_pools=1, min_pools=1, workers_per_pool=2)
    grinder = WorkGrinder(
        executor_manager=manager,
        max_wait_seconds=1,
        batch_size_threshold=1,
    )

    await manager.start()
    await grinder.start()

    try:
        def call_from_worker_thread() -> int:
            future = grinder.submit_from_thread(add, 20, 22)
            return future.result(timeout=2)

        assert await asyncio.to_thread(call_from_worker_thread) == 42
    finally:
        await grinder.stop(cancel_pending=True)
        await manager.stop()
