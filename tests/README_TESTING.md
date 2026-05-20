# leasepool comprehensive tests

Drop the `tests/` folder into the root of your `leasepool` project.

Run:

```bash
pip install -e ".[dev]"
pytest -q
```

The tests cover:

- backend normalization and executor creation
- constructor validation
- lifecycle start/stop/restart
- acquire/release behavior
- lease context manager behavior
- proxy misuse behavior
- wait, timeout, and unavailable conditions
- lease expiry and checker revocation
- adaptive sizing grow/shrink behavior
- stats output
- thread backend execution
- process backend execution
- process pickling expectations
- WorkGrinder batching, timeout, cancellation, exceptions, and thread-safe submission
