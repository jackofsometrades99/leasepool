# Test 10: acquire rejects invalid lease_seconds values
import math

import pytest

from leasepool import LeasedExecutorManager


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "lease_seconds",
    [
        0,
        -1,
        math.nan,
        math.inf,
        -math.inf,
        True,
        "not-a-number",
    ],
)
async def test_acquire_rejects_invalid_lease_seconds(lease_seconds):
    manager = LeasedExecutorManager(max_pools=1)

    await manager.start()
    try:
        with pytest.raises(ValueError):
            await manager.acquire(lease_seconds=lease_seconds)
    finally:
        await manager.stop()