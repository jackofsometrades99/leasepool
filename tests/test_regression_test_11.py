# Test 11: constructor rejects invalid check_interval values

import math

import pytest

from leasepool import LeasedExecutorManager


@pytest.mark.parametrize(
    "check_interval",
    [
        0,
        -1,
        math.nan,
        math.inf,
        -math.inf,
        True,
        False,
        "not-a-number",
    ],
)
def test_constructor_rejects_invalid_check_interval(check_interval):
    with pytest.raises(ValueError):
        LeasedExecutorManager(
            max_pools=1,
            check_interval=check_interval,
        )


@pytest.mark.parametrize(
    "check_interval",
    [
        0.001,
        1,
        120.0,
        "2.5",
    ],
)
def test_constructor_accepts_positive_finite_check_interval(check_interval):
    manager = LeasedExecutorManager(
        max_pools=1,
        check_interval=check_interval,
    )

    assert manager.total_count == 0