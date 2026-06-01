# Test 1: released executor is not reused while submitted work is running

import asyncio
import threading
import time

import pytest

from leasepool import LeasedExecutorManager
from leasepool.exceptions import LeaseUnavailableError


def wait_on_event(event: threading.Event) -> bool:
    return event.wait(timeout=2.0)


async def wait_until(predicate, *, timeout: float = 1.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("condition was not met before timeout")


@pytest.mark.asyncio
async def test_release_drains_pending_futures_before_reuse() -> None:
    manager = LeasedExecutorManager(
        max_pools=1,
        min_pools=1,
        workers_per_pool=1,
        check_interval=3600.0,
    )

    await manager.start()
    try:
        event = threading.Event()

        lease = await manager.acquire(owner="first")
        future = lease.executor.submit(wait_on_event, event)

        await lease.release()

        assert manager.leased_count == 1
        assert manager.available_count == 0

        with pytest.raises(LeaseUnavailableError):
            await manager.acquire(wait=False, owner="second")

        event.set()
        assert future.result(timeout=1.0) is True

        await wait_until(lambda: manager.available_count == 1)

        second = await manager.acquire(wait=False, owner="second")
        await second.release()
    finally:
        await manager.stop()