from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import uuid

from core.context import AgentContext

from .workflow import SQLWorkflow, WorkflowResult


@dataclass(frozen=True, slots=True)
class AgentRequest:
    """Application-level request for the Text-to-SQL agent."""

    question: str
    user_id: str | None = None
    role_name: str | None = None


class SQLAgent:
    """Public application facade around the fixed SQL workflow."""

    def __init__(self, *, workflow: SQLWorkflow) -> None:
        self.workflow: SQLWorkflow = workflow

    def run(self, request: AgentRequest) -> WorkflowResult:
        if not request.question:
            raise ValueError("Question cannot be empty.")
        metadata: dict[str, Any] = {}
        if request.role_name:
            metadata["role_name"] = request.role_name
        context = AgentContext(
            trace_id=str(uuid.uuid4()),
            user_query=request.question.strip(),
            user_id=request.user_id,
            metadata=metadata,
        )
        return self.workflow.run(context=context)
