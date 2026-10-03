from __future__ import annotations

from enum import Enum
from typing import Any, Mapping


class ErrorCategory(str, Enum):
    """High-level categories used by runtime error handling."""

    LLM = "llm"
    RATE_LIMIT = "rate_limit"
    NETWORK = "network"
    TIMEOUT = "timeout"
    DATABASE = "database"
    SQL_VALIDATION = "sql_validation"
    PERMISSION = "permission"
    TOOL = "tool"
    PLANNING = "planning"
    REFLECTION = "reflection"
    CONFIGURATION = "configuration"
    UNKNOWN = "unknown"


class AgentError(Exception):
    """
    Base exception for errors that are meaningful to the agent runtime.
    """

    def __init__(
        self,
        message: str,
        category: ErrorCategory,
        *,
        retryable: bool = False,
        details: Mapping[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message)

        self.message: str = message
        self.category: ErrorCategory = category
        self.retryable: bool = retryable
        self.details: dict[str, Any] = dict(details or {})
        self.cause: BaseException | None = cause


class LLMError(AgentError):
    """Raised when an LLM operation fails."""

    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        details: Mapping[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(
            message,
            ErrorCategory.LLM,
            retryable=retryable,
            details=details,
            cause=cause,
        )


class RateLimitError(AgentError):
    """Raised when an external API rate limit is reached."""

    def __init__(
        self,
        message: str,
        *,
        retryable: bool = True,
        details: Mapping[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(
            message,
            ErrorCategory.RATE_LIMIT,
            retryable=retryable,
            details=details,
            cause=cause,
        )


class NetworkError(AgentError):
    """Raised when a network dependency is unavailable."""

    def __init__(
        self,
        message: str,
        *,
        retryable: bool = True,
        details: Mapping[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(
            message,
            ErrorCategory.NETWORK,
            retryable=retryable,
            details=details,
            cause=cause,
        )


class ExternalTimeoutError(AgentError):
    """Raised when an external dependency exceeds its timeout."""

    def __init__(
        self,
        message: str,
        *,
        retryable: bool = True,
        details: Mapping[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(
            message,
            ErrorCategory.TIMEOUT,
            retryable=retryable,
            details=details,
            cause=cause,
        )


class DatabaseError(AgentError):
    """Raised when database interaction fails."""

    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        details: Mapping[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(
            message,
            ErrorCategory.DATABASE,
            retryable=retryable,
            details=details,
            cause=cause,
        )


class SQLValidationError(AgentError):
    """Raised when generated SQL violates validation or security rules."""

    def __init__(
        self,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            ErrorCategory.SQL_VALIDATION,
            retryable=False,
            details=details,
        )


class PermissionDeniedError(AgentError):
    """Raised when a requested operation is not allowed."""

    def __init__(
        self,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            ErrorCategory.PERMISSION,
            retryable=False,
            details=details,
        )


class ToolExecutionError(AgentError):
    """Raised when a registered tool fails during execution."""

    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        details: Mapping[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(
            message,
            ErrorCategory.TOOL,
            retryable=retryable,
            details=details,
            cause=cause,
        )


class PlanningError(AgentError):
    """Raised when the planner cannot produce a valid execution plan."""

    def __init__(
        self,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            ErrorCategory.PLANNING,
            retryable=False,
            details=details,
        )


class ReflectionError(AgentError):
    """Raised when the reflection stage fails."""

    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        details: Mapping[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(
            message,
            ErrorCategory.REFLECTION,
            retryable=retryable,
            details=details,
            cause=cause,
        )


class ConfigurationError(AgentError):
    """Raised when application configuration is invalid."""

    def __init__(
        self,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            ErrorCategory.CONFIGURATION,
            retryable=False,
            details=details,
        )