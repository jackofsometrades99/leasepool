Hosting on Read the Docs
========================

This documentation pack includes:

.. code-block:: text

   .readthedocs.yaml
   docs/requirements.txt
   docs/source/conf.py
   docs/source/index.rst

Setup steps
-----------

1. Copy the files from this pack into your project root.
2. Commit and push to GitHub.
3. Create or import the project on Read the Docs.
4. Make sure the default branch contains ``.readthedocs.yaml``.
5. Trigger a build.

Local build
-----------

.. code-block:: bash

   pip install -e .
   pip install -r docs/requirements.txt
   cd docs
   make html

Read the Docs config
--------------------

The included config uses Read the Docs v2 configuration:

.. code-block:: yaml

   version: 2

   build:
     os: ubuntu-24.04
     tools:
       python: "3.11"

   sphinx:
     configuration: docs/source/conf.py

   python:
     install:
       - requirements: docs/requirements.txt
       - method: pip
         path: .
