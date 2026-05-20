"""
Quickstart: run one blocking sync function from async code.

This is the most basic `leasepool` usage:

1. create a manager
2. start it
3. acquire a lease
4. run sync work inside the leased executor
5. stop the manager
"""

from __future__ import annotations

import asyncio
import time

from leasepool import ExecutorBackend, LeasedExecutorManager


def blocking_uppercase(value: str) -> str:
    time.sleep(0.2)
    return value.upper()


async def main() -> None:
    manager = LeasedExecutorManager(
        backend=ExecutorBackend.THREAD,
        max_pools=2,
        min_pools=1,
        workers_per_pool=4,
        name_prefix="quickstart-worker",
    )

    await manager.start()

    try:
        async with await manager.acquire(owner="quickstart") as lease:
            result = await lease.run(blocking_uppercase, "hello leasepool")

        print("Result:", result)
    finally:
        await manager.stop()


if __name__ == "__main__":
    asyncio.run(main())
