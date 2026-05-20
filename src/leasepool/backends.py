from __future__ import annotations

from typing import Any
from enum import StrEnum
from concurrent.futures import Executor, ProcessPoolExecutor, ThreadPoolExecutor


class ExecutorBackend(StrEnum):
    """Enum representing the available executor backends.

    Args:
        StrEnum (_type_): String-based enum for executor backends.
    """
    THREAD = "thread"
    PROCESS = "process"
    INTERPRETER = "interpreter"


def normalize_backend(backend: ExecutorBackend | str) -> ExecutorBackend:
    """Normalize the backend to an ExecutorBackend enum.

    Args:
        backend (ExecutorBackend | str): The backend to normalize.

    Raises:
        ValueError: If the backend is not supported.

    Returns:
        ExecutorBackend: The normalized backend.
    """
    if isinstance(backend, ExecutorBackend):
        return backend
    try:
        return ExecutorBackend(str(backend).lower())
    except ValueError as exc:
        supported = ", ".join(item.value for item in ExecutorBackend)
        raise ValueError(f"Unsupported backend {backend!r}. Supported: {supported}") from exc


def resolve_executor_cls(backend: ExecutorBackend | str) -> type[Executor]:
    """Resolve the executor class for the given backend.

    Args:
        backend (ExecutorBackend | str): The backend to resolve.

    Raises:
        UnsupportedBackendError: If the backend is not supported.
        UnsupportedBackendError: If the InterpreterPoolExecutor is not available.

    Returns:
        type[Executor]: The executor class for the given backend.
    """
    from .exceptions import UnsupportedBackendError

    normalized = normalize_backend(backend)

    if normalized is ExecutorBackend.THREAD:
        return ThreadPoolExecutor

    if normalized is ExecutorBackend.PROCESS:
        return ProcessPoolExecutor

    if normalized is ExecutorBackend.INTERPRETER:
        try:
            from concurrent.futures import InterpreterPoolExecutor  # type: ignore[attr-defined]
        except ImportError as exc:
            raise UnsupportedBackendError(
                "InterpreterPoolExecutor is available only on Python 3.14+."
            ) from exc

        return InterpreterPoolExecutor

    # Defensive fallback for static analyzers.
    raise UnsupportedBackendError(f"Unsupported backend: {backend!r}")


def build_executor(
    *,
    backend: ExecutorBackend | str,
    max_workers: int,
    name_prefix: str,
    executor_seq: int,
    executor_kwargs: dict[str, Any],
) -> Executor:
    """Build an executor instance for the selected backend.

    `thread_name_prefix` is valid for ThreadPoolExecutor and InterpreterPoolExecutor,
    but not for ProcessPoolExecutor on Python 3.11.
    """
    executor_cls = resolve_executor_cls(backend)
    kwargs = dict(executor_kwargs)

    normalized = normalize_backend(backend)

    if normalized in {ExecutorBackend.THREAD, ExecutorBackend.INTERPRETER}:
        kwargs.setdefault("thread_name_prefix", f"{name_prefix}-{executor_seq}")

    return executor_cls(max_workers=max_workers, **kwargs)
