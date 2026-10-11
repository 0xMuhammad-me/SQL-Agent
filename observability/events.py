from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class EventType(str, Enum):
    REQUEST_STARTED = "request_started"
    REQUEST_COMPLETED = "request_completed"

    AGENT_STARTED = "agent_started"
    AGENT_COMPLETED = "agent_completed"

    STAGE_STARTED = "stage_started"
    STAGE_COMPLETED = "stage_completed"
    STAGE_FAILED = "stage_failed"

    QUERY_SPEC_VALIDATED = "query_spec_validated"
    SQL_VALIDATED = "sql_validated"
    SQL_FIREWALL_CHECKED = "sql_firewall_checked"
    PERMISSION_CHECKED = "permission_checked"
    QUERY_COST_CHECKED = "query_cost_checked"
    SQL_EXECUTED = "sql_executed"
    RESULT_POLICY_APPLIED = "result_policy_applied"
    REFLECTION_COMPLETED = "reflection_completed"

    ERROR = "error"


@dataclass(slots=True)
class AgentEvent:
    event_type: EventType
    trace_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    agent_name: str | None = None
    stage_name: str | None = None
    input_data: dict[str, Any] = field(default_factory=dict)
    output_data: dict[str, Any] = field(default_factory=dict)
    latency_ms: float | None = None
    model_name: str | None = None
    prompt_version: str | None = None
    token_usage: dict[str, int] = field(default_factory=dict)
    status: str = "success"
    error_type: str | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    question_id: str | None = None