"""
Common error handling patterns.

This example demonstrates the library exceptions users are most likely to handle.
"""

from __future__ import annotations

import asyncio

from leasepool import (
    LeasedExecutorManager,
    LeaseExpiredError,
    LeasePoolNotStartedError,
    LeaseUnavailableError,
)


def echo(value: str) -> str:
    return value


async def main() -> None:
    manager = LeasedExecutorManager(
        backend="thread",
        max_pools=1,
        min_pools=1,
        lease_grace_seconds=0.05,
    )

    try:
        await manager.acquire()
    except LeasePoolNotStartedError as exc:
        print("Acquire before start failed:", exc)

    await manager.start()

    try:
        first = await manager.acquire(owner="first")

        try:
            await manager.acquire(owner="second", wait=False)
        except LeaseUnavailableError as exc:
            print("No lease available:", exc)

        await first.release()

        expiring = await manager.acquire(owner="expiring", lease_seconds=0.05)
        executor = expiring.executor

        await asyncio.sleep(0.15)

        try:
            executor.submit(echo, "too late")
        except LeaseExpiredError as exc:
            print("Lease expired:", exc)

    finally:
        await manager.stop()


if __name__ == "__main__":
    asyncio.run(main())
