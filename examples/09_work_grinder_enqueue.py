"""
WorkGrinder with `enqueue()`.

`enqueue()` returns an asyncio.Future immediately. This is useful when you want
to queue work first and await it later.
"""

from __future__ import annotations

import asyncio
import time

from leasepool import LeasedExecutorManager, WorkGrinder


def blocking_format(value: int) -> str:
    time.sleep(0.05)
    return f"value={value}"


async def main() -> None:
    manager = LeasedExecutorManager(
        backend="thread",
        max_pools=1,
        min_pools=1,
        workers_per_pool=4,
    )
    grinder = WorkGrinder(
        executor_manager=manager,
        batch_size_threshold=5,
        max_wait_seconds=1.0,
        lease_seconds=30.0,
    )

    await manager.start()
    await grinder.start()

    try:
        futures = []

        for i in range(5):
            future = await grinder.enqueue(blocking_format, i, owner=f"format-{i}")
            futures.append(future)

        print("Queued futures:", len(futures))
        print("Stats after enqueue:", grinder.stats())

        results = await asyncio.gather(*futures)

        print("Results:", results)
        print("Stats after completion:", grinder.stats())

    finally:
        await grinder.stop(cancel_pending=True)
        await manager.stop()


if __name__ == "__main__":
    asyncio.run(main())
