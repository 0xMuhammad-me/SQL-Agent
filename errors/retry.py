from __future__ import annotations
import time
from collections.abc import Callable
from random import uniform
from typing import TypeVar
from .exceptions import AgentError

T = TypeVar("T")


def retry_call(operation: Callable[[], T], *, max_attempts: int = 3, base_delay_seconds: float = .5) -> T:
    if max_attempts < 1: raise ValueError("max_attempts must be >= 1.")
    for attempt in range(1, max_attempts + 1):
        try:
            return operation()
        except AgentError as exc:
            if not exc.retryable or attempt == max_attempts: raise
            time.sleep(base_delay_seconds * (2 ** (attempt - 1)) + uniform(0, base_delay_seconds))
