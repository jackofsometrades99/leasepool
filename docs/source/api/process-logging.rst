Process logging
===============

.. autoclass:: leasepool.ProcessLoggingConfig
   :members:
   :undoc-members:
   :show-inheritance:

Low-level helpers
-----------------

These helpers are public in the module primarily for advanced users and tests.
Most applications should configure process log forwarding through
``ProcessLoggingConfig`` or the ``LeasedExecutorManager`` convenience arguments.

.. automodule:: leasepool._process_logging
   :members:
   :undoc-members:
   :show-inheritance:
