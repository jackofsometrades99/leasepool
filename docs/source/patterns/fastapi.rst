FastAPI pattern
===============

Create the manager during application startup and stop it during shutdown.

.. code-block:: python

   import time
   from contextlib import asynccontextmanager
   from typing import AsyncIterator

   from fastapi import FastAPI

   from leasepool import LeasedExecutorManager


   def blocking_vendor_call(device_id: str) -> dict[str, str]:
       time.sleep(0.2)
       return {"device_id": device_id, "status": "ok"}


   @asynccontextmanager
   async def lifespan(app: FastAPI) -> AsyncIterator[None]:
       manager = LeasedExecutorManager(
           backend="thread",
           max_pools=4,
           min_pools=1,
           workers_per_pool=4,
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

       async with await manager.acquire(owner=f"device:{device_id}") as lease:
           return await lease.run(blocking_vendor_call, device_id)
