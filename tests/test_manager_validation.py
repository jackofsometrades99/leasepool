from __future__ import annotations

import asyncio
import threading
import pytest

from leasepool import ExecutorBackend, LeasedExecutorManager, LeasePoolNotStartedError


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"max_pools": 0}, "max_pools must be > 0"),
        ({"max_pools": 1, "min_pools": 0}, "min_pools must be > 0"),
        ({"max_pools": 1, "units_per_pool": 0}, "units_per_pool must be > 0"),
        ({"max_pools": 1, "workers_per_pool": 0}, "workers_per_pool must be > 0"),
        ({"max_pools": 1, "min_pools": 2}, "min_pools cannot be greater"),
    ],
)
def test_constructor_validation(kwargs: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        LeasedExecutorManager(**kwargs)  # type: ignore[arg-type]


def test_invalid_backend_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported backend"):
        LeasedExecutorManager(backend="invalid", max_pools=1)


def test_backend_property_is_normalized() -> None:
    manager = LeasedExecutorManager(backend="THREAD", max_pools=1)

    assert manager.backend is ExecutorBackend.THREAD


@pytest.mark.asyncio
async def test_acquire_before_start_raises() -> None:
    manager = LeasedExecutorManager(max_pools=1)

    with pytest.raises(LeasePoolNotStartedError):
        await manager.acquire()


@pytest.mark.asyncio
async def test_stop_before_start_is_safe() -> None:
    manager = LeasedExecutorManager(max_pools=1)

    await manager.stop()

    assert manager.total_count == 0


@pytest.mark.asyncio
async def test_notify_scale_changed_before_start_is_safe() -> None:
    manager = LeasedExecutorManager(max_pools=1)

    manager.notify_scale_changed()

    assert manager.total_count == 0


@pytest.mark.asyncio
async def test_start_is_idempotent() -> None:
    manager = LeasedExecutorManager(max_pools=1, min_pools=1)

    try:
        await manager.start()
        await manager.start()

        assert manager.total_count == 1
        assert manager.available_count == 1
        assert manager.leased_count == 0
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_start_rejects_wrong_event_loop_after_started() -> None:
    manager = LeasedExecutorManager(max_pools=1, min_pools=1)

    await manager.start()

    errors: list[BaseException] = []

    def run_other_loop() -> None:
        async def call_start_from_wrong_loop() -> None:
            with pytest.raises(RuntimeError, match="owning event loop"):
                await manager.start()

        try:
            asyncio.run(call_start_from_wrong_loop())
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=run_other_loop)
    thread.start()
    thread.join(timeout=2.0)

    try:
        assert not thread.is_alive()
        assert errors == []
        assert manager.total_count == 1
        assert manager.available_count == 1
        assert manager.leased_count == 0
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_manager_can_restart_after_stop() -> None:
    manager = LeasedExecutorManager(max_pools=1, min_pools=1)

    await manager.start()
    await manager.stop()

    await manager.start()

    try:
        assert manager.total_count == 1
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_stats_contains_expected_fields() -> None:
    manager = LeasedExecutorManager(
        backend="thread",
        max_pools=3,
        min_pools=1,
        workers_per_pool=2,
    )

    await manager.start()

    try:
        stats = manager.stats()

        assert stats["backend"] == "thread"
        assert stats["desired"] == 1
        assert stats["max_pools"] == 3
        assert stats["min_pools"] == 1
        assert stats["available"] == 1
        assert stats["leased"] == 0
        assert stats["total"] == 1
        assert stats["workers_per_pool"] == 2
        assert stats["leases"] == []
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_bad_size_provider_falls_back_to_minimum() -> None:
    def broken_provider() -> int:
        raise RuntimeError("provider failed")

    manager = LeasedExecutorManager(
        max_pools=3,
        min_pools=1,
        size_provider=broken_provider,
    )

    await manager.start()

    try:
        assert manager.desired_executor_count() == 1
        assert manager.total_count == 1
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_stop_rejects_wrong_event_loop_without_changing_state() -> None:
    manager = LeasedExecutorManager(max_pools=1, min_pools=1)

    await manager.start()

    errors: list[BaseException] = []

    def run_other_loop() -> None:
        async def call_stop_from_wrong_loop() -> None:
            with pytest.raises(RuntimeError, match="owning event loop"):
                await manager.stop()

        try:
            asyncio.run(call_stop_from_wrong_loop())
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=run_other_loop)
    thread.start()
    thread.join(timeout=2.0)

    try:
        assert not thread.is_alive()
        assert errors == []

        # Proves the failed wrong-loop stop did not set _stopping=True
        # or clear the manager's executor state.
        assert manager.total_count == 1
        assert manager.available_count == 1
        assert manager.leased_count == 0

        lease = await manager.acquire(wait=False)
        await lease.release()

        assert manager.total_count == 1
        assert manager.available_count == 1
        assert manager.leased_count == 0
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_acquire_rejects_wrong_event_loop_without_waiting() -> None:
    manager = LeasedExecutorManager(max_pools=1, min_pools=1)

    await manager.start()
    lease = await manager.acquire(owner="owner-loop")

    errors: list[BaseException] = []

    def run_other_loop() -> None:
        async def call_acquire_from_wrong_loop() -> None:
            with pytest.raises(RuntimeError, match="owning event loop"):
                await manager.acquire(owner="wrong-loop", timeout=0.25)

        try:
            asyncio.run(call_acquire_from_wrong_loop())
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=run_other_loop)
    thread.start()
    thread.join(timeout=2.0)

    try:
        assert not thread.is_alive()
        assert errors == []

        # Proves the wrong-loop acquire did not create or steal a lease.
        assert manager.total_count == 1
        assert manager.available_count == 0
        assert manager.leased_count == 1
    finally:
        await lease.release()
        await manager.stop()


@pytest.mark.asyncio
async def test_acquire_wait_false_rejects_wrong_event_loop() -> None:
    manager = LeasedExecutorManager(max_pools=1, min_pools=1)

    await manager.start()

    errors: list[BaseException] = []

    def run_other_loop() -> None:
        async def call_acquire_from_wrong_loop() -> None:
            with pytest.raises(RuntimeError, match="owning event loop"):
                await manager.acquire(owner="wrong-loop", wait=False)

        try:
            asyncio.run(call_acquire_from_wrong_loop())
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=run_other_loop)
    thread.start()
    thread.join(timeout=2.0)

    try:
        assert not thread.is_alive()
        assert errors == []
        assert manager.total_count == 1
        assert manager.available_count == 1
        assert manager.leased_count == 0
    finally:
        await manager.stop()