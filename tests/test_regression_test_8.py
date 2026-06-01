# Test 8: immediate broken submit retires the lease

import pytest
from concurrent.futures import BrokenExecutor, Executor, Future

from leasepool import LeasedExecutorManager


class AlwaysBrokenExecutor(Executor):
    def submit(self, fn, /, *args, **kwargs) -> Future:
        raise BrokenExecutor("cannot submit")

    def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
        pass


@pytest.mark.asyncio
async def test_immediate_broken_submit_retires_lease(monkeypatch) -> None:
    manager = LeasedExecutorManager(
        max_pools=1,
        min_pools=1,
        workers_per_pool=1,
    )

    await manager.start()
    try:
        with manager._lock:
            manager._available.clear()
            manager._available.append(AlwaysBrokenExecutor())

        lease = await manager.acquire(owner="immediate-broken")

        with pytest.raises(BrokenExecutor):
            lease.executor.submit(lambda: "never runs")

        assert manager.leased_count == 0
        assert manager.available_count == 1
    finally:
        await manager.stop()