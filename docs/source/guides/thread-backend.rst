Thread backend
==============

Use the thread backend for blocking I/O or synchronous libraries that would
otherwise block the event loop.

Good uses
---------

* blocking vendor SDK calls;
* file I/O;
* synchronous HTTP clients;
* synchronous database drivers;
* small blocking operations from async services.

Example
-------

.. literalinclude:: ../../../examples/00_quickstart_thread_backend.py
   :language: python
   :caption: examples/00_quickstart_thread_backend.py

Context manager pattern
-----------------------

.. literalinclude:: ../../../examples/01_lease_context_manager.py
   :language: python
   :caption: examples/01_lease_context_manager.py

Avoid
-----

Do not use the thread backend for heavy pure-Python CPU work if true CPU
parallelism is required on Python 3.11. Use the process backend instead.
