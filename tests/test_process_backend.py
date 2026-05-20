from __future__ import annotations

import asyncio

import pytest

from helpers import count_primes, multiply, with_kwargs
from leasepool import ExecutorBackend, LeasedExecutorManager, WorkGrinder


@pytest.mark.asyncio
async def test_process_backend_runs_picklable_function() -> None:
    manager = LeasedExecutorManager(
        backend=ExecutorBackend.PROCESS,
        max_pools=1,
        min_pools=1,
        workers_per_pool=2,
    )

    await manager.start()

    try:
        async with await manager.acquire(owner="process-test") as lease:
            assert await lease.run(multiply, 6, 7) == 42
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_process_backend_supports_picklable_kwargs() -> None:
    manager = LeasedExecutorManager(
        backend="process",
        max_pools=1,
        min_pools=1,
        workers_per_pool=2,
    )

    await manager.start()

    try:
        async with await manager.acquire(owner="process-kwargs") as lease:
            assert await lease.run(with_kwargs, left=20, right=22) == 42
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_process_backend_can_parallelize_cpu_work() -> None:
    manager = LeasedExecutorManager(
        backend="process",
        max_pools=1,
        min_pools=1,
        workers_per_pool=2,
    )

    await manager.start()

    try:
        async with await manager.acquire(owner="cpu") as lease:
            first, second = await asyncio.gather(
                lease.run(count_primes, 5_000),
                lease.run(count_primes, 5_500),
            )

        assert first > 0
        assert second >= first
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_process_backend_rejects_non_picklable_lambda() -> None:
    manager = LeasedExecutorManager(
        backend="process",
        max_pools=1,
        min_pools=1,
        workers_per_pool=1,
    )

    await manager.start()

    try:
        async with await manager.acquire(owner="non-picklable") as lease:
            with pytest.raises(Exception):
                await lease.run(lambda value: value * 2, 21)  # noqa: E731
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_work_grinder_with_process_backend() -> None:
    manager = LeasedExecutorManager(
        backend="process",
        max_pools=1,
        min_pools=1,
        workers_per_pool=2,
    )
    grinder = WorkGrinder(
        executor_manager=manager,
        max_wait_seconds=1,
        batch_size_threshold=2,
    )

    await manager.start()
    await grinder.start()

    try:
        results = await asyncio.gather(
            grinder.submit(multiply, 6, 7),
            grinder.submit(multiply, 3, 14),
        )

        assert results == [42, 42]
    finally:
        await grinder.stop(cancel_pending=True)
        await manager.stop()


@pytest.mark.asyncio
async def test_process_backend_can_forward_worker_logs(caplog: pytest.LogCaptureFixture) -> None:
    import logging

    from helpers import log_and_multiply, wait_until

    target_logger = logging.getLogger("test.leasepool.process")
    caplog.set_level(logging.INFO, logger=target_logger.name)

    manager = LeasedExecutorManager(
        backend="process",
        max_pools=1,
        min_pools=1,
        workers_per_pool=1,
        forward_process_logs=True,
        process_log_target_logger=target_logger,
    )

    await manager.start()

    try:
        async with await manager.acquire(owner="process-log-test") as lease:
            assert await lease.run(log_and_multiply, "worker.example", 6, 7) == 42

        await wait_until(lambda: "worker multiplying 6 x 7" in caplog.text)
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_process_log_forwarding_composes_user_initializer(
    caplog: pytest.LogCaptureFixture,
) -> None:
    import logging

    from helpers import log_and_multiply, wait_until, worker_initializer_logs

    target_logger = logging.getLogger("test.leasepool.process.initializer")
    caplog.set_level(logging.INFO, logger=target_logger.name)

    manager = LeasedExecutorManager(
        backend="process",
        max_pools=1,
        min_pools=1,
        workers_per_pool=1,
        forward_process_logs=True,
        process_log_target_logger=target_logger,
        initializer=worker_initializer_logs,
        initargs=("worker.initializer", "initializer ran"),
    )

    await manager.start()

    try:
        async with await manager.acquire(owner="process-log-init-test") as lease:
            assert await lease.run(log_and_multiply, "worker.example", 3, 14) == 42

        await wait_until(lambda: "initializer ran" in caplog.text)
        await wait_until(lambda: "worker multiplying 3 x 14" in caplog.text)
    finally:
        await manager.stop()
