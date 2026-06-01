# Test 15: WorkGrinder.submit_from_thread() works correctly

import asyncio
import pytest

from leasepool import LeasedExecutorManager, WorkGrinder


def add(a: int, b: int) -> int:
    return a + b


@pytest.mark.asyncio
async def test_work_grinder_submit_from_thread_still_works() -> None:
    manager = LeasedExecutorManager(max_pools=1)
    await manager.start()

    grinder = WorkGrinder(
        executor_manager=manager,
        batch_size_threshold=1,
        max_wait_seconds=60.0,
    )
    await grinder.start()

    results: list[int] = []
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            future = grinder.submit_from_thread(add, 2, 3)
            results.append(future.result(timeout=2.0))
        except BaseException as exc:
            errors.append(exc)

    await asyncio.to_thread(worker)

    try:
        assert errors == []
        assert results == [5]
    finally:
        await grinder.stop(cancel_pending=True)
        await manager.stop()