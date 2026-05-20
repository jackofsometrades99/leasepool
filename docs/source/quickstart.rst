Quickstart
==========

Use ``leasepool`` when async code needs to run synchronous work without leaking
raw executors throughout your codebase.

The usual lifecycle is:

#. create a ``LeasedExecutorManager``;
#. ``await manager.start()`` during application startup;
#. acquire leases around synchronous work;
#. ``await manager.stop()`` during application shutdown.

Basic thread backend
--------------------

Use the thread backend for blocking I/O or legacy synchronous SDKs:

.. literalinclude:: ../../examples/00_quickstart_thread_backend.py
   :language: python
   :caption: examples/00_quickstart_thread_backend.py

Context-managed leases
----------------------

The async context manager is the recommended style because it returns the lease
even when your work raises an exception.

.. code-block:: python

   async with await manager.acquire(owner="vendor-sdk-call") as lease:
       result = await lease.run(blocking_vendor_call, device_id)

``lease.run()`` accepts positional and keyword arguments. It runs a synchronous
callable in the leased executor and awaits the result.

Manual release
--------------

Manual release is available for control flow that cannot fit inside one context:

.. code-block:: python

   lease = await manager.acquire(owner="manual-flow")

   try:
       result = await lease.run(sync_function)
   finally:
       await lease.release()

Prefer the context-manager form unless manual control is necessary.

CPU work with the process backend
---------------------------------

Use the process backend for CPU-heavy Python work that should run across CPU
cores:

.. literalinclude:: ../../examples/07_process_backend_cpu_work.py
   :language: python
   :caption: examples/07_process_backend_cpu_work.py

.. important::

   With the process backend, submitted functions, arguments, and return values
   must be picklable. Prefer top-level functions and simple serializable data.

Batch many small jobs with WorkGrinder
--------------------------------------

``WorkGrinder`` is useful when many async callers submit small pieces of
synchronous work and you want one component to control batching and leasing.

.. literalinclude:: ../../examples/08_work_grinder_submit.py
   :language: python
   :caption: examples/08_work_grinder_submit.py
