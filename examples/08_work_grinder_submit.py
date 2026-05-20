"""
WorkGrinder with `submit()`.

`submit()` queues work and waits for the result.

The grinder processes a batch when either:

- pending count reaches batch_size_threshold
- the oldest pending item waits max_wait_seconds
"""

from __future__ import annotations

import asyncio
import time

from leasepool import LeasedExecutorManager, WorkGrinder


def blocking_square(value: int) -> int:
    time.sleep(0.05)
    return value * value


async def main() -> None:
    manager = LeasedExecutorManager(
        backend="thread",
        max_pools=1,
        min_pools=1,
        workers_per_pool=4,
    )
    grinder = WorkGrinder(
        executor_manager=manager,
        batch_size_threshold=10,
        max_wait_seconds=1.0,
        lease_seconds=30.0,
        owner_prefix="square-grinder",
    )

    await manager.start()
    await grinder.start()

    try:
        results = await asyncio.gather(
            *(grinder.submit(blocking_square, i, owner=f"item-{i}") for i in range(20))
        )

        print("Results:", results)
        print("Grinder stats:", grinder.stats())

    finally:
        await grinder.stop(cancel_pending=True)
        await manager.stop()


if __name__ == "__main__":
    asyncio.run(main())
