"""
Reading manager state.

Use these for dashboards, logs, health endpoints, or debugging.
"""

from __future__ import annotations

import asyncio
from pprint import pprint

from leasepool import LeasedExecutorManager


async def main() -> None:
    manager = LeasedExecutorManager(
        backend="thread",
        max_pools=2,
        min_pools=1,
        workers_per_pool=3,
    )

    await manager.start()

    try:
        print("Backend:", manager.backend)
        print("Desired executor count:", manager.desired_executor_count())
        print("Available count:", manager.available_count)
        print("Leased count:", manager.leased_count)
        print("Total count:", manager.total_count)

        lease = await manager.acquire(owner="stats-demo", lease_seconds=30)

        try:
            print("\nAfter acquiring one lease:")
            print("Available count:", manager.available_count)
            print("Leased count:", manager.leased_count)
            print("Total count:", manager.total_count)

            print("\nFull stats:")
            pprint(manager.stats())

        finally:
            await lease.release()

        print("\nAfter release:")
        pprint(manager.stats())

    finally:
        await manager.stop()


if __name__ == "__main__":
    asyncio.run(main())
