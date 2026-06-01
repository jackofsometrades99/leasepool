Configuration
=============

LeasedExecutorManager
---------------------

.. code-block:: python

   manager = LeasedExecutorManager(
       backend="thread",
       max_pools=4,
       min_pools=1,
       units_per_pool=10,
       size_provider=lambda: len(connected_devices),
       check_interval=120.0,
       default_lease_seconds=300.0,
       lease_grace_seconds=15.0,
       workers_per_pool=4,
       name_prefix="leasepool",
   )

``backend``
   ``"thread"``, ``"process"``, or ``"interpreter"``. You may also pass the
   matching ``ExecutorBackend`` enum value.

``max_pools``
   Maximum number of executor objects owned by this manager. Required.

``min_pools``
   Minimum desired number of executor objects. The manager creates this many on
   startup unless adaptive sizing asks for more.

``units_per_pool``
   Adaptive sizing ratio used with ``size_provider``.

``size_provider``
   Optional callable returning a current unit count. Units can be connected
   devices, tenants, queues, shards, customers, or any custom runtime signal.

``check_interval``
   How often the background checker wakes when no scale or expiry event occurs.
   Expiring leases and ``notify_scale_changed()`` can wake it earlier.

``default_lease_seconds``
   Default lease duration when callers do not specify ``lease_seconds`` in
   ``acquire()``.

``lease_grace_seconds``
   Extra time after soft expiry before hard revocation.

``workers_per_pool``
   Worker count passed to the executor constructor as ``max_workers``.

``name_prefix``
   Prefix for worker thread names on backends that support
   ``thread_name_prefix``.

``logger``
   Optional logger used by the manager for lifecycle, lease, and checker logs.

``process_logging``
   Optional ``ProcessLoggingConfig`` for process-worker log forwarding.

``forward_process_logs``
   Convenience flag for enabling process-worker log forwarding without creating a
   ``ProcessLoggingConfig`` manually.

``process_log_level``
   Child-process root logger level when process log forwarding is enabled.

``process_log_target_logger``
   Parent-process logger that receives forwarded worker log records.

``clear_process_log_handlers``
   Whether to remove existing child-process root handlers before installing the
   queue handler. Defaults to ``True`` to avoid duplicate logs after fork.

``**executor_kwargs``
   Extra keyword arguments passed to the underlying executor constructor. For the
   process backend this can include options such as ``initializer``, ``initargs``,
   ``mp_context``, or ``max_tasks_per_child``.

Validation notes
----------------

``max_pools``, ``min_pools``, ``units_per_pool``, and ``workers_per_pool`` must
be positive integer-like values. Fractional values are rejected instead of being
silently truncated.

``check_interval`` and ``default_lease_seconds`` must be finite numbers greater
than zero.

``lease_grace_seconds`` must be a finite number greater than or equal to zero.
Use ``lease_grace_seconds=0.0`` for no grace period.

Per-call ``lease_seconds`` passed to ``manager.acquire()`` must be a finite
number greater than zero.

Process logging configuration
-----------------------------

Use the explicit configuration object when you want documented, reusable
configuration:

.. code-block:: python

   import logging

   from leasepool import LeasedExecutorManager, ProcessLoggingConfig


   manager = LeasedExecutorManager(
       backend="process",
       max_pools=1,
       min_pools=1,
       workers_per_pool=2,
       process_logging=ProcessLoggingConfig(
           enabled=True,
           level="INFO",
           target_logger=logging.getLogger("myapp.process-workers"),
       ),
   )

Use the convenience arguments for a shorter setup:

.. code-block:: python

   manager = LeasedExecutorManager(
       backend="process",
       max_pools=1,
       min_pools=1,
       workers_per_pool=2,
       forward_process_logs=True,
       process_log_level="INFO",
   )

Do not pass ``process_logging`` and the ``forward_process_logs`` /
``process_log_*`` convenience arguments together.

Acquire options
---------------

.. code-block:: python

   lease = await manager.acquire(
       lease_seconds=30.0,
       owner="request:123",
       wait=True,
       timeout=2.0,
   )

``lease_seconds``
   Overrides ``default_lease_seconds`` for this lease.

``owner``
   Optional diagnostic label.

``wait``
   If ``True``, wait for capacity when every pool is leased. If ``False``, raise
   ``LeaseUnavailableError`` immediately.

``timeout``
   Maximum time to wait for capacity. Raises built-in ``TimeoutError`` if the
   timeout is reached.

WorkGrinder
-----------

.. code-block:: python

   grinder = WorkGrinder(
       executor_manager=manager,
       max_wait_seconds=10.0,
       batch_size_threshold=20,
       lease_seconds=60.0,
       owner_prefix="work-grinder",
   )

``executor_manager``
   Started ``LeasedExecutorManager`` used for leases.

``max_wait_seconds``
   Maximum age of the oldest pending item before a batch is processed.

``batch_size_threshold``
   Pending item count that triggers immediate batch processing.

``lease_seconds``
   Lease duration requested for each batch.

``owner_prefix``
   Prefix used to label batch leases in manager diagnostics.

Loop ownership
--------------

``WorkGrinder`` async methods are bound to the event loop that called
``await grinder.start()``.

Call these from the owning event loop:

* ``await grinder.submit(...)``;
* ``await grinder.enqueue(...)``;
* ``await grinder.stop(...)``;
* ``await grinder.astats()``;
* ``grinder.stats()`` while the grinder is running.

Call these from other OS threads:

* ``grinder.submit_from_thread(...)``;
* ``grinder.stats_from_thread(...)``.

max_pools is per manager
------------------------

``max_pools`` is not global across all backend types.

.. code-block:: python

   thread_manager = LeasedExecutorManager(
       backend="thread",
       max_pools=5,
       workers_per_pool=4,
   )

   process_manager = LeasedExecutorManager(
       backend="process",
       max_pools=1,
       workers_per_pool=4,
   )

This allows up to five thread executors and one process executor. Each manager
enforces its own limit.
