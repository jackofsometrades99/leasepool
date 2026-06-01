WorkGrinder
===========

.. autoclass:: leasepool.WorkGrinder
   :members:
   :undoc-members:
   :show-inheritance:

Manual summary
--------------

Constructor
~~~~~~~~~~~

.. code-block:: python

   WorkGrinder(
       *,
       executor_manager,
       max_wait_seconds=10.0,
       batch_size_threshold=20,
       lease_seconds=60.0,
       owner_prefix="work-grinder",
       logger=None,
   )

Lifecycle
~~~~~~~~~

``await grinder.start()``
   Start the background grinder task and bind the grinder to the current event
   loop.

``await grinder.stop(cancel_pending=False)``
   Stop the grinder. Pending work is drained by default. With
   ``cancel_pending=True``, queued pending work is cancelled and the grinder task
   is cancelled if it is blocked waiting for a lease or waiting for in-flight
   executor work.

Submitting work
~~~~~~~~~~~~~~~

``await grinder.submit(fn, *args, owner=None, **kwargs)``
   Queue work and wait for its result.

``await grinder.enqueue(fn, *args, owner=None, **kwargs)``
   Queue work and return an ``asyncio.Future`` immediately.

``grinder.submit_from_thread(fn, *args, owner=None, **kwargs)``
   Submit from another OS thread and receive a ``concurrent.futures.Future``.

Diagnostics
~~~~~~~~~~~

``grinder.stats()``
   Return a diagnostic snapshot. Safe before start and after stop. While the
   grinder is running, call it from the owning event loop.

``await grinder.astats()``
   Return a diagnostic snapshot from the owning event loop.

``grinder.stats_from_thread(timeout=None)``
   Return diagnostics from another OS thread.

Loop ownership
~~~~~~~~~~~~~~

Async WorkGrinder methods must be called from the event loop that started the
grinder. Use ``submit_from_thread()`` and ``stats_from_thread()`` from other OS
threads.
