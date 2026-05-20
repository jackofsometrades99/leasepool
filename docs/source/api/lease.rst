ExecutorLease
=============

.. autoclass:: leasepool.ExecutorLease
   :members:
   :undoc-members:
   :show-inheritance:

Manual summary
--------------

``lease.lease_id``
   Unique lease identifier.

``lease.owner``
   Optional owner label.

``lease.lease_seconds``
   Requested soft lease lifetime.

``lease.grace_seconds``
   Extra time before hard revocation.

``lease.leased_at``
   Monotonic timestamp when the lease was created.

``lease.executor``
   Safe executor proxy. It supports ``submit()`` but rejects direct
   ``shutdown()`` and submissions after release or revocation.

``lease.soft_expires_at``
   Monotonic timestamp for soft expiry.

``lease.hard_expires_at``
   Monotonic timestamp for hard expiry.

``await lease.run(fn, *args, **kwargs)``
   Run a synchronous callable in the leased executor and await its result.

``await lease.release()``
   Return the lease. Calling it more than once is safe.

Async context manager
---------------------

.. code-block:: python

   async with await manager.acquire(owner="job") as lease:
       result = await lease.run(sync_function)
