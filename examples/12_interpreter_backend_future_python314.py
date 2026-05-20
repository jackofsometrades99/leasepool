"""
Future Python 3.14+ InterpreterPoolExecutor backend.

On Python 3.11, this example should raise UnsupportedBackendError.

The point is to show that the public API does not need to change later. Once
Python 3.14+ is available, the same LeasedExecutorManager can use:

    backend="interpreter"

for CPU-bound work with isolated interpreters.
"""

from __future__ import annotations

import asyncio

from leasepool import LeasedExecutorManager, UnsupportedBackendError


def pure_cpu_function(value: int) -> int:
    total = 0
    for i in range(value):
        total += i * i
    return total


async def main() -> None:
    manager = LeasedExecutorManager(
        backend="interpreter",
        max_pools=1,
        min_pools=1,
        workers_per_pool=4,
    )

    try:
        await manager.start()
    except UnsupportedBackendError as exc:
        print("Interpreter backend is not available on this Python version:")
        print(exc)
        return

    try:
        async with await manager.acquire(owner="future-interpreter-demo") as lease:
            result = await lease.run(pure_cpu_function, 100_000)

        print("Result:", result)

    finally:
        await manager.stop()


if __name__ == "__main__":
    asyncio.run(main())
