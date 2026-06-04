WorkGrinder
===========

``WorkGrinder`` batches many submitters into executor work batches.

Use it when many async callers submit small synchronous jobs and you want one
component to control batching, leasing, completion, and shutdown.

How batching works
------------------

The grinder processes a batch when either:

* pending work count reaches ``batch_size_threshold``;
* the oldest pending item has waited ``max_wait_seconds``.

Each batch acquires one lease from the configured manager, submits each work item
through that lease, resolves each caller's future, and releases the lease.

Basic submit
------------

``submit()`` queues work and waits for the result:

.. literalinclude:: ../../../examples/08_work_grinder_submit.py
   :language: python
   :caption: examples/08_work_grinder_submit.py

enqueue
-------

``enqueue()`` queues work and returns an ``asyncio.Future`` immediately. This is
useful when you want to queue multiple items first and await later.

.. literalinclude:: ../../../examples/09_work_grinder_enqueue.py
   :language: python
   :caption: examples/09_work_grinder_enqueue.py

submit_from_thread
------------------

``submit_from_thread()`` is for non-async code or another OS thread. It returns a
``concurrent.futures.Future``.

.. literalinclude:: ../../../examples/10_submit_from_thread.py
   :language: python
   :caption: examples/10_submit_from_thread.py

Event-loop ownership
--------------------

``WorkGrinder`` belongs to the event loop that started it.

Use these from the owning event loop:

* ``await grinder.submit(...)``;
* ``await grinder.enqueue(...)``;
* ``await grinder.stop(...)``;
* ``await grinder.astats()``.

Use these from other OS threads:

* ``grinder.submit_from_thread(...)``;
* ``grinder.stats_from_thread(...)``.

Calling async WorkGrinder methods from another event loop raises
``RuntimeError``.

Shutdown behavior
-----------------

.. code-block:: python

   await grinder.stop(cancel_pending=False)

Drains queued work before stopping. This is the graceful shutdown path.

.. code-block:: python

   await grinder.stop(cancel_pending=True)

Cancels queued pending work and cancels the grinder task if it is blocked
waiting for a lease or waiting for in-flight executor work.

Already-running synchronous functions follow the underlying executor semantics.
For thread workers, cancelling the asyncio wrapper does not forcibly stop Python
code that is already running in a worker thread. The executor lease remains
managed safely by the manager's lease-draining behavior.

Stop the grinder before stopping the manager it depends on:

.. code-block:: python

   await grinder.stop(cancel_pending=True)
   await manager.stop()

Validation
~~~~~~~~~~

``WorkGrinder`` validates its batching and lease configuration at construction
time.

``batch_size_threshold`` must be a strict positive integer. Fractional values
such as ``1.9`` are rejected instead of being truncated.

``max_wait_seconds`` and ``lease_seconds`` must be finite positive numbers.
``NaN``, positive infinity, negative infinity, booleans, strings, zero, and
negative values are rejected.

Cross-thread APIs
~~~~~~~~~~~~~~~~~

``submit_from_thread()`` and ``stats_from_thread()`` are only for non-owner OS
threads. They must not be called from the event-loop thread that started the
grinder.

From the owning event loop, use:

.. code-block:: python

   await grinder.submit(...)
   await grinder.enqueue(...)
   grinder.stats()
   await grinder.astats()

From another OS thread, use:

.. code-block:: python

   future = grinder.submit_from_thread(sync_fn, arg)
   result = future.result(timeout=2)

   stats = grinder.stats_from_thread(timeout=2)

Cancellation
~~~~~~~~~~~~

If a future returned by ``enqueue()`` is cancelled while still pending, the item
is removed from the pending queue promptly. This keeps ``grinder.stats()`` accurate
and avoids retaining cancelled work until the next batch threshold, timeout, or
shutdown.

Partial batch submission failures
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

WorkGrinder treats batch items independently.

If a submitted callable raises, only that caller receives the callable exception.
Other submitted work in the same batch can still complete normally.

If executor submission fails part-way through a batch, already-submitted work is
awaited and receives its real result or exception. Only work that was not
submitted receives the submission failure.

Diagnostics
-----------

Call ``grinder.stats()`` from the event-loop thread to get:

* ``started``;
* ``stopping``;
* ``pending``;
* ``batch_size_threshold``;
* ``max_wait_seconds``;
* ``lease_seconds``;
* ``oldest_wait_seconds``.
