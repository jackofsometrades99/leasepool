# Test 16: WorkGrinder.stats() raises RuntimeError when called from the wrong thread, and stats_from_thread() works correctly

import asyncio
import threading

import pytest

from leasepool import LeasedExecutorManager, WorkGrinder


@pytest.mark.asyncio
async def test_work_grinder_stats_loop_ownership() -> None:
    manager = LeasedExecutorManager(max_pools=1)
    await manager.start()

    grinder = WorkGrinder(executor_manager=manager)
    await grinder.start()

    thread_stats: list[dict] = []
    errors: list[BaseException] = []

    def worker() -> None:
        async def wrong_loop_stats() -> None:
            with pytest.raises(RuntimeError):
                grinder.stats()

        try:
            asyncio.run(wrong_loop_stats())
            thread_stats.append(grinder.stats_from_thread(timeout=2.0))
        except BaseException as exc:
            errors.append(exc)

    await asyncio.to_thread(worker)

    try:
        assert errors == []
        assert thread_stats[0]["started"] is True
    finally:
        await grinder.stop(cancel_pending=True)
        await manager.stop()