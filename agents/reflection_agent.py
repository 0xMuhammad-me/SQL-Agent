from __future__ import annotations

import time

from typing import Any, Mapping, Sequence

from agent_schemas import QuerySpec
from core.context import AgentContext
from agent_schemas.agent_outputs import ReflectionResult

from observability.logger import AgentLogger

from prompts.reflection_prompt import (
    PROMPT_VERSION as REFLECTION_PROMPT_VERSION,
    PROMPT_NAME as REFLECTION_PROMPT_NAME,
    REFLECTION_SYSTEM_PROMPT,
    build_reflection_prompt,
)

from .base_agent import BaseAgent, LLMClient


class ReflectionAgent(BaseAgent[ReflectionResult]):
    """Review semantic correctness after SQL execution."""

    agent_name: str = "reflection"
    prompt_name: str = REFLECTION_PROMPT_NAME
    prompt_version: str = REFLECTION_PROMPT_VERSION

    def __init__(self, *, llm_client: LLMClient, logger: AgentLogger, model_name: str | None = None) -> None:
        super().__init__(llm_client=llm_client, logger=logger, model_name=model_name)

    def run(
            self,
            *,
            context: AgentContext,
            question: str,
            query_spec: QuerySpec,
            sql: str,
            execution_result: Sequence[Mapping[str, Any]]
                              | Sequence[Any],
            execution_metadata: Mapping[str, Any],
            schema_context: Sequence[Mapping[str, Any]],
            business_context: Sequence[Mapping[str, Any]],
            metric_context: Sequence[Mapping[str, Any]],
    ) -> ReflectionResult:

        stage_name: str = "reflection"
        started_at: float = time.perf_counter()

        self._log_started(
            context=context,
            stage_name=stage_name,
            input_data={
                "question": question,
                "result_row_count": execution_metadata.get("row_count"),
                "execution_status": execution_metadata.get("status"),
                "truncated": execution_metadata.get("truncated", False, )
            },
        )

        try:

            user_prompt: str = (
                build_reflection_prompt(
                    question=question,
                    query_spec=query_spec,
                    sql=sql,
                    execution_result=list(execution_result),
                    execution_metadata=dict(execution_metadata),
                    schema_context=list(schema_context),
                    business_context=list(business_context),
                    metric_context=list(metric_context)
                )
            )

            result: ReflectionResult = (
                self.llm_client.generate_structured(
                    system_prompt=REFLECTION_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    response_model=ReflectionResult,
                    model=self.model_name,
                )
            )

            self._validate_output(result)

            elapsed_ms: float = (time.perf_counter() - started_at) * 1000

            self._log_completed(
                context=context,
                stage_name=stage_name,
                output_data={
                    "verdict": result.verdict,
                    "confidence":
                        result.confidence,
                    "issue_count":
                        len(result.issues),
                },
                latency_ms=elapsed_ms,
            )

            return result

        except Exception as exc:
            self._log_error(context=context, stage_name=stage_name, error=exc)

            raise self._raise_llm_error(exc) from exc

    @staticmethod
    def _validate_output(result: ReflectionResult) -> None:
        """Validate semantic consistency of reflection output."""

        if result.verdict == "pass":

            if result.issues:
                raise ValueError("Pass verdict cannot contain issues.")

            if result.repair_instructions:
                raise ValueError("Pass verdict cannot contain repair instructions.")

        if result.verdict != "repair":

            if result.repair_instructions:
                raise ValueError("Repair instructions require verdict='repair'.")
