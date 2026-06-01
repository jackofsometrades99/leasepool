# Test 4: integer config parameters reject non-integral values and accept valid positive integers

import pytest

from leasepool import LeasedExecutorManager


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_pools": 0.9},
        {"min_pools": 0.9},
        {"units_per_pool": 0.5},
        {"workers_per_pool": 0.5},
        {"max_pools": True},
        {"min_pools": False},
        {"max_pools": "2"},
    ],
)
def test_integer_config_rejects_non_integral_values(kwargs):
    base = {
        "max_pools": 2,
        "min_pools": 1,
        "units_per_pool": 10,
        "workers_per_pool": 4,
    }
    base.update(kwargs)

    with pytest.raises(ValueError):
        LeasedExecutorManager(**base)


def test_integer_config_accepts_valid_positive_ints():
    manager = LeasedExecutorManager(
        max_pools=2,
        min_pools=1,
        units_per_pool=10,
        workers_per_pool=4,
    )

    assert manager.total_count == 0