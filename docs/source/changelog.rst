Changelog
=========

0.1.3 - 2026-06-03
------------------

Correctness and safety release for WorkGrinder validation, event-loop ownership,
cross-thread APIs, cancellation cleanup, partial batch submission handling, and
process log forwarding.

Changed
~~~~~~~

* WorkGrinder now validates ``batch_size_threshold`` as a strict positive
  integer. Fractional values, booleans, strings, zero, and negative values are
  rejected instead of being silently coerced.
* WorkGrinder now validates ``max_wait_seconds`` and ``lease_seconds`` as finite
  positive durations. ``NaN`` and infinity are rejected at construction time.
* ``LeasedExecutorManager.start()``, ``stop()``, and ``acquire()`` now enforce
  owning event-loop usage after the manager has started.
* ``WorkGrinder.submit_from_thread()`` and ``stats_from_thread()`` now fail fast
  when called from the owning event-loop thread. Use the async APIs from the
  owning event loop.
* Process log forwarding now defaults to a non-fork multiprocessing context when
  no explicit ``mp_context`` is provided, preferring ``forkserver`` and then
  ``spawn``.

Fixed
~~~~~

* Fixed wrong-loop ``LeasedExecutorManager.stop()`` calls mutating manager state
  before failing.
* Fixed wrong-loop ``LeasedExecutorManager.acquire()`` calls waiting on loop-bound
  state and potentially missing wakeups.
* Fixed cancelled pending WorkGrinder items remaining in the pending queue until
  threshold, timeout, or shutdown.
* Fixed partial WorkGrinder batch submission failures so already-submitted work
  receives its real result or exception, while only unsubmitted work receives the
  submission error.

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
