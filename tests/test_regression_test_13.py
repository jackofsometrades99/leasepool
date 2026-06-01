# Test 13: stopping the grinder with cancel_pending=True cancels pending work and cancels in-flight batch
import asyncio
import threading

import pytest

from leasepool import LeasedExecutorManager, WorkGrinder


def wait_on_event(event: threading.Event) -> bool:
    return event.wait(timeout=5.0)


@pytest.mark.asyncio
async def test_work_grinder_stop_cancel_pending_cancels_in_flight_batch() -> None:
    manager = LeasedExecutorManager(
        max_pools=1,
        min_pools=1,
        workers_per_pool=1,
    )
    await manager.start()

    grinder = WorkGrinder(
        executor_manager=manager,
        max_wait_seconds=60.0,
        batch_size_threshold=1,
        lease_seconds=10.0,
    )
    await grinder.start()

    event = threading.Event()

    try:
        result_future = await grinder.enqueue(wait_on_event, event)

        await asyncio.sleep(0.05)

        await asyncio.wait_for(
            grinder.stop(cancel_pending=True),
            timeout=1.0,
        )

        assert result_future.cancelled()
        assert not grinder.stats()["started"]

    finally:
        event.set()
        await manager.stop()