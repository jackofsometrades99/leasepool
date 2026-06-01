# Test 3: normal lease.run() still works
import pytest

from leasepool import LeasedExecutorManager


def add(a: int, b: int) -> int:
    return a + b


@pytest.mark.asyncio
async def test_lease_run_still_releases_immediately_after_awaited_work() -> None:
    manager = LeasedExecutorManager(
        max_pools=1,
        min_pools=1,
        workers_per_pool=1,
    )

    await manager.start()
    try:
        async with await manager.acquire(owner="run") as lease:
            result = await lease.run(add, 2, 3)

        assert result == 5
        assert manager.leased_count == 0
        assert manager.available_count == 1
    finally:
        await manager.stop()