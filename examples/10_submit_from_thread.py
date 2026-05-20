"""
Submitting work to WorkGrinder from another OS thread.

Use `submit_from_thread()` only from non-async code or another thread. It returns
a `concurrent.futures.Future`.
"""

from __future__ import annotations

import asyncio
import threading
import time

from leasepool import LeasedExecutorManager, WorkGrinder


def blocking_add(left: int, right: int) -> int:
    time.sleep(0.05)
    return left + right


def thread_entrypoint(grinder: WorkGrinder) -> None:
    future = grinder.submit_from_thread(
        blocking_add,
        20,
        22,
        owner="external-thread",
    )

    print("Worker thread got result:", future.result(timeout=5))


async def main() -> None:
    manager = LeasedExecutorManager(
        backend="thread",
        max_pools=1,
        min_pools=1,
        workers_per_pool=2,
    )
    grinder = WorkGrinder(
        executor_manager=manager,
        batch_size_threshold=1,
        max_wait_seconds=1.0,
    )

    await manager.start()
    await grinder.start()

    try:
        thread = threading.Thread(
            target=thread_entrypoint,
            args=(grinder,),
            name="external-submitter",
        )
        thread.start()

        while thread.is_alive():
            await asyncio.sleep(0.05)

        thread.join()

    finally:
        await grinder.stop(cancel_pending=True)
        await manager.stop()


if __name__ == "__main__":
    asyncio.run(main())
