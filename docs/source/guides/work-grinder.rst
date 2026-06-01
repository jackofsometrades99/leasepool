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
