from __future__ import annotations
import time
from collections.abc import Callable
from random import uniform
from typing import TypeVar
from .exceptions import AgentError

T = TypeVar("T")

def _is_daily_quota_exhausted(exc: AgentError) -> bool:
    details: object = getattr(exc, "details", None)
    cause: object = getattr(exc, "cause", None)

    status_code: object = None
    if isinstance(details, dict):
        status_code = details.get("status_code")

    if status_code != 429:
        return False

    error_text: str = " ".join(
        str(value)
        for value in (cause, getattr(cause, "message", None), getattr(exc, "message", None), details)
        if value is not None
    ).lower()

    daily_quota_markers: tuple[str, ...] = (
        "generate_content_free_tier_requests",
        "generaterequestsperdayperproject",
        "per_day_per_project",
        "quota exceeded for metric",
    )

    return any(marker in error_text for marker in daily_quota_markers)

def retry_call(operation: Callable[[], T], *, max_attempts: int = 3, base_delay_seconds: float = .5) -> T:
    if max_attempts < 1: raise ValueError("max_attempts must be >= 1.")
    for attempt in range(1, max_attempts + 1):
        try:
            return operation()
        except AgentError as exc:
            if _is_daily_quota_exhausted(exc):
                raise

            if not exc.retryable or attempt == max_attempts:
                raise

            time.sleep(base_delay_seconds * (2 ** (attempt - 1)) + uniform(0, base_delay_seconds))
