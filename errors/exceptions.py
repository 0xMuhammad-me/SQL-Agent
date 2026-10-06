from __future__ import annotations
from typing import Any


class AgentError(Exception):
    category = "unknown"

    def __init__(self, message: str, *, retryable: bool = False, cause: BaseException | None = None,
                 details: dict[str, Any] | None = None) -> None:
        super().__init__(message);
        self.retryable = retryable;
        self.cause = cause;
        self.details = dict(details or {})


class LLMError(AgentError): category = "llm"


class RateLimitError(LLMError):
    category = "rate_limit"

    def __init__(self, message: str, **kwargs: Any) -> None: kwargs.setdefault("retryable", True); super().__init__(
        message, **kwargs)


class NetworkError(LLMError):
    category = "network"

    def __init__(self, message: str, **kwargs: Any) -> None: kwargs.setdefault("retryable", True); super().__init__(
        message, **kwargs)


class ExternalTimeoutError(LLMError):
    category = "timeout"

    def __init__(self, message: str, **kwargs: Any) -> None: kwargs.setdefault("retryable", True); super().__init__(
        message, **kwargs)


class DatabaseError(AgentError): category = "database"


class SQLValidationError(AgentError): category = "sql_validation"


class PermissionDeniedError(AgentError): category = "permission"


class SecurityPolicyError(AgentError): category = "security"


class QueryCostError(AgentError): category = "query_cost"


class PlanningError(AgentError): category = "planning"


class ReflectionError(AgentError): category = "reflection"


class ConfigurationError(AgentError): category = "configuration"


class InfrastructureError(AgentError): category = "infrastructure"


class ResultPolicyError(AgentError): category = "result_policy"
