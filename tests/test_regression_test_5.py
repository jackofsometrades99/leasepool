# Test 5: waiting acquire during stop does not crash with attribute error
import asyncio

import pytest

from leasepool import LeasedExecutorManager
from leasepool.exceptions import LeasePoolNotStartedError


@pytest.mark.asyncio
async def test_waiting_acquire_during_stop_does_not_crash_with_attribute_error() -> None:
    manager = LeasedExecutorManager(
        max_pools=1,
        min_pools=1,
        workers_per_pool=1,
        check_interval=3600.0,
    )

    await manager.start()

    lease = await manager.acquire(owner="holder")

    waiter = asyncio.create_task(
        manager.acquire(owner="waiter", timeout=10.0)
    )

    await asyncio.sleep(0.05)
    await manager.stop()

    with pytest.raises(LeasePoolNotStartedError):
        await waiter

    await lease.release()