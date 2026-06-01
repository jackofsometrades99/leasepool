# Test 2: released lease rejects new submissions while draining

import threading

import pytest

from leasepool import LeasedExecutorManager
from leasepool.exceptions import LeaseExpiredError


def wait_on_event(event: threading.Event) -> bool:
    return event.wait(timeout=2.0)


@pytest.mark.asyncio
async def test_released_draining_lease_rejects_new_submissions() -> None:
    manager = LeasedExecutorManager(
        max_pools=1,
        min_pools=1,
        workers_per_pool=1,
    )

    await manager.start()
    try:
        event = threading.Event()

        lease = await manager.acquire(owner="owner")
        future = lease.executor.submit(wait_on_event, event)

        await lease.release()

        with pytest.raises(LeaseExpiredError):
            lease.executor.submit(lambda: "should not run")

        event.set()
        assert future.result(timeout=1.0) is True
    finally:
        await manager.stop()