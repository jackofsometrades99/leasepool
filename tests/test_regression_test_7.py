# Test 7: normal user exceptions do not poison the executor

import pytest

from leasepool import LeasedExecutorManager


def user_error() -> None:
    raise ValueError("normal task failure")


def ok() -> str:
    return "ok"


@pytest.mark.asyncio
async def test_user_function_exception_does_not_retire_executor() -> None:
    manager = LeasedExecutorManager(
        max_pools=1,
        min_pools=1,
        workers_per_pool=1,
    )

    await manager.start()
    try:
        lease = await manager.acquire(owner="normal-error")

        future = lease.executor.submit(user_error)

        with pytest.raises(ValueError):
            future.result(timeout=2.0)

        await lease.release()

        assert manager.leased_count == 0
        assert manager.available_count == 1

        second = await manager.acquire(wait=False, owner="second")
        result = await second.run(ok)
        assert result == "ok"
        await second.release()
    finally:
        await manager.stop()