from __future__ import annotations

import time

from typing import Any, Mapping, Sequence

from core.context import AgentContext
from agent_schemas.agent_outputs import SQLGenerationResult
from agent_schemas.query_spec import QuerySpec

from observability.logger import AgentLogger

from prompts.sql_generation_prompt import (
    PROMPT_VERSION as SQL_GENERATION_PROMPT_VERSION,
    PROMPT_NAME as SQL_GENERATION_PROMPT_NAME,
    SQL_GENERATION_SYSTEM_PROMPT,
    build_sql_generation_prompt,
)

from .base_agent import BaseAgent, LLMClient


class SQLGeneratorAgent(BaseAgent[SQLGenerationResult]):
    """Generate one parameterized read-only SQL statement."""

    agent_name: str = "sql_generator"
    prompt_name: str = SQL_GENERATION_PROMPT_NAME
    prompt_version: str = SQL_GENERATION_PROMPT_VERSION

    def __init__(self, *, llm_client: LLMClient, logger: AgentLogger, model_name: str | None = None) -> None:
        super().__init__(llm_client=llm_client, logger=logger, model_name=model_name)

    def run(
            self,
            *,
            context: AgentContext,
            question: str,
            query_spec: QuerySpec,
            schema_context: Sequence[Mapping[str, Any]],
            relationship_context: Sequence[str],
            business_context: Sequence[Mapping[str, Any]],
            metric_context: Sequence[Mapping[str, Any]],
            dialect: str = "postgresql",
    ) -> SQLGenerationResult:

        stage_name: str = "sql_generation"
        started_at: float = time.perf_counter()

        self._log_started(
            context=context,
            stage_name=stage_name,
            input_data={
                "question": question,
                "metric": query_spec.metric,
                "dimensions": query_spec.dimensions,
                "filter_count": len(
                    query_spec.filters
                ),
                "schema_table_count": len(
                    schema_context
                ),
            },
        )

        try:

            user_prompt: str = (
                build_sql_generation_prompt(
                    question=question,
                    query_spec=query_spec.model_dump(mode="json"),
                    schema_context=list(schema_context),
                    relationship_context=list(relationship_context),
                    business_context=list(business_context),
                    metric_context=list(metric_context),
                    dialect=dialect,
                )
            )

            result: SQLGenerationResult = (
                self.llm_client.generate_structured(
                    system_prompt=SQL_GENERATION_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    response_model=SQLGenerationResult,
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
                    "parameter_count": len(result.parameters)},
                latency_ms=elapsed_ms,
            )

            return result

        except Exception as exc:
            self._log_error(context=context, stage_name=stage_name, error=exc)
            raise self._raise_llm_error(exc) from exc

    @staticmethod
    def _validate_output(result: SQLGenerationResult) -> None:
        """Validate basic consistency of the model output."""

        if result.status == "query":
            if not result.sql:
                raise ValueError("Query status requires SQL.")

            if result.clarification_question:
                raise ValueError("Query status cannot contain a clarification question.")

            return

        if result.status == "clarification_required":

            if result.sql is not None:
                raise ValueError("Clarification status cannot contain SQL.")

            if result.parameters:
                raise ValueError("Clarification status cannot contain parameters.")

            if not result.clarification_question:
                raise ValueError("Clarification status requires a question.")
