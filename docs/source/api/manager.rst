LeasedExecutorManager
=====================

.. autoclass:: leasepool.LeasedExecutorManager
   :members:
   :undoc-members:
   :show-inheritance:

Manual summary
--------------

Constructor
~~~~~~~~~~~

.. code-block:: python

   LeasedExecutorManager(
       *,
       backend="thread",
       max_pools,
       min_pools=1,
       units_per_pool=10,
       size_provider=None,
       check_interval=120.0,
       default_lease_seconds=300.0,
       lease_grace_seconds=15.0,
       workers_per_pool=4,
       name_prefix="leasepool",
       logger=None,
       process_logging=None,
       forward_process_logs=False,
       process_log_level=logging.INFO,
       process_log_target_logger=None,
       clear_process_log_handlers=True,
       **executor_kwargs,
   )

Lifecycle
~~~~~~~~~

``await manager.start()``
   Start the manager, create the minimum/desired pool count, and start the
   checker task. After the manager has started, this method must be called from the owning event
   loop. Calling it from another event loop raises ``RuntimeError``.

``await manager.stop()``
   Stop the checker task, clear available and leased pools, shut down owned
   executors, and stop process log forwarding if it is running. Calling ``stop()`` before ``start()``
   is safe and remains a no-op.

Acquiring and releasing
~~~~~~~~~~~~~~~~~~~~~~~

``await manager.acquire(lease_seconds=None, owner=None, wait=True, timeout=None)``
   Borrow an executor through an ``ExecutorLease``.

``await manager.release(lease_id)``
   Return a lease manually. Most users call ``await lease.release()`` or use the
   lease as an async context manager instead.

Lease draining
~~~~~~~~~~~~~~

If work was submitted through ``lease.executor.submit()``, releasing the lease
marks it as released and rejects new submissions, but the executor is not
returned to the available pool until submitted futures finish.

This prevents work submitted under one lease from overlapping with work submitted
under a later lease on the same executor.

Broken executor handling
~~~~~~~~~~~~~~~~~~~~~~~~

If an executor becomes broken, the manager retires it, removes it from active
leases, shuts it down, and creates replacement capacity when needed.

Shutdown triggered from future callbacks is deferred out of the callback context
to avoid deadlocks or hangs in backend-owned callback threads.

Sizing and diagnostics
~~~~~~~~~~~~~~~~~~~~~~

``manager.notify_scale_changed()``
   Wake the checker after the adaptive size signal changes.

``manager.desired_executor_count()``
   Return the current adaptive target.

``manager.stats()``
   Return a diagnostic snapshot dictionary.

Common properties
~~~~~~~~~~~~~~~~~

``manager.backend``
   Backend enum.

``manager.available_count``
   Number of idle executor pools.

``manager.leased_count``
   Number of currently leased executor pools.

``manager.total_count``
   Available plus leased executor pools.
