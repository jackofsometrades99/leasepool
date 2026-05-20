from __future__ import annotations

import sys
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

import pytest

from helpers import current_thread_name, multiply
from leasepool import ExecutorBackend, UnsupportedBackendError
from leasepool.backends import build_executor, normalize_backend, resolve_executor_cls


def test_normalize_backend_accepts_enum() -> None:
    assert normalize_backend(ExecutorBackend.THREAD) is ExecutorBackend.THREAD
    assert normalize_backend(ExecutorBackend.PROCESS) is ExecutorBackend.PROCESS


def test_normalize_backend_accepts_case_insensitive_string() -> None:
    assert normalize_backend("thread") is ExecutorBackend.THREAD
    assert normalize_backend("THREAD") is ExecutorBackend.THREAD
    assert normalize_backend("process") is ExecutorBackend.PROCESS
    assert normalize_backend("INTERPRETER") is ExecutorBackend.INTERPRETER


def test_normalize_backend_rejects_unknown_backend() -> None:
    with pytest.raises(ValueError, match="Unsupported backend"):
        normalize_backend("gpu")


def test_resolve_executor_cls_thread() -> None:
    assert resolve_executor_cls("thread") is ThreadPoolExecutor


def test_resolve_executor_cls_process() -> None:
    assert resolve_executor_cls("process") is ProcessPoolExecutor


@pytest.mark.skipif(
    sys.version_info >= (3, 14),
    reason="Python 3.14+ has InterpreterPoolExecutor",
)
def test_resolve_executor_cls_interpreter_is_not_available_before_314() -> None:
    with pytest.raises(UnsupportedBackendError, match="Python 3.14"):
        resolve_executor_cls("interpreter")


def test_build_thread_executor_sets_thread_name_prefix() -> None:
    executor = build_executor(
        backend="thread",
        max_workers=1,
        name_prefix="test-prefix",
        executor_seq=7,
        executor_kwargs={},
    )

    try:
        assert isinstance(executor, ThreadPoolExecutor)

        thread_name = executor.submit(current_thread_name).result(timeout=1)

        assert thread_name.startswith("test-prefix-7")
    finally:
        executor.shutdown(wait=True, cancel_futures=True)


def test_build_process_executor_does_not_pass_thread_name_prefix() -> None:
    executor = build_executor(
        backend="process",
        max_workers=1,
        name_prefix="ignored-for-process",
        executor_seq=1,
        executor_kwargs={},
    )

    try:
        assert isinstance(executor, ProcessPoolExecutor)
        assert executor.submit(multiply, 6, 7).result(timeout=5) == 42
    finally:
        executor.shutdown(wait=True, cancel_futures=True)
