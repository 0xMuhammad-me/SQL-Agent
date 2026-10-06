from __future__ import annotations

from typing import Any, Mapping, Sequence

from agent_schemas import QuerySpec, SQLReviewResult
from core.context import AgentContext
from prompts.sql_review_prompt import (
    PROMPT_NAME,
    PROMPT_VERSION,
    SQL_REVIEW_SYSTEM_PROMPT,
    build_sql_review_prompt,
)

from .base_agent import BaseAgent, agent_lifecycle


class SQLReviewAgent(BaseAgent[SQLReviewResult]):
    """Review generated SQL for semantic correctness before deterministic gates."""

    agent_name: str = "sql_review"
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
            parameters: Mapping[str, Any],
            schema_context: Sequence[Mapping[str, object]],
            relationship_context: Sequence[str],
            business_context: Sequence[Mapping[str, object]],
            metric_context: Sequence[Mapping[str, object]],
            glossary_context: Sequence[Mapping[str, object]] = (),
            dialect: str = "postgresql",
    ) -> SQLReviewResult:
        user_prompt: str = build_sql_review_prompt(
            question=question,
            query_spec=query_spec,
            sql=sql,
            parameters=parameters,
            schema_context=schema_context,
            relationship_context=relationship_context,
            business_context=business_context,
            metric_context=metric_context,
            glossary_context=glossary_context,
            dialect=dialect,
        )

        return self._structured(
            context=context,
            system_prompt=SQL_REVIEW_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=SQLReviewResult,
        )

    def _start_metadata(self,kwargs: dict[str, object]) -> dict[str, object]:
        query_spec: QuerySpec | None = (
            kwargs.get("query_spec")
            if isinstance(kwargs.get("query_spec"), QuerySpec)
            else None
        )

        return {
            "question_length": len(str(kwargs.get("question", ""))),
            "metric": query_spec.metric if query_spec else None,
            "dimension_count": (
                len(query_spec.dimensions) if query_spec else None
            ),
            "filter_count": (
                len(query_spec.filters) if query_spec else None
            ),
        }

    def _result_metadata(self,result: SQLReviewResult) -> dict[str, object]:
        return {
            "verdict": result.verdict,
            "confidence": result.confidence,
            "issue_count": len(result.issues),
            "issue_types": [
                issue.type
                for issue in result.issues
            ],
            "issues": [
                issue.description
                for issue in result.issues
            ],
            "repair_instruction_count": len(
                result.repair_instructions
            ),
            "repair_instructions": list(
                result.repair_instructions
            ),
            "clarification_question": result.clarification_question,
        }
