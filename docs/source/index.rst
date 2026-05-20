leasepool documentation
=======================

**leasepool** is a local executor orchestration library for async Python
applications.

It helps async services safely borrow execution capacity from
``ThreadPoolExecutor`` and ``ProcessPoolExecutor`` backends using leases,
backpressure, expiry, adaptive sizing, batch submission, and clean shutdown.

Project links
-------------

* `GitHub repository <https://github.com/jackofsometrades99/leasepool>`_
* `PyPI package <https://pypi.org/project/leasepool/>`_

Free-threaded Python / no-GIL support
-------------------------------------

``leasepool`` is a pure Python package and does not ship native extension
modules. It is intended to work on CPython free-threaded builds.

Current support level: ``Stable``.

The package declares:

.. code-block:: text

   Programming Language :: Python :: Free Threading :: 3 - Stable

User-submitted functions are still responsible for their own thread-safety when
executed concurrently.

Python 3.11+ support includes:

* ``thread`` backend for blocking I/O and legacy synchronous SDKs.
* ``process`` backend for CPU-heavy Python work.
* ``interpreter`` backend reserved for Python 3.14+ ``InterpreterPoolExecutor``.

.. warning::

   ``leasepool`` is not a distributed task queue. It is not a replacement for
   Celery, Dramatiq, RQ, Ray, or a message broker. It manages **local** executor
   capacity inside one Python process.

.. toctree::
   :maxdepth: 2
   :caption: User guide

   installation
   quickstart
   concepts
   configuration
   guides/thread-backend
   guides/process-backend
   guides/process-logging
   guides/work-grinder
   guides/adaptive-sizing
   guides/error-handling
   patterns/fastapi
   examples
   faq

.. toctree::
   :maxdepth: 2
   :caption: API reference

   api/index

.. toctree::
   :maxdepth: 1
   :caption: Project

   readthedocs
   contributing
   changelog
