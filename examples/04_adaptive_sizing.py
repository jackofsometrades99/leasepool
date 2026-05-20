"""
Adaptive sizing with `size_provider`.

The manager does not need to know what your units are. They can be connected
devices, tenants, queues, shards, customers, or anything else.

The desired pool count is:

    max(min_pools, ceil(size_provider() / units_per_pool))

capped by max_pools.
"""

from __future__ import annotations

import asyncio

from leasepool import LeasedExecutorManager


async def main() -> None:
    connected_devices: set[str] = set()

    manager = LeasedExecutorManager(
        backend="thread",
        max_pools=5,
        min_pools=1,
        units_per_pool=10,
        size_provider=lambda: len(connected_devices),
        check_interval=60,
        workers_per_pool=2,
    )

    await manager.start()

    try:
        print("Initial desired:", manager.desired_executor_count())
        print("Initial total:", manager.total_count)

        for i in range(31):
            connected_devices.add(f"device-{i}")

        # Wake the checker immediately instead of waiting for check_interval.
        manager.notify_scale_changed()

        await asyncio.sleep(0.1)

        print("After adding 31 devices:")
        print("  desired:", manager.desired_executor_count())
        print("  total:", manager.total_count)

        connected_devices.clear()
        manager.notify_scale_changed()

        await asyncio.sleep(0.1)

        print("After removing all devices:")
        print("  desired:", manager.desired_executor_count())
        print("  total:", manager.total_count)

    finally:
        await manager.stop()


if __name__ == "__main__":
    asyncio.run(main())
