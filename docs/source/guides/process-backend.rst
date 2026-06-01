Process backend
===============

Use the process backend for CPU-heavy Python work on Python 3.11+ when you want
work to run across CPU cores.

Good uses
---------

* parsing large payloads;
* scoring algorithms;
* CPU-heavy transformations;
* compression or hashing;
* pure functions over serializable data.

Pickling rules
--------------

``ProcessPoolExecutor`` sends functions, arguments, and return values between
processes. They must be picklable.

Good:

.. code-block:: python

   def calculate_score(payload: dict[str, float]) -> float:
       return float(payload["value"]) * 1.5

Avoid:

.. code-block:: python

   lambda value: value * 2

Avoid sending:

* Redis clients;
* database connections;
* sockets;
* locks;
* async functions;
* objects with complex process-local state.

Basic example
-------------

.. literalinclude:: ../../../examples/07_process_backend_cpu_work.py
   :language: python
   :caption: examples/07_process_backend_cpu_work.py

Keyword arguments
-----------------

``ExecutorLease.run()`` supports keyword arguments. With the process backend,
keyword values must also be picklable.

.. code-block:: python

   async with await manager.acquire(owner="score") as lease:
       result = await lease.run(calculate_score, payload={"value": 21.0})

Executor kwargs
---------------

Extra keyword arguments passed to ``LeasedExecutorManager`` are forwarded to the
underlying executor constructor.

For process pools this lets you pass options such as ``initializer``,
``initargs``, ``mp_context``, and ``max_tasks_per_child``:

.. code-block:: python

   manager = LeasedExecutorManager(
       backend="process",
       max_pools=1,
       workers_per_pool=4,
       initializer=configure_worker,
       initargs=("worker-config",),
   )

When process log forwarding is enabled, leasepool composes its own initializer
with your initializer so both run.

Broken process pools
--------------------

If a process pool becomes broken, for example because a worker initializer fails
or a worker exits unexpectedly, leasepool retires that executor instead of
returning it to the available pool.

The manager replaces capacity according to ``min_pools`` and adaptive sizing.
Submitted futures still expose the underlying ``concurrent.futures`` exception,
such as a broken-pool exception.

Operational notes
-----------------

Run process-backend examples as files:

.. code-block:: bash

   python examples/07_process_backend_cpu_work.py

Do not paste process-pool examples into an interactive REPL. Worker processes
must be able to import top-level functions from a module.
