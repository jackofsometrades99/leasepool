FAQ
===

Is leasepool a task queue?
--------------------------

No. leasepool manages local executor capacity inside one Python process. It does
not provide distributed workers, persistence, retries across machines, scheduling,
or broker integration.

Should I use threads or processes?
----------------------------------

Use threads for blocking I/O and synchronous libraries. Use processes for
CPU-heavy Python work when functions and data are picklable.

Can I submit async functions?
-----------------------------

No. leasepool is designed for synchronous callables that need to run outside the
event loop. Async functions should usually be awaited directly.

Is max_pools global?
--------------------

No. ``max_pools`` applies to one ``LeasedExecutorManager`` instance. Separate
thread and process managers each enforce their own limits.

What happens if every pool is leased?
-------------------------------------

``manager.acquire()`` waits by default. Pass ``timeout=...`` to bound the wait or
``wait=False`` to raise ``LeaseUnavailableError`` immediately.

What happens after a lease expires?
-----------------------------------

After ``lease_seconds + lease_grace_seconds``, new submissions through that lease
raise ``LeaseExpiredError``. Use context managers and realistic lease durations to
avoid accidental expiry.

Can I use InterpreterPoolExecutor on Python 3.11?
-------------------------------------------------

No. The interpreter backend is reserved for Python 3.14+.

Why do worker-process logs not appear in my app logs?
-----------------------------------------------------

Process workers run in child processes. Enable ``ProcessLoggingConfig`` or
``forward_process_logs=True`` when using the process backend if you want worker
log records forwarded to a parent-process logger.

Can I pass executor-specific options?
-------------------------------------

Yes. Extra keyword arguments passed to ``LeasedExecutorManager`` are forwarded to
the underlying executor constructor. For example, process managers can receive
``initializer``, ``initargs``, ``mp_context``, or ``max_tasks_per_child``.
