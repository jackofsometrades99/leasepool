"""
Manual acquire/release.

Use this style when your control flow cannot easily fit inside an async context
manager. Prefer the context manager style when possible.
"""

from __future__ import annotations

import asyncio
import time

from leasepool import LeasedExecutorManager


def blocking_double(value: int) -> int:
    time.sleep(0.1)
    return value * 2


async def main() -> None:
    manager = LeasedExecutorManager(
        backend="thread",
        max_pools=1,
        min_pools=1,
        workers_per_pool=2,
    )

    await manager.start()

    lease = None

    try:
        lease = await manager.acquire(owner="manual-example")

        # Option 1: high-level async helper.
        result = await lease.run(blocking_double, 21)
        print("lease.run result:", result)

        # Option 2: direct executor submit through the safe proxy.
        future = lease.executor.submit(blocking_double, 10)
        print("lease.executor.submit result:", future.result(timeout=1))

        print("Counts before manual release:")
        print("  available:", manager.available_count)
        print("  leased:", manager.leased_count)
        print("  total:", manager.total_count)

    finally:
        if lease is not None:
            # This calls manager.release(lease.lease_id) internally.
            await lease.release()

        print("Counts after manual release:")
        print("  available:", manager.available_count)
        print("  leased:", manager.leased_count)
        print("  total:", manager.total_count)

        await manager.stop()


if __name__ == "__main__":
    asyncio.run(main())
