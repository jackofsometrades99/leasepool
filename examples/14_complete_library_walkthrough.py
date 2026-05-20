"""
Complete leasepool usage walkthrough.

This example combines the APIs most applications use together:

- manager lifecycle
- adaptive sizing
- explicit owner labels
- context-managed leases
- WorkGrinder batching
- manager and grinder diagnostics
- clean shutdown order
"""

from __future__ import annotations

import asyncio
import time
from pprint import pprint

from leasepool import LeasedExecutorManager, WorkGrinder


def blocking_vendor_lookup(device_id: str) -> dict[str, str]:
    time.sleep(0.05)
    return {"device_id": device_id, "status": "ok"}


def blocking_score(value: int) -> int:
    time.sleep(0.02)
    return value * value


async def main() -> None:
    connected_devices: set[str] = {"device-1", "device-2"}

    manager = LeasedExecutorManager(
        backend="thread",
        max_pools=3,
        min_pools=1,
        units_per_pool=2,
        size_provider=lambda: len(connected_devices),
        workers_per_pool=4,
        default_lease_seconds=60.0,
        lease_grace_seconds=5.0,
        name_prefix="walkthrough-worker",
    )
    grinder = WorkGrinder(
        executor_manager=manager,
        batch_size_threshold=4,
        max_wait_seconds=0.5,
        lease_seconds=30.0,
        owner_prefix="walkthrough-grinder",
    )

    await manager.start()
    await grinder.start()

    try:
        print("Initial manager stats:")
        pprint(manager.stats())

        # Adaptive sizing: update your signal and wake the checker immediately.
        connected_devices.update({"device-3", "device-4", "device-5"})
        manager.notify_scale_changed()
        await asyncio.sleep(0.05)

        print("\nAfter adaptive signal changed:")
        pprint(manager.stats())

        # Direct lease: best for one request or one coordinated group of calls.
        async with await manager.acquire(owner="device-status:device-1") as lease:
            status = await lease.run(blocking_vendor_lookup, "device-1")

        print("\nDirect lease result:", status)

        # Grinder: best for many small pieces of sync work submitted by callers.
        scores = await asyncio.gather(
            *(
                grinder.submit(blocking_score, value, owner=f"score:{value}")
                for value in range(8)
            )
        )

        print("\nGrinder scores:", scores)
        print("\nGrinder stats:")
        pprint(grinder.stats())
        print("\nFinal manager stats:")
        pprint(manager.stats())

    finally:
        # Stop producers/batchers before shutting down the manager they depend on.
        await grinder.stop(cancel_pending=True)
        await manager.stop()


if __name__ == "__main__":
    asyncio.run(main())
