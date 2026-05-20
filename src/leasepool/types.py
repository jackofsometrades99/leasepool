from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeAlias

SyncCallable: TypeAlias = Callable[..., Any]
SizeProvider: TypeAlias = Callable[[], int]
