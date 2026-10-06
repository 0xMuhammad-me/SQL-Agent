from __future__ import annotations

from typing import Any, Mapping, Sequence

from agent_schemas import QuerySpec, ReflectionResult
from core.context import AgentContext
from prompts.reflection_prompt import (
    PROMPT_NAME,
    PROMPT_VERSION,
    REFLECTION_SYSTEM_PROMPT,
    build_reflection_prompt,
)

from .base_agent import BaseAgent, agent_lifecycle


class ReflectionAgent(BaseAgent[ReflectionResult]):
    """Review semantic correctness after ResultPolicy."""

    agent_name: str = "reflection"
    prompt_name: str = PROMPT_NAME
    prompt_version: str = PROMPT_VERSION

    @agent_lifecycle
    def run(
        self,
        *,
        context: AgentContext,
        question: str,
        query_spec: QuerySpec,
        sql: str,
        execution_result: Sequence[Mapping[str, Any]],
        execution_metadata: Mapping[str, Any],
        schema_context: Sequence[Mapping[str, object]],
        relationship_context: Sequence[str],
        business_context: Sequence[Mapping[str, object]],
        metric_context: Sequence[Mapping[str, object]],
        glossary_context: Sequence[Mapping[str, object]] = (),
    ) -> ReflectionResult:
        user_prompt: str = build_reflection_prompt(
            question=question,
            query_spec=query_spec,
            sql=sql,
            execution_result=execution_result,
            execution_metadata=execution_metadata,
            schema_context=schema_context,
            relationship_context=relationship_context,
            business_context=business_context,
            metric_context=metric_context,
            glossary_context=glossary_context,
        )
        return self._structured(
            context=context,
            system_prompt=REFLECTION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=ReflectionResult,
        )

    def _result_metadata(self, result: ReflectionResult) -> dict[str, object]:
        return {
            "verdict": result.verdict,
            "confidence": result.confidence,
            "issue_count": len(result.issues),
        }
