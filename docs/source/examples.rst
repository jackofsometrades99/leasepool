Examples
========

The repository examples are a guided learning path. Run them from the project
root after installing the package in editable mode:

.. code-block:: bash

   pip install -e .
   python examples/00_quickstart_thread_backend.py

For process-backend examples, run the file directly. Do not paste process-pool
code into a REPL because worker processes need importable top-level functions.

Example map
-----------

.. list-table::
   :header-rows: 1
   :widths: 32 68

   * - File
     - What it teaches
   * - ``00_quickstart_thread_backend.py``
     - Minimal manager lifecycle, lease acquisition, and ``lease.run()``.
   * - ``01_lease_context_manager.py``
     - Safe context-managed leases, owner labels, expiry fields, keyword args.
   * - ``02_manual_acquire_release.py``
     - Manual release and direct ``lease.executor.submit()`` through the proxy.
   * - ``03_wait_timeout_unavailable.py``
     - ``wait=False``, ``timeout``, and backpressure when all pools are leased.
   * - ``04_adaptive_sizing.py``
     - ``size_provider``, ``units_per_pool``, and ``notify_scale_changed()``.
   * - ``05_stats_and_counts.py``
     - ``backend``, counts, desired target, and ``manager.stats()``.
   * - ``06_lease_expiry_and_revocation.py``
     - Soft expiry, hard expiry, and ``LeaseExpiredError``.
   * - ``07_process_backend_cpu_work.py``
     - Process backend for CPU-heavy picklable functions.
   * - ``08_work_grinder_submit.py``
     - ``WorkGrinder.submit()`` batching and result awaiting.
   * - ``09_work_grinder_enqueue.py``
     - ``WorkGrinder.enqueue()`` and awaiting futures later.
   * - ``10_submit_from_thread.py``
     - ``WorkGrinder.submit_from_thread()`` from another OS thread.
   * - ``11_error_handling.py``
     - Common leasepool exceptions.
   * - ``12_interpreter_backend_future_python314.py``
     - Future ``InterpreterPoolExecutor`` backend behavior.
   * - ``13_process_log_forwarding.py``
     - ``ProcessLoggingConfig`` and process-worker log forwarding.
   * - ``14_complete_library_walkthrough.py``
     - Combined lifecycle, adaptive sizing, leases, grinder, and diagnostics.
   * - ``fastapi_lifespan_pattern.py``
     - Store a manager on ``app.state`` and stop it during lifespan shutdown.

Complete walkthrough
--------------------

.. literalinclude:: ../../examples/14_complete_library_walkthrough.py
   :language: python
   :caption: examples/14_complete_library_walkthrough.py

FastAPI pattern
---------------

.. literalinclude:: ../../examples/fastapi_lifespan_pattern.py
   :language: python
   :caption: examples/fastapi_lifespan_pattern.py
