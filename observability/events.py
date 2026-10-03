from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class EventType(str, Enum):
    """
    Defines all observable events inside the agent workflow.
    """

    REQUEST_STARTED = "request_started"
    REQUEST_COMPLETED = "request_completed"

    AGENT_STARTED = "agent_started"
    AGENT_COMPLETED = "agent_completed"

    TOOL_STARTED = "tool_started"
    TOOL_COMPLETED = "tool_completed"

    SQL_GENERATED = "sql_generated"
    SQL_VALIDATED = "sql_validated"
    SQL_EXECUTED = "sql_executed"

    REFLECTION_STARTED = "reflection_started"
    REFLECTION_COMPLETED = "reflection_completed"

    ERROR = "error"


@dataclass
class AgentEvent:
    """
    Represents a single observable event.

    Each important action in the system should create an event.
    """

    event_type: EventType
    trace_id: str
    timestamp: datetime = field(default_factory=datetime.now())

    # Agent metadata
    agent_name: Optional[str] = None
    stage_name: Optional[str] = None

    # Tool metadata
    tool_name: Optional[str] = None

    # Execution data
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)

    # Performance
    latency_ms: Optional[float] = None

    # LLM information
    model_name: Optional[str] = None
    prompt_version: Optional[str] = None
    token_usage: Dict[str, int] = field(default_factory=dict)

    # Result state
    status: str = "success"
    error_type: Optional[str] = None
    error_message: Optional[str] = None

    # Extra extensible metadata
    metadata: Dict[str, Any] = field(default_factory=dict)