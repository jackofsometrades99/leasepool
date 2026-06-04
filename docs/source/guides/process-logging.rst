Process log forwarding
======================

Logs emitted inside ``ProcessPoolExecutor`` workers are created in child
processes. They do not automatically flow through the parent application's
logger handlers.

``leasepool`` provides optional process log forwarding for the process backend.
It installs a queue handler in each worker and a queue listener in the parent
process.

Explicit configuration
----------------------

Use ``ProcessLoggingConfig`` when you want one object that documents the logging
bridge configuration:

.. literalinclude:: ../../../examples/13_process_log_forwarding.py
   :language: python
   :caption: examples/13_process_log_forwarding.py

Multiprocessing context selection
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When process log forwarding is enabled, leasepool starts a parent-side
``QueueListener`` thread. If no explicit ``mp_context`` is supplied, leasepool
chooses a non-fork multiprocessing context for process pools and logging queues,
preferring ``forkserver`` and then ``spawn``.

This avoids forking a multithreaded parent process after the logging listener has
started.

If your application requires a specific multiprocessing start method, pass an
explicit context:

.. code-block:: python

   import multiprocessing

   manager = LeasedExecutorManager(
       backend="process",
       max_pools=1,
       min_pools=1,
       forward_process_logs=True,
       mp_context=multiprocessing.get_context("spawn"),
   )

Convenience configuration
-------------------------

For shorter setup, pass the convenience arguments directly to the manager:

.. code-block:: python

   import logging

   from leasepool import LeasedExecutorManager


   manager = LeasedExecutorManager(
       backend="process",
       max_pools=1,
       min_pools=1,
       workers_per_pool=2,
       forward_process_logs=True,
       process_log_level="INFO",
       process_log_target_logger=logging.getLogger("myapp.process-workers"),
   )

Do not pass both ``process_logging`` and the convenience arguments in the same
manager.

Configuration fields
--------------------

``enabled``
   Enable child-process log forwarding.

``level``
   Minimum level configured on the child-process root logger. Accepts an integer
   logging level or a standard level name such as ``"INFO"``.

``target_logger``
   Parent-process logger that receives worker log records. If omitted, the
   manager's logger is used.

``clear_child_handlers``
   Remove existing child-process root handlers before installing the queue
   handler. Defaults to ``True`` to avoid duplicate records after fork.

Composing worker initializers
-----------------------------

If you pass ``initializer`` and ``initargs`` to the process executor, leasepool
preserves them when log forwarding is enabled:

.. code-block:: python

   manager = LeasedExecutorManager(
       backend="process",
       max_pools=1,
       forward_process_logs=True,
       initializer=configure_worker,
       initargs=("worker-config",),
   )

The leasepool logging initializer runs first, then your initializer runs.

When to enable it
-----------------

Enable process log forwarding when worker logs are important for debugging,
monitoring, or audit trails.

Leave it disabled when workers do not log or when you have your own
process-aware logging setup.
