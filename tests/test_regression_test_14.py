# Test 14: WorkGrinder.enqueue() rejects calls from the wrong event loop

import asyncio
import threading

import pytest

from leasepool import LeasedExecutorManager, WorkGrinder


def noop() -> str:
    return "ok"


@pytest.mark.asyncio
async def test_work_grinder_enqueue_rejects_wrong_event_loop() -> None:
    manager = LeasedExecutorManager(max_pools=1)
    await manager.start()

    grinder = WorkGrinder(executor_manager=manager)
    await grinder.start()

    errors: list[BaseException] = []

    def run_other_loop() -> None:
        async def call_from_wrong_loop() -> None:
            with pytest.raises(RuntimeError):
                await grinder.enqueue(noop)

        try:
            asyncio.run(call_from_wrong_loop())
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=run_other_loop)
    thread.start()
    thread.join(timeout=2.0)

    try:
        assert not errors
    finally:
        await grinder.stop(cancel_pending=True)
        await manager.stop()