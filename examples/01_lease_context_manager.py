"""
Using ExecutorLease as an async context manager.

This is the safest default style. The lease is automatically returned even if
your work raises an exception.
"""

from __future__ import annotations

import asyncio
import time

from leasepool import LeasedExecutorManager


def blocking_add(left: int, right: int) -> int:
    time.sleep(0.1)
    return left + right


def blocking_join(*, first: str, second: str) -> str:
    time.sleep(0.1)
    return f"{first}-{second}"


async def main() -> None:
    manager = LeasedExecutorManager(
        backend="thread",
        max_pools=1,
        min_pools=1,
        workers_per_pool=2,
    )

    await manager.start()

    try:
        print("Before acquire:", manager.stats())

        async with await manager.acquire(owner="context-manager-example") as lease:
            print("Lease ID:", lease.lease_id)
            print("Owner:", lease.owner)
            print("Soft expires at monotonic timestamp:", lease.soft_expires_at)
            print("Hard expires at monotonic timestamp:", lease.hard_expires_at)

            number_result = await lease.run(blocking_add, 20, 22)
            keyword_result = await lease.run(
                blocking_join,
                first="hello",
                second="world",
            )

            print("Number result:", number_result)
            print("Keyword result:", keyword_result)
            print("During lease:", manager.stats())

        print("After context exits:", manager.stats())

    finally:
        await manager.stop()


if __name__ == "__main__":
    asyncio.run(main())
