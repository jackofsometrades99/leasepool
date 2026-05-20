"""
Lease expiry and revocation.

A lease has:

- soft expiry: lease_seconds
- hard expiry: lease_seconds + lease_grace_seconds

After hard expiry, new submissions through that lease are rejected.
"""

from __future__ import annotations

import asyncio

from leasepool import LeasedExecutorManager, LeaseExpiredError


def echo(value: str) -> str:
    return value


async def main() -> None:
    manager = LeasedExecutorManager(
        backend="thread",
        max_pools=1,
        min_pools=1,
        workers_per_pool=1,
        lease_grace_seconds=0.1,
        check_interval=60,
    )

    await manager.start()

    try:
        lease = await manager.acquire(
            owner="expiry-demo",
            lease_seconds=0.1,
        )

        print("Lease ID:", lease.lease_id)
        print("Soft expires at:", lease.soft_expires_at)
        print("Hard expires at:", lease.hard_expires_at)

        print("Before expiry:", await lease.run(echo, "ok"))

        await asyncio.sleep(0.25)

        try:
            lease.executor.submit(echo, "too late")
        except LeaseExpiredError as exc:
            print("Submit after hard expiry was rejected:", exc)

        print("Manager stats after expiry handling:", manager.stats())

    finally:
        await manager.stop()


if __name__ == "__main__":
    asyncio.run(main())
