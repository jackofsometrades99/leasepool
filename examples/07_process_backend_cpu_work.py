"""
CPU-heavy work with ProcessPoolExecutor backend on Python 3.11.

Use the process backend for CPU-bound work that should use multiple CPU cores.

Important:
- submitted functions must be top-level importable functions
- arguments and return values must be picklable
- do not submit lambdas, nested functions, open sockets, Redis clients, or DB clients
"""

from __future__ import annotations

import asyncio

from leasepool import ExecutorBackend, LeasedExecutorManager


def count_primes(limit: int) -> int:
    count = 0

    for number in range(2, limit):
        for divisor in range(2, int(number**0.5) + 1):
            if number % divisor == 0:
                break
        else:
            count += 1

    return count


async def main() -> None:
    manager = LeasedExecutorManager(
        backend=ExecutorBackend.PROCESS,
        max_pools=1,
        min_pools=1,
        workers_per_pool=4,
    )

    await manager.start()

    try:
        async with await manager.acquire(owner="cpu-primes") as lease:
            results = await asyncio.gather(
                lease.run(count_primes, 20_000),
                lease.run(count_primes, 21_000),
                lease.run(count_primes, 22_000),
                lease.run(count_primes, 23_000),
            )

        print("Prime counts:", results)

    finally:
        await manager.stop()


if __name__ == "__main__":
    asyncio.run(main())
