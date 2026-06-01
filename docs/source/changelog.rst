Changelog
=========

0.1.2
-----

Stability release focused on executor lifecycle correctness, shutdown behavior,
validation, and WorkGrinder safety.

Fixed:

* prevented ``LeasedExecutorManager.acquire()`` from returning a new lease while
  the manager is stopping or stopped;
* woke the checker when new leases are acquired so short lease expiries are not
  delayed by a long ``check_interval``;
* prevented expired leases from recycling their executors;
* added lease draining so executors with submitted futures are not returned to
  the pool until those futures finish;
* retired broken executors instead of returning them to the pool;
* deferred executor shutdown from future callbacks to avoid callback-thread
  deadlocks or hangs;
* validated integer sizing options without silent float truncation;
* rejected negative, zero where invalid, NaN, and infinite timing values;
* rejected non-positive or non-finite ``check_interval`` values;
* fixed ``WorkGrinder.stop(cancel_pending=True)`` so it can cancel a grinder task
  blocked in lease acquisition or waiting for executor work;
* added WorkGrinder event-loop ownership checks.

Testing:

* added regression coverage for manager shutdown races;
* added regression coverage for lease expiry scheduling and expired release;
* added regression coverage for draining leases with pending futures;
* added regression coverage for broken thread, process, and Python 3.14+
  interpreter executors;
* added regression coverage for validation edge cases;
* added regression coverage for WorkGrinder cancellation and cross-thread APIs.

0.1.0
-----

Initial planned release.

Features:

* leased executor manager;
* thread backend;
* process backend;
* future interpreter backend selector for Python 3.14+;
* lease expiry and revocation;
* acquire backpressure with ``wait`` and ``timeout``;
* adaptive sizing with ``size_provider`` and ``notify_scale_changed()``;
* ``WorkGrinder`` batching;
* process-worker log forwarding;
* public exceptions;
* examples pack;
* Sphinx documentation.
