Installation
============

Install from PyPI
-----------------

.. code-block:: bash

   pip install leasepool

Install from source
-------------------

From the project root:

.. code-block:: bash

   pip install -e .

Install documentation dependencies
----------------------------------

.. code-block:: bash

   pip install -r docs/requirements.txt

Build documentation locally
---------------------------

.. code-block:: bash

   cd docs
   make html

Open the generated HTML:

.. code-block:: bash

   open build/html/index.html

Python support
--------------

Python 3.11 to 3.13 only supports:

* ``ThreadPoolExecutor``
* ``ProcessPoolExecutor``

Python 3.14+ will support:

* ``ThreadPoolExecutor``
* ``ProcessPoolExecutor``
* ``InterpreterPoolExecutor``


Free-threaded Python
--------------------

leasepool is pure Python and has been tested on CPython 3.14t free-threaded
builds with the GIL disabled.

leasepool manages executor leases, backpressure, shutdown, and WorkGrinder
batching under free-threaded Python. User-submitted callables are still
responsible for their own thread-safety when they mutate shared state or use
non-thread-safe third-party libraries.