Core concepts
=============

Executor backend
----------------

A backend is the executor implementation used internally.

``thread``
   Uses ``concurrent.futures.ThreadPoolExecutor``. Best for blocking I/O, file
   operations, and legacy synchronous libraries.

``process``
   Uses ``concurrent.futures.ProcessPoolExecutor``. Best for CPU-heavy Python
   code on Python 3.11+ when functions and data are picklable.

``interpreter``
   Reserved for Python 3.14+ ``InterpreterPoolExecutor`` support. On earlier
   versions, selecting it raises ``UnsupportedBackendError``.

Executor pool
-------------

A pool is one executor object owned by a manager.

.. code-block:: python

   LeasedExecutorManager(
       backend="thread",
       max_pools=2,
       workers_per_pool=4,
   )

means:

* up to 2 executor objects;
* each executor can have up to 4 workers;
* up to 8 worker threads total for that manager.

``max_pools`` is per manager, not global across all managers in your process.

Lease
-----

A lease is temporary permission to submit work to one executor.

A lease has:

``lease_id``
   Unique lease identifier.

``owner``
   Optional human-readable label used in logs and diagnostics.

``lease_seconds``
   Soft lifetime requested for the lease.

``grace_seconds``
   Extra time after soft expiry before hard revocation.

``soft_expires_at``
   Monotonic timestamp when the lease enters the grace period.

``hard_expires_at``
   Monotonic timestamp after which new submissions are rejected.

Safe executor proxy
-------------------

Users receive a proxy executor, not the raw executor. The proxy prevents callers
from shutting down internal executors directly and rejects new submissions after
a lease has been released or revoked.

Use either:

.. code-block:: python

   result = await lease.run(sync_function, payload)

or, when you specifically need a ``concurrent.futures.Future``:

.. code-block:: python

   future = lease.executor.submit(sync_function, payload)
   result = future.result(timeout=1)

Backpressure
------------

When all pools are leased and the manager has reached ``max_pools``, acquiring a
lease waits by default. You can set ``timeout`` or ``wait=False`` to control this
behavior.

.. code-block:: python

   lease = await manager.acquire(owner="bounded-request", timeout=2.0)

.. code-block:: python

   lease = await manager.acquire(owner="fail-fast", wait=False)

Adaptive sizing
---------------

A manager can grow and shrink idle pools based on a runtime signal returned by
``size_provider``. The target is:

.. code-block:: text

   max(min_pools, ceil(size_provider() / units_per_pool))

capped by ``max_pools``.

Call ``manager.notify_scale_changed()`` when the signal changes and you want the
checker to wake immediately.

WorkGrinder
-----------

``WorkGrinder`` batches many async callers into executor batches. It starts a
batch when either:

* pending work reaches ``batch_size_threshold``;
* the oldest item has waited ``max_wait_seconds``.

Use it when many callers produce small synchronous jobs and you want a single
component to manage batching, leasing, and completion.

Process log forwarding
----------------------

Logs emitted inside ``ProcessPoolExecutor`` workers are produced in child
processes. Enable ``ProcessLoggingConfig`` or ``forward_process_logs=True`` when
you want those log records forwarded through a logger in the parent process.
