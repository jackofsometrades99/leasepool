import asyncio
import time

import pytest

from leasepool import LeasedExecutorManager


async def wait_until(predicate, *, timeout: float = 1.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("condition was not met before timeout")


@pytest.mark.asyncio
async def test_checker_wakes_for_newly_acquired_short_lease() -> None:
    manager = LeasedExecutorManager(
        max_pools=1,
        min_pools=1,
        check_interval=3600.0,
        lease_grace_seconds=0.0,
        workers_per_pool=1,
    )

    await manager.start()
    try:
        lease = await manager.acquire(
            lease_seconds=0.05,
            owner="expiry-test",
        )

        assert lease.lease_id
        assert manager.leased_count == 1

        await wait_until(lambda: manager.leased_count == 0, timeout=1.0)

        assert manager.available_count == 1
    finally:
        await manager.stop()