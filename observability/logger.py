from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Mapping

from .events import AgentEvent


_SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "password",
        "api_key",
        "authorization",
        "access_token",
        "refresh_token",
        "secret",
        "credential",
    }
)

_SENSITIVE_CONTENT_KEYS: frozenset[str] = frozenset(
    {
        "prompt",
        "system_prompt",
        "user_prompt",
        "question",
        "user_question",
        "query",
        "user_query",
        "sql",
        "generated_sql",
        "current_sql",
    }
)

_MAX_STRING_LENGTH: int = 2000
_MAX_COLLECTION_ITEMS: int = 50


class AgentLogger:
    """Structured logger with lightweight central redaction and truncation."""

    def __init__(
        self,
        *,
        service_name: str = "sql-agent",
        level: str = "INFO",
        log_file_path: str = "logs/sql_agent.log",
        enable_console: bool = True,
        enable_file: bool = True,
        json_logging: bool = True,
    ) -> None:
        self.logger: logging.Logger = logging.getLogger(service_name)
        self.logger.setLevel(level.upper())
        self.logger.propagate = False
        self._json_logging: bool = json_logging

        marker: str = "sql_agent_handler"
        if any(getattr(handler, marker, False) for handler in self.logger.handlers):
            return

        formatter: logging.Formatter = logging.Formatter("%(message)s")
        if enable_console:
            console_handler: logging.Handler = logging.StreamHandler()
            setattr(console_handler, marker, True)
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
        if enable_file:
            Path(log_file_path).parent.mkdir(parents=True, exist_ok=True)
            file_handler: logging.Handler = logging.FileHandler(log_file_path)
            setattr(file_handler, marker, True)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

    def log(self, event: AgentEvent) -> None:
        payload: dict[str, Any] = {
            "event_type": event.event_type.value,
            "trace_id": event.trace_id,
            "timestamp": event.timestamp.isoformat(),
            "agent_name": event.agent_name,
            "stage_name": event.stage_name,
            "input_data": self._sanitize(event.input_data),
            "output_data": self._sanitize(event.output_data),
            "latency_ms": event.latency_ms,
            "model_name": event.model_name,
            "prompt_version": event.prompt_version,
            "token_usage": event.token_usage,
            "status": event.status,
            "error_type": event.error_type,
            "error_message": self._sanitize(event.error_message),
            "metadata": self._sanitize(event.metadata),
        }
        if self._json_logging:
            self.logger.info(json.dumps(payload, ensure_ascii=False, default=str))
        else:
            self.logger.info(
                "%s [%s] %s",
                payload["event_type"],
                payload["trace_id"],
                payload.get("error_message") or payload.get("output_data"),
            )

    @classmethod
    def _sanitize(cls, value: Any, *, key: str | None = None) -> Any:
        if key and key.lower() in _SENSITIVE_KEYS:
            return "[REDACTED]"
        if key and key.lower() in _SENSITIVE_CONTENT_KEYS:
            if isinstance(value, str):
                return f"[OMITTED:{len(value)} chars]"
        if isinstance(value, str):
            return value if len(value) <= _MAX_STRING_LENGTH else value[:_MAX_STRING_LENGTH] + "…"
        if isinstance(value, Mapping):
            return {
                str(item_key): cls._sanitize(item_value, key=str(item_key))
                for item_key, item_value in list(value.items())[:_MAX_COLLECTION_ITEMS]
            }
        if isinstance(value, (list, tuple, set, frozenset)):
            values = list(value)[:_MAX_COLLECTION_ITEMS]
            return [cls._sanitize(item) for item in values]
        return value

