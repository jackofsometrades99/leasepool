Installation
============

Install from PyPI
-----------------

When the package is published:

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

The initial version targets Python 3.11+.

Python 3.11 supports:

* ``ThreadPoolExecutor``
* ``ProcessPoolExecutor``

Python 3.14+ will later support:

* ``InterpreterPoolExecutor``
