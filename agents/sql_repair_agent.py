from __future__ import annotations

import time

from typing import Any, Mapping, Sequence

from core.context import AgentContext
from errors.exceptions import PlanningError
from agent_schemas.agent_outputs import SQLRepairResult

from observability.logger import AgentLogger

from prompts.sql_repair_prompt import (
    PROMPT_VERSION as SQL_REPAIR_PROMPT_VERSION,
    PROMPT_NAME as SQL_REPAIR_PROMPT_NAME,
    SQL_REPAIR_SYSTEM_PROMPT,
    build_sql_repair_prompt,
)

from .base_agent import BaseAgent, LLMClient

REPAIRABLE_ISSUE_TYPES: frozenset[str] = frozenset(
    {
        "syntax",
        "schema",
        "semantic",
        "join",
        "aggregation",
        "date_logic",
        "business_rule",
        "metric",
    }
)

NON_REPAIRABLE_ISSUE_TYPES: frozenset[str] = frozenset(
    {
        "security",
        "permission",
        "privacy",
        "infrastructure",
    }
)


class SQLRepairAgent(
    BaseAgent[SQLRepairResult]
):
    """Repair SQL only for explicitly repairable SQL-related issues."""

    agent_name: str = "sql_repair"
    prompt_name: str = SQL_REPAIR_PROMPT_NAME
    prompt_version: str = SQL_REPAIR_PROMPT_VERSION

    def __init__(self, *, llm_client: LLMClient, logger: AgentLogger, model_name: str | None = None) -> None:
        super().__init__(llm_client=llm_client, logger=logger, model_name=model_name)

    def run(
            self,
            *,
            context: AgentContext,
            question: str,
            current_sql: str,
            current_parameters: Mapping[str, Any],
            issues: Sequence[Mapping[str, Any]],
            schema_context: Sequence[Mapping[str, Any]],
            relationship_context: Sequence[str],
            business_context: Sequence[Mapping[str, Any]],
            metric_context: Sequence[Mapping[str, Any]],
            dialect: str = "postgresql",
    ) -> SQLRepairResult:

        stage_name: str = "sql_repair"
        self._validate_repair_issues(issues)

        started_at: float = time.perf_counter()

        self._log_started(
            context=context,
            stage_name=stage_name,
            input_data={
                "issue_count": len(issues),
                "issue_types": sorted(
                    {
                        str(issue.get("type"))
                        for issue in issues
                    }
                ),
            },
        )

        try:

            user_prompt: str = (
                build_sql_repair_prompt(
                    question=question,
                    current_sql=current_sql,
                    current_parameters=dict(current_parameters),
                    issues=list(issues),
                    schema_context=list(schema_context),
                    relationship_context=list(relationship_context),
                    business_context=list(business_context),
                    metric_context=list(metric_context),
                    dialect=dialect,
                )
            )

            result: SQLRepairResult = (
                self.llm_client.generate_structured(
                    system_prompt=(
                        SQL_REPAIR_SYSTEM_PROMPT
                    ),
                    user_prompt=user_prompt,
                    response_model=SQLRepairResult,
                    model=self.model_name,
                )
            )

            self._validate_output(result)
            elapsed_ms: float = (time.perf_counter() - started_at) * 1000

            self._log_completed(
                context=context,
                stage_name=stage_name,
                output_data={
                    "status": result.status,
                    "sql_present": result.sql is not None,
                    "parameter_names": list(result.parameters.keys()),
                },
                latency_ms=elapsed_ms,
            )

            return result

        except Exception as exc:
            self._log_error(context=context, stage_name=stage_name, error=exc)
            raise self._raise_llm_error(exc) from exc

    @staticmethod
    def _validate_repair_issues(issues: Sequence[Mapping[str, Any]]) -> None:
        """Prevent non-repairable failures from reaching the repair model."""

        for issue in issues:

            issue_type: str = str(
                issue.get("type", "")
            ).lower()

            if issue_type in NON_REPAIRABLE_ISSUE_TYPES:
                raise PlanningError("Non-repairable issue cannot be sent to SQL repair agent.")

            if issue_type not in REPAIRABLE_ISSUE_TYPES:
                raise PlanningError(f"Unsupported repair issue type: {issue_type}")

    @staticmethod
    def _validate_output(result: SQLRepairResult) -> None:
        """Validate consistency of repair model output."""

        if result.status == "repaired":

            if not result.sql:
                raise ValueError("Repaired status requires SQL.")

            if result.clarification_question:
                raise ValueError("Repaired status cannot contain clarification question.")

            return

        if result.status == "clarification_required":

            if result.sql is not None:
                raise ValueError("Clarification status cannot contain SQL.")

            if result.parameters:
                raise ValueError("Clarification status cannot contain parameters.")

            if not result.clarification_question:
                raise ValueError("Clarification status requires a question.")

            return

        if result.status == "cannot_repair":

            if result.sql is not None:
                raise ValueError("Cannot-repair status cannot contain SQL.")

            if result.parameters:
                raise ValueError("Cannot-repair status cannot contain parameters.")
