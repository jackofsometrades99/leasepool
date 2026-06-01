# Test 12: stopping the grinder with cancel_pending=True cancels pending work and unblocks blocked acquire
import asyncio

import pytest

from leasepool import LeasedExecutorManager, WorkGrinder


def work() -> str:
    return "done"


@pytest.mark.asyncio
async def test_work_grinder_stop_cancel_pending_cancels_blocked_acquire() -> None:
    manager = LeasedExecutorManager(
        max_pools=1,
        min_pools=1,
        workers_per_pool=1,
    )
    await manager.start()

    holder = await manager.acquire(owner="holder")

    grinder = WorkGrinder(
        executor_manager=manager,
        max_wait_seconds=60.0,
        batch_size_threshold=1,
        lease_seconds=10.0,
    )
    await grinder.start()

    try:
        result_future = await grinder.enqueue(work)

        # Let the grinder drain the queued work and reach manager.acquire(...).
        await asyncio.sleep(0.05)

        await asyncio.wait_for(
            grinder.stop(cancel_pending=True),
            timeout=1.0,
        )

        assert result_future.cancelled()
        assert not grinder.stats()["started"]

    finally:
        await holder.release()
        await manager.stop()