from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Callable
from typing import Any


async def wait_until(
    predicate: Callable[[], bool],
    *,
    timeout: float = 1.0,
    interval: float = 0.01,
) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout

    while loop.time() < deadline:
        if predicate():
            return
        await asyncio.sleep(interval)

    assert predicate(), "condition was not reached before timeout"


def identity(value: Any) -> Any:
    return value


def add(left: int, right: int) -> int:
    return left + right


def multiply(left: int, right: int) -> int:
    return left * right


def with_kwargs(*, left: int, right: int) -> int:
    return left + right


def raise_value_error(message: str = "boom") -> None:
    raise ValueError(message)


def blocking_sleep_return(delay: float, value: Any) -> Any:
    time.sleep(delay)
    return value


def current_thread_name() -> str:
    return threading.current_thread().name


def count_primes(limit: int) -> int:
    count = 0

    for number in range(2, limit):
        for divisor in range(2, int(number**0.5) + 1):
            if number % divisor == 0:
                break
        else:
            count += 1

    return count


def log_and_multiply(logger_name: str, left: int, right: int) -> int:
    import logging

    logging.getLogger(logger_name).info("worker multiplying %s x %s", left, right)
    return left * right


def worker_initializer_logs(logger_name: str, message: str) -> None:
    import logging

    logging.getLogger(logger_name).info(message)

