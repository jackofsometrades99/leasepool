# Test 6: broken thread pool is not returned to _available

import pytest

from leasepool import LeasedExecutorManager


def bad_initializer() -> None:
    raise RuntimeError("initializer failed")


def add_one(value: int) -> int:
    return value + 1


@pytest.mark.asyncio
async def test_broken_thread_executor_is_not_reused_after_future_failure() -> None:
    manager = LeasedExecutorManager(
        max_pools=1,
        min_pools=1,
        workers_per_pool=1,
        initializer=bad_initializer,
    )

    await manager.start()
    try:
        lease = await manager.acquire(owner="broken-thread")

        future = lease.executor.submit(add_one, 1)

        with pytest.raises(Exception) as exc_info:
            future.result(timeout=2.0)

        assert "Broken" in type(exc_info.value).__name__

        # The callback should retire the broken lease and create replacement
        # capacity, but the broken executor itself must not become available.
        assert manager.leased_count == 0
        assert manager.available_count == 1

        # Releasing the old lease should be a no-op, not a path that returns the
        # broken executor to available.
        await lease.release()

        assert manager.leased_count == 0
        assert manager.available_count == 1
    finally:
        await manager.stop()