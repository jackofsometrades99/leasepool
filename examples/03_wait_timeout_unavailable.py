"""
Acquire behavior when all executor pools are already leased.

This demonstrates:

- `wait=False`
- `timeout=...`
- waiting until another lease is released
"""

from __future__ import annotations

import asyncio

from leasepool import LeasedExecutorManager, LeaseUnavailableError


async def main() -> None:
    manager = LeasedExecutorManager(
        backend="thread",
        max_pools=1,
        min_pools=1,
        workers_per_pool=1,
    )

    await manager.start()

    try:
        first = await manager.acquire(owner="first-holder")

        print("After first acquire:")
        print("  available:", manager.available_count)
        print("  leased:", manager.leased_count)
        print("  total:", manager.total_count)

        try:
            await manager.acquire(owner="no-wait", wait=False)
        except LeaseUnavailableError as exc:
            print("wait=False failed immediately:", exc)

        try:
            await manager.acquire(owner="short-timeout", timeout=0.1)
        except TimeoutError as exc:
            print("timeout failed as expected:", exc)

        async def delayed_release() -> None:
            await asyncio.sleep(0.2)
            await first.release()
            print("first lease released")

        release_task = asyncio.create_task(delayed_release())

        second = await manager.acquire(owner="waits-until-release", timeout=1)

        try:
            print("Second lease acquired after first was released.")
            print("Second lease owner:", second.owner)
        finally:
            await second.release()

        await release_task

    finally:
        await manager.stop()


if __name__ == "__main__":
    asyncio.run(main())
