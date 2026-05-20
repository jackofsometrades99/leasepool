from __future__ import annotations

import asyncio

import pytest

from helpers import (
    add,
    blocking_sleep_return,
    identity,
    raise_value_error,
    wait_until,
    with_kwargs,
)
from leasepool import LeasedExecutorManager, LeaseExpiredError, LeaseUnavailableError


@pytest.mark.asyncio
async def test_lease_run_returns_result() -> None:
    manager = LeasedExecutorManager(max_pools=1, min_pools=1, workers_per_pool=2)
    await manager.start()

    try:
        async with await manager.acquire(owner="test") as lease:
            assert await lease.run(add, 20, 22) == 42
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_lease_run_supports_keyword_arguments() -> None:
    manager = LeasedExecutorManager(max_pools=1, min_pools=1, workers_per_pool=2)
    await manager.start()

    try:
        async with await manager.acquire(owner="kwargs") as lease:
            assert await lease.run(with_kwargs, left=40, right=2) == 42
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_lease_run_propagates_callable_exception() -> None:
    manager = LeasedExecutorManager(max_pools=1, min_pools=1)
    await manager.start()

    try:
        async with await manager.acquire(owner="exception") as lease:
            with pytest.raises(ValueError, match="custom boom"):
                await lease.run(raise_value_error, "custom boom")
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_context_manager_releases_on_success() -> None:
    manager = LeasedExecutorManager(max_pools=1, min_pools=1)
    await manager.start()

    try:
        async with await manager.acquire(owner="ctx"):
            assert manager.leased_count == 1
            assert manager.available_count == 0

        assert manager.leased_count == 0
        assert manager.available_count == 1
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_context_manager_releases_on_exception() -> None:
    manager = LeasedExecutorManager(max_pools=1, min_pools=1)
    await manager.start()

    try:
        with pytest.raises(RuntimeError, match="inside"):
            async with await manager.acquire(owner="ctx-error"):
                raise RuntimeError("inside")

        assert manager.leased_count == 0
        assert manager.available_count == 1
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_release_is_idempotent() -> None:
    manager = LeasedExecutorManager(max_pools=1, min_pools=1)
    await manager.start()

    try:
        lease = await manager.acquire(owner="idempotent")

        await lease.release()
        await lease.release()

        assert manager.leased_count == 0
        assert manager.available_count == 1
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_release_unknown_lease_id_is_noop() -> None:
    manager = LeasedExecutorManager(max_pools=1, min_pools=1)
    await manager.start()

    try:
        await manager.release("does-not-exist")

        assert manager.total_count == 1
        assert manager.available_count == 1
        assert manager.leased_count == 0
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_proxy_rejects_direct_shutdown() -> None:
    manager = LeasedExecutorManager(max_pools=1, min_pools=1)
    await manager.start()

    try:
        async with await manager.acquire(owner="proxy") as lease:
            with pytest.raises(RuntimeError, match="Do not shut down"):
                lease.executor.shutdown()
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_proxy_rejects_submit_after_release() -> None:
    manager = LeasedExecutorManager(max_pools=1, min_pools=1)
    await manager.start()

    try:
        lease = await manager.acquire(owner="after-release")
        executor = lease.executor

        await lease.release()

        with pytest.raises(LeaseExpiredError, match="no longer active"):
            executor.submit(identity, 1)
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_wait_false_raises_when_all_pools_are_leased() -> None:
    manager = LeasedExecutorManager(max_pools=1, min_pools=1)
    await manager.start()

    try:
        lease = await manager.acquire(owner="first")

        try:
            with pytest.raises(LeaseUnavailableError, match="No executor available"):
                await manager.acquire(owner="second", wait=False)
        finally:
            await lease.release()
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_wait_true_waits_until_release() -> None:
    manager = LeasedExecutorManager(max_pools=1, min_pools=1)
    await manager.start()

    try:
        first = await manager.acquire(owner="first")

        acquire_task = asyncio.create_task(
            manager.acquire(owner="second", wait=True, timeout=1)
        )

        await asyncio.sleep(0.05)

        assert not acquire_task.done()

        await first.release()

        second = await acquire_task

        try:
            assert second.owner == "second"
            assert manager.leased_count == 1
        finally:
            await second.release()
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_acquire_timeout_when_no_pool_becomes_available() -> None:
    manager = LeasedExecutorManager(max_pools=1, min_pools=1)
    await manager.start()

    try:
        lease = await manager.acquire(owner="held")

        try:
            with pytest.raises(TimeoutError, match="Timed out waiting"):
                await manager.acquire(owner="timeout", wait=True, timeout=0.05)
        finally:
            await lease.release()
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_expired_lease_is_revoked_on_next_submit() -> None:
    manager = LeasedExecutorManager(
        max_pools=1,
        min_pools=1,
        lease_grace_seconds=0.01,
        check_interval=60,
    )
    await manager.start()

    try:
        lease = await manager.acquire(owner="expires", lease_seconds=0.01)
        executor = lease.executor

        await asyncio.sleep(0.05)

        with pytest.raises(LeaseExpiredError, match="expired|no longer active"):
            executor.submit(identity, 1)

        assert manager.leased_count == 0
        assert manager.total_count == 1
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_checker_revokes_expired_lease_without_submit() -> None:
    manager = LeasedExecutorManager(
        max_pools=1,
        min_pools=1,
        lease_grace_seconds=0.01,
        check_interval=0.01,
    )
    await manager.start()

    try:
        await manager.acquire(owner="checker-expiry", lease_seconds=0.01)

        await wait_until(
            lambda: manager.leased_count == 0 and manager.available_count == 1
        )
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_stats_includes_active_lease_expiry_information() -> None:
    manager = LeasedExecutorManager(max_pools=1, min_pools=1)
    await manager.start()

    try:
        lease = await manager.acquire(owner="stats-owner", lease_seconds=10)

        try:
            stats = manager.stats()

            assert stats["leased"] == 1
            assert len(stats["leases"]) == 1

            lease_stats = stats["leases"][0]

            assert lease_stats["lease_id"] == lease.lease_id
            assert lease_stats["owner"] == "stats-owner"
            assert lease_stats["seconds_until_soft_expiry"] > 0
            assert lease_stats["seconds_until_hard_expiry"] > 0
        finally:
            await lease.release()
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_adaptive_sizing_grows_when_size_provider_increases() -> None:
    units = {"count": 0}

    manager = LeasedExecutorManager(
        max_pools=5,
        min_pools=1,
        units_per_pool=10,
        size_provider=lambda: units["count"],
        check_interval=60,
    )
    await manager.start()

    try:
        assert manager.total_count == 1

        units["count"] = 31
        manager.notify_scale_changed()

        await wait_until(lambda: manager.desired_executor_count() == 4)
        await wait_until(lambda: manager.total_count == 4)
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_adaptive_sizing_shrinks_idle_executors_when_size_provider_decreases() -> None:
    units = {"count": 41}

    manager = LeasedExecutorManager(
        max_pools=5,
        min_pools=1,
        units_per_pool=10,
        size_provider=lambda: units["count"],
        check_interval=60,
    )
    await manager.start()

    try:
        assert manager.total_count == 5

        units["count"] = 0
        manager.notify_scale_changed()

        await wait_until(lambda: manager.desired_executor_count() == 1)
        await wait_until(lambda: manager.total_count == 1)
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_adaptive_sizing_does_not_revoke_non_expired_leased_executor_when_shrinking() -> None:
    units = {"count": 30}

    manager = LeasedExecutorManager(
        max_pools=5,
        min_pools=1,
        units_per_pool=10,
        size_provider=lambda: units["count"],
        check_interval=60,
    )
    await manager.start()

    try:
        assert manager.total_count == 3

        lease = await manager.acquire(owner="held-during-shrink")

        units["count"] = 0
        manager.notify_scale_changed()

        await wait_until(lambda: manager.desired_executor_count() == 1)
        await wait_until(lambda: manager.total_count == 1)

        assert manager.leased_count == 1
        assert await lease.run(identity, "still alive") == "still alive"

        await lease.release()

        assert manager.total_count == 1
        assert manager.available_count == 1
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_max_pools_is_per_manager_not_global() -> None:
    manager_a = LeasedExecutorManager(max_pools=1, min_pools=1, name_prefix="a")
    manager_b = LeasedExecutorManager(max_pools=1, min_pools=1, name_prefix="b")

    await manager_a.start()
    await manager_b.start()

    try:
        lease_a = await manager_a.acquire(owner="a")
        lease_b = await manager_b.acquire(owner="b")

        try:
            assert manager_a.leased_count == 1
            assert manager_b.leased_count == 1
        finally:
            await lease_a.release()
            await lease_b.release()
    finally:
        await manager_b.stop()
        await manager_a.stop()


@pytest.mark.asyncio
async def test_running_task_can_finish_even_if_lease_is_released_after_submission() -> None:
    manager = LeasedExecutorManager(max_pools=1, min_pools=1, workers_per_pool=1)
    await manager.start()

    try:
        lease = await manager.acquire(owner="submitted-task")
        future = lease.executor.submit(blocking_sleep_return, 0.05, "done")

        await lease.release()

        assert future.result(timeout=1) == "done"
    finally:
        await manager.stop()
