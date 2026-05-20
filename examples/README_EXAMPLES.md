# leasepool examples pack

The `examples/` folder is a runnable learning path for the public `leasepool`
API. Start at `00_...` and move downward when learning the library for the first
time.

Install the package in editable mode from the project root:

```bash
pip install -e .
```

Then run any example directly:

```bash
python examples/00_quickstart_thread_backend.py
```

For process-backend examples, run the file directly. Do not paste the code into
an interactive REPL because `ProcessPoolExecutor` needs importable top-level
functions.

## Recommended learning order

1. `00_quickstart_thread_backend.py` — smallest complete manager/lease example.
2. `01_lease_context_manager.py` — safest lease style and keyword arguments.
3. `02_manual_acquire_release.py` — manual release and direct proxy submit.
4. `03_wait_timeout_unavailable.py` — backpressure, `wait=False`, and timeouts.
5. `04_adaptive_sizing.py` — `size_provider` and `notify_scale_changed()`.
6. `05_stats_and_counts.py` — diagnostic counts and `manager.stats()`.
7. `06_lease_expiry_and_revocation.py` — soft expiry, hard expiry, revocation.
8. `07_process_backend_cpu_work.py` — CPU-heavy work with processes.
9. `08_work_grinder_submit.py` — batch small jobs and wait for results.
10. `09_work_grinder_enqueue.py` — queue futures first, await later.
11. `10_submit_from_thread.py` — submit into the grinder from another thread.
12. `11_error_handling.py` — common exception handling.
13. `12_interpreter_backend_future_python314.py` — future interpreter backend.
14. `13_process_log_forwarding.py` — forward worker-process logs to parent logs.
15. `14_complete_library_walkthrough.py` — combined lifecycle, sizing, leases, grinder, and stats.
16. `fastapi_lifespan_pattern.py` — production-style app startup/shutdown pattern.

## API coverage map

| API or behavior | Covered in |
|---|---|
| `ExecutorBackend.THREAD` | `00_quickstart_thread_backend.py`, `01_lease_context_manager.py` |
| `ExecutorBackend.PROCESS` | `07_process_backend_cpu_work.py`, `13_process_log_forwarding.py` |
| `ExecutorBackend.INTERPRETER` | `12_interpreter_backend_future_python314.py` |
| `LeasedExecutorManager(...)` | all manager examples |
| `manager.start()` / `manager.stop()` | all lifecycle examples |
| `manager.acquire()` | `01_lease_context_manager.py`, `02_manual_acquire_release.py`, `03_wait_timeout_unavailable.py` |
| `manager.release(lease_id)` | used indirectly by `lease.release()` in `02_manual_acquire_release.py` |
| `manager.notify_scale_changed()` | `04_adaptive_sizing.py`, `14_complete_library_walkthrough.py` |
| `manager.desired_executor_count()` | `04_adaptive_sizing.py`, `05_stats_and_counts.py` |
| `manager.available_count` / `leased_count` / `total_count` | `03_wait_timeout_unavailable.py`, `05_stats_and_counts.py` |
| `manager.stats()` | `05_stats_and_counts.py`, `14_complete_library_walkthrough.py` |
| `manager.backend` | `05_stats_and_counts.py` |
| `ExecutorLease.run()` | `00_quickstart_thread_backend.py`, `01_lease_context_manager.py`, `07_process_backend_cpu_work.py` |
| `ExecutorLease.release()` | `02_manual_acquire_release.py`, `03_wait_timeout_unavailable.py` |
| `ExecutorLease` async context manager | `00_quickstart_thread_backend.py`, `01_lease_context_manager.py` |
| `lease.soft_expires_at` / `hard_expires_at` | `01_lease_context_manager.py`, `06_lease_expiry_and_revocation.py` |
| `lease.executor.submit()` | `02_manual_acquire_release.py`, `06_lease_expiry_and_revocation.py` |
| `WorkGrinder.start()` / `stop()` | `08_work_grinder_submit.py`, `09_work_grinder_enqueue.py` |
| `WorkGrinder.submit()` | `08_work_grinder_submit.py`, `14_complete_library_walkthrough.py` |
| `WorkGrinder.enqueue()` | `09_work_grinder_enqueue.py` |
| `WorkGrinder.submit_from_thread()` | `10_submit_from_thread.py` |
| `WorkGrinder.stats()` | `09_work_grinder_enqueue.py`, `14_complete_library_walkthrough.py` |
| `ProcessLoggingConfig` | `13_process_log_forwarding.py` |
| `forward_process_logs=True` convenience API | documented in `README.md` and docs |
| `LeasePoolNotStartedError` | `11_error_handling.py` |
| `LeaseUnavailableError` | `03_wait_timeout_unavailable.py`, `11_error_handling.py` |
| `LeaseExpiredError` | `06_lease_expiry_and_revocation.py`, `11_error_handling.py` |
| `UnsupportedBackendError` | `12_interpreter_backend_future_python314.py` |
| FastAPI lifespan integration | `fastapi_lifespan_pattern.py` |

## FastAPI example


```text
examples/fastapi_lifespan_pattern.py
```

Run it with:

```bash
pip install fastapi uvicorn
uvicorn examples.fastapi_lifespan_pattern:app --reload
```
