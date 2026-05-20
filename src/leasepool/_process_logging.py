from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from logging.handlers import QueueHandler, QueueListener
from typing import Any


@dataclass(frozen=True, slots=True)
class ProcessLoggingConfig:
    """Configuration for forwarding ProcessPoolExecutor worker logs.

    This is intentionally opt-in. Normal leasepool logs are emitted in the parent
    process through normal Python loggers and do not need this bridge.

    Attributes:
        enabled: Enable child-process log forwarding.
        level: Minimum level configured on the child-process root logger.
        target_logger: Parent-process logger that receives records from workers.
            If omitted, LeasedExecutorManager's logger is used.
        clear_child_handlers: Remove inherited/preconfigured child handlers before
            installing the queue handler. This avoids duplicate child logs after
            fork and prevents children from writing directly to stderr.
    """
    enabled: bool = False
    level: int | str = logging.INFO
    target_logger: logging.Logger | None = None
    clear_child_handlers: bool = True


def coerce_log_level(level: int | str) -> int:
    """Return a numeric logging level from an int or standard level name."""
    if isinstance(level, str):
        try:
            resolved = logging.getLevelName(level.upper())
            if isinstance(resolved, int):
                return resolved
            raise ValueError(f"Unknown logging level: {level!r}")
        except Exception as e:
            raise ValueError(f"Invalid logging level: {level!r}") from e

    return int(level)


class LoggerForwardingHandler(logging.Handler):
    """QueueListener target that forwards records into a parent logger.

    QueueListener normally writes records directly to concrete handlers. This
    handler instead re-enters the parent's logger hierarchy, so the application
    keeps control over formatters, handlers, filters, propagation, and levels.
    """

    def __init__(self, target_logger: logging.Logger):
        """Initialize the handler with a target logger.

        Args:
            target_logger (logging.Logger): The parent logger to which records will be forwarded.
        """
        super().__init__(level=logging.NOTSET)
        self._target_logger = target_logger

    def emit(self, record: logging.LogRecord) -> None:
        """Forward a log record to the target logger.

        Args:
            record (logging.LogRecord): The log record to be forwarded.
        """
        if not self._target_logger.isEnabledFor(record.levelno):
            return
        self._target_logger.handle(record)


def configure_process_worker_logging(
    log_queue: Any,
    *,
    level: int | str,
    clear_existing_handlers: bool,
) -> None:
    """Install QueueHandler on the worker process root logger.

    Args:
        log_queue: The multiprocessing queue to which log records will be sent. If None, logging is not configured.
        level: Minimum logging level for the worker process root logger.
        clear_existing_handlers: Whether to remove existing handlers from the root logger before adding the QueueHandler.
    """
    root_logger = logging.getLogger()

    if clear_existing_handlers:
        root_logger.handlers.clear()

    root_logger.addHandler(QueueHandler(log_queue))
    root_logger.setLevel(coerce_log_level(level))


def process_worker_initializer(
    log_queue: Any | None,
    level: int | str,
    clear_existing_handlers: bool,
    user_initializer: Callable[..., Any] | None,
    user_initargs: tuple[Any, ...],
) -> None:
    """ProcessPoolExecutor initializer used by leasepool.

    It first configures child-process logging, then calls the user's original
    initializer, if one was supplied to ProcessPoolExecutor.

    Args:
        log_queue: The multiprocessing queue to which log records will be sent. If None, logging is not configured.
        level: Minimum logging level for the worker process root logger.
        clear_existing_handlers: Whether to remove existing handlers from the root logger before adding the QueueHandler.
        user_initializer: The original initializer function supplied by the user to ProcessPoolExecutor, if any.
        user_initargs: The original initializer arguments supplied by the user to ProcessPoolExecutor, if any.
    """
    if log_queue is not None:
        configure_process_worker_logging(
            log_queue,
            level=level,
            clear_existing_handlers=clear_existing_handlers,
        )

    if user_initializer is not None:
        user_initializer(*user_initargs)


def build_queue_listener(
    *,
    log_queue: Any,
    target_logger: logging.Logger,
) -> QueueListener:
    """Create the parent-side listener for child-process log records.

    Args:
        log_queue: The multiprocessing queue from which log records will be received.
        target_logger: The parent logger to which received log records will be forwarded.
    """
    return QueueListener(
        log_queue,
        LoggerForwardingHandler(target_logger),
        respect_handler_level=True,
    )
