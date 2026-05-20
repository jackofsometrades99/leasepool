"""
Forward logs emitted by ProcessPoolExecutor workers.

Normal leasepool logs are emitted by the parent process. Logs created inside a
process worker need an explicit queue bridge. Use ProcessLoggingConfig when you
want the parent application logger to receive worker log records.

Run this file directly:

    python examples/13_process_log_forwarding.py
"""

from __future__ import annotations

import asyncio
import logging

from leasepool import LeasedExecutorManager, ProcessLoggingConfig


LOGGER_NAME = "leasepool.examples.process.worker"


def logged_cpu_work(value: int) -> int:
    logger = logging.getLogger(LOGGER_NAME)
    logger.info("worker received value=%s", value)

    total = 0
    for item in range(value):
        total += item * item

    logger.info("worker finished value=%s", value)
    return total


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(processName)s %(name)s %(levelname)s: %(message)s",
    )

    parent_logger = logging.getLogger("leasepool.examples.process.parent")

    manager = LeasedExecutorManager(
        backend="process",
        max_pools=1,
        min_pools=1,
        workers_per_pool=2,
        process_logging=ProcessLoggingConfig(
            enabled=True,
            level="INFO",
            target_logger=parent_logger,
        ),
    )

    await manager.start()

    try:
        async with await manager.acquire(owner="process-log-demo") as lease:
            first, second = await asyncio.gather(
                lease.run(logged_cpu_work, 10_000),
                lease.run(logged_cpu_work, 12_000),
            )

        print("Results:", first, second)
    finally:
        await manager.stop()


if __name__ == "__main__":
    asyncio.run(main())
