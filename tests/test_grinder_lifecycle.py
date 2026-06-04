from __future__ import annotations

import math
import pytest
import asyncio
from typing import Any
from concurrent.futures import Executor
from concurrent.futures import Future as ConcurrentFuture
from helpers import add, raise_value_error
from leasepool import LeasedExecutorManager, WorkGrinder


async def _wait_for_pending_count(
    grinder: WorkGrinder,
    expected: int,
    *,
    timeout: float = 1.0,
) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout

    while loop.time() < deadline:
        if grinder.stats()["pending"] == expected:
            return

        await asyncio.sleep(0)

    assert grinder.stats()["pending"] == expected


class _FailAfterNSubmitsExecutor(Executor):
    def __init__(self, *, fail_after: int, error: Exception) -> None:
        self._fail_after = fail_after
        self._error = error
        self.submit_count = 0

    def submit(self, fn, /, *args, **kwargs):  # type: ignore[no-untyped-def]
        self.submit_count += 1

        if self.submit_count > self._fail_after:
            raise self._error

        future: ConcurrentFuture[Any] = ConcurrentFuture()

        try:
            result = fn(*args, **kwargs)
        except BaseException as exc:
            future.set_exception(exc)
        else:
            future.set_result(result)

        return future

    def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
        return None


class _FakeLease:
    def __init__(self, executor: Executor) -> None:
        self.executor = executor
        self.released = False

    async def release(self) -> None:
        self.released = True


class _FakeManager:
    def __init__(self, lease: _FakeLease) -> None:
        self._lease = lease

    async def acquire(self, **kwargs: Any) -> _FakeLease:
        return self._lease


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
    manager = LeasedExecutorManager(max_pools=1, min_pools=1, workers_per_pool=2, check_interval=1)
    grinder = WorkGrinder(
        executor_manager=manager,
        max_wait_seconds=5,
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
    manager = LeasedExecutorManager(max_pools=1, min_pools=1, workers_per_pool=4, check_interval=1)
    grinder = WorkGrinder(
        executor_manager=manager,
        max_wait_seconds=5,
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
    manager = LeasedExecutorManager(max_pools=1, min_pools=1, workers_per_pool=2, check_interval=1)
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
    manager = LeasedExecutorManager(max_pools=1, min_pools=1, check_interval=1)
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
    manager = LeasedExecutorManager(max_pools=1, min_pools=1, check_interval=1)
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
    manager = LeasedExecutorManager(max_pools=1, min_pools=1, workers_per_pool=2, check_interval=1)
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
    manager = LeasedExecutorManager(max_pools=1, min_pools=1, workers_per_pool=2, check_interval=1)
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


@pytest.mark.parametrize(
    "bad_threshold",
    [
        0.5,
        1.1,
        1.9,
        True,
        False,
        "2",
    ],
)
def test_batch_size_threshold_rejects_non_integer_values(
    bad_threshold: object,
) -> None:
    manager = LeasedExecutorManager(max_pools=1)

    with pytest.raises(ValueError, match="batch_size_threshold must be an integer > 0"):
        WorkGrinder(
            executor_manager=manager,
            batch_size_threshold=bad_threshold,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "bad_wait_seconds",
    [
        math.nan,
        math.inf,
        -math.inf,
        True,
        False,
        "not-a-number",
    ],
)
def test_max_wait_seconds_rejects_non_finite_or_non_numeric_values(
    bad_wait_seconds: object,
) -> None:
    manager = LeasedExecutorManager(max_pools=1)

    with pytest.raises(
        ValueError,
        match="max_wait_seconds must be a finite number > 0",
    ):
        WorkGrinder(
            executor_manager=manager,
            max_wait_seconds=bad_wait_seconds,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "bad_lease_seconds",
    [
        math.nan,
        math.inf,
        -math.inf,
        True,
        False,
        "not-a-number",
    ],
)
def test_lease_seconds_rejects_non_finite_or_non_numeric_values(
    bad_lease_seconds: object,
) -> None:
    manager = LeasedExecutorManager(max_pools=1)

    with pytest.raises(
        ValueError,
        match="lease_seconds must be a finite number > 0",
    ):
        WorkGrinder(
            executor_manager=manager,
            lease_seconds=bad_lease_seconds,  # type: ignore[arg-type]
        )


def test_batch_size_threshold_accepts_integer_value() -> None:
    manager = LeasedExecutorManager(max_pools=1)

    grinder = WorkGrinder(
        executor_manager=manager,
        batch_size_threshold=3,
    )

    assert grinder.stats()["batch_size_threshold"] == 3


def test_max_wait_seconds_accepts_positive_finite_values() -> None:
    manager = LeasedExecutorManager(max_pools=1)

    grinder = WorkGrinder(
        executor_manager=manager,
        max_wait_seconds=0.25,
    )

    assert grinder.stats()["max_wait_seconds"] == 0.25


def test_lease_seconds_accepts_positive_finite_values() -> None:
    manager = LeasedExecutorManager(max_pools=1)

    grinder = WorkGrinder(
        executor_manager=manager,
        lease_seconds=0.25,
    )

    assert grinder.stats()["lease_seconds"] == 0.25


@pytest.mark.asyncio
async def test_submit_from_thread_rejects_owner_event_loop_thread() -> None:
    manager = LeasedExecutorManager(max_pools=1, min_pools=1, workers_per_pool=2)
    grinder = WorkGrinder(
        executor_manager=manager,
        max_wait_seconds=1,
        batch_size_threshold=1,
    )

    await manager.start()
    await grinder.start()

    try:
        with pytest.raises(RuntimeError, match="owning event-loop thread"):
            grinder.submit_from_thread(add, 20, 22)
    finally:
        await grinder.stop(cancel_pending=True)
        await manager.stop()


@pytest.mark.asyncio
async def test_stats_from_thread_rejects_owner_event_loop_thread() -> None:
    manager = LeasedExecutorManager(max_pools=1, min_pools=1)
    grinder = WorkGrinder(executor_manager=manager)

    await manager.start()
    await grinder.start()

    try:
        with pytest.raises(RuntimeError, match="owning event-loop thread"):
            grinder.stats_from_thread(timeout=0.01)
    finally:
        await grinder.stop(cancel_pending=True)
        await manager.stop()


@pytest.mark.asyncio
async def test_stats_from_thread_returns_stats_from_worker_thread() -> None:
    manager = LeasedExecutorManager(max_pools=1, min_pools=1)
    grinder = WorkGrinder(executor_manager=manager)

    await manager.start()
    await grinder.start()

    try:
        def call_from_worker_thread() -> dict[str, object]:
            return grinder.stats_from_thread(timeout=2)

        stats = await asyncio.to_thread(call_from_worker_thread)

        assert stats["started"] is True
        assert stats["stopping"] is False
        assert stats["pending"] == 0
    finally:
        await grinder.stop(cancel_pending=True)
        await manager.stop()


@pytest.mark.asyncio
async def test_cancelled_pending_work_item_is_removed_immediately() -> None:
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

        assert grinder.stats()["pending"] == 1

        future.cancel()

        await _wait_for_pending_count(grinder, 0)

        assert future.cancelled()
        assert grinder.stats()["pending"] == 0
    finally:
        await grinder.stop(cancel_pending=True)
        await manager.stop()


@pytest.mark.asyncio
async def test_cancelled_pending_work_item_does_not_remove_other_pending_items() -> None:
    manager = LeasedExecutorManager(max_pools=1, min_pools=1)
    grinder = WorkGrinder(
        executor_manager=manager,
        max_wait_seconds=60,
        batch_size_threshold=100,
    )

    await manager.start()
    await grinder.start()

    try:
        cancelled = await grinder.enqueue(add, 1, 2)
        active = await grinder.enqueue(add, 20, 22)

        assert grinder.stats()["pending"] == 2

        cancelled.cancel()

        await _wait_for_pending_count(grinder, 1)

        assert cancelled.cancelled()
        assert not active.done()
        assert grinder.stats()["pending"] == 1
    finally:
        await grinder.stop(cancel_pending=True)
        await manager.stop()


@pytest.mark.asyncio
async def test_partial_batch_submission_failure_preserves_submitted_result() -> None:
    submit_error = RuntimeError("submit boom")
    executor = _FailAfterNSubmitsExecutor(fail_after=1, error=submit_error)
    lease = _FakeLease(executor)
    manager = _FakeManager(lease)

    grinder = WorkGrinder(
        executor_manager=manager,  # type: ignore[arg-type]
        max_wait_seconds=60,
        batch_size_threshold=2,
    )

    await grinder.start()

    try:
        first = await grinder.enqueue(add, 1, 2)
        second = await grinder.enqueue(add, 20, 22)

        assert await first == 3

        with pytest.raises(RuntimeError, match="submit boom"):
            await second

        assert executor.submit_count == 2
        assert lease.released is True
    finally:
        await grinder.stop(cancel_pending=True)


@pytest.mark.asyncio
async def test_partial_batch_submission_failure_preserves_submitted_exception() -> None:
    submit_error = RuntimeError("submit boom")
    executor = _FailAfterNSubmitsExecutor(fail_after=1, error=submit_error)
    lease = _FakeLease(executor)
    manager = _FakeManager(lease)

    grinder = WorkGrinder(
        executor_manager=manager,  # type: ignore[arg-type]
        max_wait_seconds=60,
        batch_size_threshold=2,
    )

    await grinder.start()

    try:
        first = await grinder.enqueue(raise_value_error, "callable boom")
        second = await grinder.enqueue(add, 20, 22)

        with pytest.raises(ValueError, match="callable boom"):
            await first

        with pytest.raises(RuntimeError, match="submit boom"):
            await second

        assert executor.submit_count == 2
        assert lease.released is True
    finally:
        await grinder.stop(cancel_pending=True)

