from __future__ import annotations

import uuid

from dataclasses import dataclass
from typing import Any

from core.context import AgentContext

from observability.events import (
    AgentEvent,
    EventType,
)

from observability.logger import AgentLogger

from .workflow import (
    SQLWorkflow,
    WorkflowResult,
)


@dataclass(frozen=True)
class AgentRequest:
    """
    Normalized request passed to the SQL Agent.
    """

    user_query: str
    user_id: str | None = None
    request_metadata: dict[str, Any] | None = None


class SQLAgent:
    """
    Public entry point for the production SQL agent.

    This class creates request-scoped context and delegates all workflow
    execution to SQLWorkflow.
    """

    agent_name: str = "sql_agent"

    def __init__(self, *, workflow: SQLWorkflow,  logger: AgentLogger ) -> None:

        self.workflow: SQLWorkflow = workflow
        self.logger: AgentLogger = logger

    def run(self,    request: AgentRequest) -> WorkflowResult:
        """
        Execute one end-to-end SQL agent request.

        Args:
            request:
                User request and optional application metadata.

        Returns:
            WorkflowResult containing status and answer.
        """

        trace_id: str = str(    uuid.uuid4())
        context: AgentContext = AgentContext(  trace_id=trace_id,  user_query=request.user_query)

        if request.user_id is not None:
            context.set_metadata("user_id",  request.user_id)

        if request.request_metadata:
            for key, value in (request.request_metadata.items()):
                context.set_metadata(key,   value)

        self.logger.log(
            AgentEvent(
                event_type=EventType.REQUEST_STARTED,
                trace_id=trace_id,
                agent_name=self.agent_name,
                stage_name="request",
                input_data={ "query_length":len(request.user_query)},
                metadata={"has_user_id":   request.user_id is not None},
            )
        )

        try:
            result: WorkflowResult = self.workflow.run( context=context)

            self.logger.log(
                AgentEvent(
                    event_type=EventType.REQUEST_COMPLETED,
                    trace_id=trace_id,
                    agent_name=self.agent_name,
                    stage_name="request",
                    output_data={
                        "status":result.status.value,
                        "repair_attempts": result.repair_attempts,
                        "execution_ms": result.execution_ms,
                        "sql_generated":result.sql is not None},
                    status="success",
                )
            )

            return result

        except Exception as exc:

            self.logger.log(
                AgentEvent(
                    event_type=EventType.ERROR,
                    trace_id=trace_id,
                    agent_name=self.agent_name,
                    stage_name="request",
                    status="error",
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
            )

            raise