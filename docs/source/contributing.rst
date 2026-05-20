Contributing
============

Development setup
-----------------

.. code-block:: bash

   git clone https://github.com/yourname/leasepool.git
   cd leasepool
   python -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"
   pip install -r docs/requirements.txt

Run tests
---------

.. code-block:: bash

   pytest -q

Run linting
-----------

.. code-block:: bash

   ruff check .

Run type checking
-----------------

.. code-block:: bash

   mypy src/leasepool

Build docs
----------

.. code-block:: bash

   cd docs
   make html
