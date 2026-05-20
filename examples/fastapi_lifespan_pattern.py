"""
FastAPI integration pattern.

This file requires FastAPI if you want to run it:

    pip install fastapi uvicorn

Run:

    uvicorn examples.fastapi_lifespan_pattern:app --reload

The important idea:
- create the manager during lifespan startup
- store it on app.state
- stop it during lifespan shutdown
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from leasepool import LeasedExecutorManager


def blocking_vendor_sdk_call(device_id: str) -> dict[str, str]:
    time.sleep(0.2)
    return {"device_id": device_id, "status": "ok"}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    manager = LeasedExecutorManager(
        backend="thread",
        max_pools=4,
        min_pools=1,
        workers_per_pool=4,
        name_prefix="fastapi-blocking-worker",
    )

    await manager.start()

    app.state.executor_manager = manager

    try:
        yield
    finally:
        await manager.stop()


app = FastAPI(lifespan=lifespan)


@app.get("/devices/{device_id}/status")
async def get_device_status(device_id: str) -> dict[str, str]:
    manager: LeasedExecutorManager = app.state.executor_manager

    async with await manager.acquire(owner=f"device-status:{device_id}") as lease:
        return await lease.run(blocking_vendor_sdk_call, device_id)


@app.get("/executor/stats")
async def executor_stats() -> dict:
    manager: LeasedExecutorManager = app.state.executor_manager
    return manager.stats()
