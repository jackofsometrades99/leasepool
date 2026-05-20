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
   checker task.

``await manager.stop()``
   Stop the checker task, clear available and leased pools, shut down owned
   executors, and stop process log forwarding if it is running.

Acquiring and releasing
~~~~~~~~~~~~~~~~~~~~~~~

``await manager.acquire(lease_seconds=None, owner=None, wait=True, timeout=None)``
   Borrow an executor through an ``ExecutorLease``.

``await manager.release(lease_id)``
   Return a lease manually. Most users call ``await lease.release()`` or use the
   lease as an async context manager instead.

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
