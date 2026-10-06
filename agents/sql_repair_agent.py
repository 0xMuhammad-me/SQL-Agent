from __future__ import annotations

from typing import Any, Mapping, Sequence

from agent_schemas import SQLRepairResult, QuerySpec
from core.context import AgentContext
from prompts.sql_repair_prompt import (
    PROMPT_NAME,
    PROMPT_VERSION,
    SQL_REPAIR_SYSTEM_PROMPT,
    build_sql_repair_prompt,
)

from .base_agent import BaseAgent, agent_lifecycle


class SQLRepairAgent(BaseAgent[SQLRepairResult]):
    """Repair SQL defects without becoming a security policy authority."""

    agent_name: str = "sql_repair"
    prompt_name: str = PROMPT_NAME
    prompt_version: str = PROMPT_VERSION

    @agent_lifecycle
    def run(
            self,
            *,
            context: AgentContext,
            question: str,
            query_spec: QuerySpec,
            current_sql: str,
            current_parameters: Mapping[str, Any],
            issues: Sequence[Mapping[str, Any]],
            schema_context: Sequence[Mapping[str, object]],
            relationship_context: Sequence[str],
            business_context: Sequence[Mapping[str, object]],
            metric_context: Sequence[Mapping[str, object]],
            repair_instructions: Sequence[str] = (),
            glossary_context: Sequence[Mapping[str, object]] = (),
            dialect: str = "postgresql",
    ) -> SQLRepairResult:
        user_prompt: str = build_sql_repair_prompt(
            question=question,
            query_spec=query_spec,
            current_sql=current_sql,
            repair_instructions=repair_instructions,
            current_parameters=current_parameters,
            issues=issues,
            schema_context=schema_context,
            relationship_context=relationship_context,
            business_context=business_context,
            metric_context=metric_context,
            glossary_context=glossary_context,
            dialect=dialect,
        )
        return self._structured(
            context=context,
            system_prompt=SQL_REPAIR_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=SQLRepairResult,
        )

    def _result_metadata(self, result: SQLRepairResult) -> dict[str, object]:
        return {
            "status": result.status,
            "sql_present": result.sql is not None,
            "parameter_names": [parameter.name for parameter in result.parameters],
            "parameter_count": len(result.parameters),
            "clarification_question": result.clarification_question
        }
