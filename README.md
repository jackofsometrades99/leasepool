# leasepool

**Executor leasing, backpressure, and adaptive CPU/I/O offloading for async Python.**

`leasepool` helps async applications borrow local executor capacity safely. Instead
of passing raw `ThreadPoolExecutor` or `ProcessPoolExecutor` objects around your
codebase, callers acquire short-lived leases, run synchronous work, and return the
executor to the manager.

Use it when you need to run blocking I/O, legacy sync SDK calls, or CPU-heavy
functions from an `asyncio` application without letting unbounded executor usage
spread through the service.

## Install

```bash
pip install leasepool
```

For local development from this repository:

```bash
pip install -e .
```

## Project links

- GitHub: https://github.com/jackofsometrades99/leasepool
- PyPI: https://pypi.org/project/leasepool/
- Official Documentation: https://leasepool.readthedocs.io/en/latest/

## Free-threaded Python / no-GIL support

`leasepool` is a pure Python package and does not ship native extension modules.
It is intended to work on CPython free-threaded builds.

Current support level:

- CPython free-threaded builds: Stable
- Package classifier: `Programming Language :: Python :: Free Threading :: 3 - Stable`

Note that `leasepool` can manage executor leases safely, but functions submitted by
users are still responsible for their own thread-safety when run concurrently.

## Quickstart

```python
import asyncio
import time

from leasepool import ExecutorBackend, LeasedExecutorManager


def blocking_uppercase(value: str) -> str:
    time.sleep(0.2)
    return value.upper()


async def main() -> None:
    manager = LeasedExecutorManager(
        backend=ExecutorBackend.THREAD,
        max_pools=2,
        min_pools=1,
        workers_per_pool=4,
        name_prefix="quickstart-worker",
    )

    await manager.start()

    try:
        async with await manager.acquire(owner="quickstart") as lease:
            result = await lease.run(blocking_uppercase, "hello leasepool")

        print(result)
    finally:
        await manager.stop()


asyncio.run(main())
```

## Core usage model

A `LeasedExecutorManager` owns a bounded number of executor pools.

```text
async application
  -> LeasedExecutorManager
  -> ExecutorLease
  -> ThreadPoolExecutor / ProcessPoolExecutor
```

The lease is the temporary right to submit work to one executor. Prefer the async
context-manager style because it returns the lease automatically:

```python
async with await manager.acquire(owner="vendor-sdk-call") as lease:
    result = await lease.run(sync_function, payload)
```

Manual release is also available when your control flow requires it:

```python
lease = await manager.acquire(owner="manual-flow")
try:
    result = await lease.run(sync_function)
finally:
    await lease.release()
```

`lease.executor` is a safe proxy. It supports `submit()`, but prevents callers
from shutting down the internal executor or submitting after the lease expires or
has been released.

## Backends

### Thread backend

Use `backend="thread"` or `ExecutorBackend.THREAD` for blocking I/O:

- blocking vendor SDKs
- synchronous HTTP or database clients
- file I/O
- small blocking operations called from async services

### Process backend

Use `backend="process"` or `ExecutorBackend.PROCESS` for CPU-heavy Python work
that should run across CPU cores:

```python
manager = LeasedExecutorManager(
    backend=ExecutorBackend.PROCESS,
    max_pools=1,
    min_pools=1,
    workers_per_pool=4,
)
```

Functions, arguments, and return values submitted to the process backend must be
picklable. Prefer top-level functions and simple serializable data. Do not submit
lambdas, nested functions, sockets, database clients, or async clients.

### Interpreter backend

`backend="interpreter"` is reserved for Python 3.14+ `InterpreterPoolExecutor`.
On earlier Python versions, selecting it raises `UnsupportedBackendError`.

## Backpressure and waiting

`max_pools` bounds the number of executor objects owned by one manager. If every
pool is leased, `acquire()` waits by default:

```python
lease = await manager.acquire(owner="wait-for-capacity", timeout=2.0)
```

Fail immediately with `wait=False`:

```python
from leasepool import LeaseUnavailableError

try:
    lease = await manager.acquire(owner="no-wait", wait=False)
except LeaseUnavailableError:
    # Return HTTP 503, retry later, or enqueue elsewhere.
    ...
```

## Lease expiry

Each lease has a soft lifetime and a grace period:

```python
manager = LeasedExecutorManager(
    backend="thread",
    max_pools=2,
    default_lease_seconds=300.0,
    lease_grace_seconds=15.0,
)

lease = await manager.acquire(lease_seconds=30.0, owner="bounded-operation")
```

After `lease_seconds + lease_grace_seconds`, new submissions through that lease
raise `LeaseExpiredError`. Existing work that was already submitted is left to the
underlying executor semantics.

## Adaptive sizing

You can connect desired pool count to a runtime signal:

```python
connected_devices: set[str] = set()

manager = LeasedExecutorManager(
    backend="thread",
    max_pools=10,
    min_pools=1,
    units_per_pool=10,
    size_provider=lambda: len(connected_devices),
)

await manager.start()

connected_devices.add("device-1")
manager.notify_scale_changed()
```

The target executor count is:

```text
max(min_pools, ceil(size_provider() / units_per_pool))
```

capped by `max_pools`. Idle executors above the target are shut down. Active
non-expired leases are not revoked just because the target shrinks.

## WorkGrinder

`WorkGrinder` batches many async submitters into leased executor batches:

```python
from leasepool import WorkGrinder

grinder = WorkGrinder(
    executor_manager=manager,
    batch_size_threshold=50,
    max_wait_seconds=2.0,
    lease_seconds=60.0,
)

await grinder.start()

try:
    result = await grinder.submit(sync_function, payload, owner="item-1")
finally:
    await grinder.stop(cancel_pending=True)
```

Use:

- `await grinder.submit(...)` to queue work and wait for its result.
- `await grinder.enqueue(...)` to receive an `asyncio.Future` immediately.
- `grinder.submit_from_thread(...)` from non-async code or another OS thread.
- `grinder.stats()` for diagnostics from the event-loop thread.

## Process worker log forwarding

Worker-process logs do not automatically flow through the parent process logger.
Enable forwarding when using the process backend:

```python
import logging

from leasepool import LeasedExecutorManager, ProcessLoggingConfig

manager = LeasedExecutorManager(
    backend="process",
    max_pools=1,
    min_pools=1,
    workers_per_pool=2,
    process_logging=ProcessLoggingConfig(
        enabled=True,
        level="INFO",
        target_logger=logging.getLogger("leasepool.process"),
    ),
)
```

A convenience form is also available:

```python
manager = LeasedExecutorManager(
    backend="process",
    max_pools=1,
    forward_process_logs=True,
    process_log_level="INFO",
)
```

## Diagnostics

```python
print(manager.backend)
print(manager.available_count)
print(manager.leased_count)
print(manager.total_count)
print(manager.desired_executor_count())
print(manager.stats())
```

`manager.stats()` includes backend, sizing, counts, workers per pool, and current
lease expiry information.

## Examples

The `examples/` directory is designed as a learning path:

```bash
python examples/00_quickstart_thread_backend.py
python examples/07_process_backend_cpu_work.py
python examples/08_work_grinder_submit.py
python examples/13_process_log_forwarding.py
python examples/14_complete_library_walkthrough.py
```

For process-backend examples, run files directly instead of pasting them into a
REPL. `ProcessPoolExecutor` needs importable top-level functions.

See `README_EXAMPLES.md` for the complete example map.

## What leasepool is not

`leasepool` is not a distributed task queue. It does not provide persistence,
remote workers, retries across machines, scheduling, or broker integration. It
manages local executor capacity inside one Python process.
