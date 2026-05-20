Error handling
==============

leasepool exceptions
--------------------

``LeasePoolError``
   Base exception for all leasepool-specific errors.

``LeasePoolNotStartedError``
   Raised when acquiring from a manager that has not been started.

``LeaseUnavailableError``
   Raised when ``wait=False`` and no executor is available.

``LeaseExpiredError``
   Raised when submitting through a released or expired lease.

``UnsupportedBackendError``
   Raised when requesting a backend that is not available on the current Python
   version.

Acquire before start
--------------------

.. code-block:: python

   from leasepool import LeasePoolNotStartedError


   try:
       await manager.acquire()
   except LeasePoolNotStartedError:
       ...

No capacity available
---------------------

Use ``wait=False`` when you want to fail fast instead of waiting:

.. code-block:: python

   from leasepool import LeaseUnavailableError


   try:
       lease = await manager.acquire(wait=False)
   except LeaseUnavailableError:
       # Return HTTP 503, retry later, or enqueue elsewhere.
       ...

Use ``timeout`` when you are willing to wait for bounded time:

.. code-block:: python

   try:
       lease = await manager.acquire(timeout=2.0)
   except TimeoutError:
       ...

Expired leases
--------------

After hard expiry, new submissions through a lease raise ``LeaseExpiredError``.

.. literalinclude:: ../../../examples/06_lease_expiry_and_revocation.py
   :language: python
   :caption: examples/06_lease_expiry_and_revocation.py

Full exception example
----------------------

.. literalinclude:: ../../../examples/11_error_handling.py
   :language: python
   :caption: examples/11_error_handling.py
