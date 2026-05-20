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
   Start the background grinder task.

``await grinder.stop(cancel_pending=False)``
   Stop the grinder. Pending work is drained by default. With
   ``cancel_pending=True``, queued pending work is cancelled.

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
   Return a diagnostic snapshot. Call it from the event-loop thread.
