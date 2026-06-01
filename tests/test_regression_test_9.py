# Test 9: constructor rejects invalid lease timings
import math

import pytest

from leasepool import LeasedExecutorManager


@pytest.mark.parametrize(
    "kwargs",
    [
        {"default_lease_seconds": 0},
        {"default_lease_seconds": -1},
        {"default_lease_seconds": math.nan},
        {"default_lease_seconds": math.inf},
        {"default_lease_seconds": -math.inf},
        {"default_lease_seconds": True},
        {"default_lease_seconds": "not-a-number"},
        {"lease_grace_seconds": -1},
        {"lease_grace_seconds": math.nan},
        {"lease_grace_seconds": math.inf},
        {"lease_grace_seconds": -math.inf},
        {"lease_grace_seconds": False},
        {"lease_grace_seconds": "not-a-number"},
    ],
)
def test_constructor_rejects_invalid_lease_timings(kwargs):
    base = {
        "max_pools": 2,
        "min_pools": 1,
        "default_lease_seconds": 300.0,
        "lease_grace_seconds": 15.0,
    }
    base.update(kwargs)

    with pytest.raises(ValueError):
        LeasedExecutorManager(**base)


def test_constructor_accepts_zero_lease_grace_seconds():
    manager = LeasedExecutorManager(
        max_pools=1,
        lease_grace_seconds=0.0,
    )

    assert manager.total_count == 0