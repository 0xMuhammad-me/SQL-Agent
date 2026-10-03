from __future__ import annotations

import random
import time

from dataclasses import dataclass
from functools import wraps
from typing import Callable, ParamSpec, TypeVar

from .exceptions import AgentError


P = ParamSpec("P")
R = TypeVar("R")


@dataclass(frozen=True)
class RetryPolicy:
    """Controls retry behavior for transient failures."""

    max_attempts: int = 3
    initial_delay_seconds: float = 0.5
    max_delay_seconds: float = 8.0
    exponential_base: float = 2.0
    jitter_ratio: float = 0.2


    def delay_for_attempt(self, attempt_number: int) -> float:
        """
        Calculate backoff delay for a retry attempt.

        Args:
            attempt_number: Zero-based retry attempt number.

        Returns:
            Delay in seconds before the next attempt.
        """

        raw_delay: float = min(
            self.initial_delay_seconds
            * (
                self.exponential_base
                ** attempt_number
            ),
            self.max_delay_seconds,
        )

        jitter: float = (
            raw_delay
            * self.jitter_ratio
            * random.random()
        )

        return raw_delay + jitter


def is_retryable_exception(exc: BaseException) -> bool:
    """
    Determine whether an exception should be retried.

    Returns:
        True when the exception is explicitly marked retryable.
    """

    if isinstance(exc, AgentError):
        return exc.retryable

    return isinstance(exc, (TimeoutError, ConnectionError))


def retry(policy: RetryPolicy) -> Callable[[Callable[P, R]],Callable[P, R]]:
    """
    Decorate a function with bounded exponential retry.

    The decorator retries only exceptions that are classified
    as retryable.
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:

        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:

            last_error: BaseException | None = None

            for attempt_number in range(policy.max_attempts):

                try:
                    return func(*args,**kwargs)
                except BaseException as exc:
                    last_error = exc

                    is_last_attempt: bool = (attempt_number == policy.max_attempts - 1)

                    if is_last_attempt or not is_retryable_exception(exc):
                        raise

                    delay_seconds: float = (policy.delay_for_attempt(attempt_number))

                    time.sleep(delay_seconds)

            assert last_error is not None

            raise last_error

        return wrapper

    return decorator