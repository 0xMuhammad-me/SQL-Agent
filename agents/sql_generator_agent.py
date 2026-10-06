from __future__ import annotations

from typing import Mapping, Sequence

from agent_schemas import QuerySpec, SQLGenerationResult
from core.context import AgentContext
from prompts.sql_generation_prompt import (
    PROMPT_NAME,
    PROMPT_VERSION,
    SQL_GENERATION_SYSTEM_PROMPT,
    build_sql_generation_prompt,
)

from .base_agent import BaseAgent, agent_lifecycle


class SQLGeneratorAgent(BaseAgent[SQLGenerationResult]):
    """Generate one parameterized read-only SQL statement."""

    agent_name: str = "sql_generator"
    prompt_name: str = PROMPT_NAME
    prompt_version: str = PROMPT_VERSION

    @agent_lifecycle
    def run(
            self,
            *,
            context: AgentContext,
            question: str,
            query_spec: QuerySpec,
            schema_context: Sequence[Mapping[str, object]],
            relationship_context: Sequence[str],
            business_context: Sequence[Mapping[str, object]],
            metric_context: Sequence[Mapping[str, object]],
            glossary_context: Sequence[Mapping[str, object]] = (),
            dialect: str = "postgresql",
    ) -> SQLGenerationResult:
        user_prompt: str = build_sql_generation_prompt(
            question=question,
            query_spec=query_spec.model_dump(mode="json"),
            schema_context=schema_context,
            relationship_context=relationship_context,
            business_context=business_context,
            metric_context=metric_context,
            glossary_context=glossary_context,
            dialect=dialect,
        )
        result: SQLGenerationResult = self._structured(
            context=context,
            system_prompt=SQL_GENERATION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=SQLGenerationResult,
        )
        if result.status == "query" and not result.sql:
            raise ValueError("Query generation returned an empty SQL statement.")
        return result

    def _start_metadata(self, kwargs: dict[str, object]) -> dict[str, object]:
        raw_query_spec: object = kwargs.get("query_spec")
        query_spec: QuerySpec | None = (
            raw_query_spec
            if isinstance(raw_query_spec, QuerySpec)
            else None
        )

        raw_question: object = kwargs.get("question")
        question: str = (
            raw_question
            if isinstance(raw_question, str)
            else ""
        )

        raw_schema_context: object = kwargs.get("schema_context", ())
        schema_context: Sequence[Mapping[str, object]] = (
            raw_schema_context
            if isinstance(raw_schema_context, Sequence)
               and not isinstance(raw_schema_context, (str, bytes))
            else ()
        )

        return {
            "question_length": len(question),
            "metric": query_spec.metric if query_spec else None,
            "dimension_count": (
                len(query_spec.dimensions)
                if query_spec
                else None
            ),
            "schema_table_count": len(schema_context),
            "schema_tables": [
                str(item.get("name"))
                for item in schema_context
                if isinstance(item, Mapping)
                   and item.get("name") is not None
            ],
        }

    def _result_metadata(self, result: SQLGenerationResult) -> dict[str, object]:
        return {
            "status": result.status,
            "sql_present": result.sql is not None,
            "sql": result.sql,
            "parameters": [
                {
                    "name": parameter.name,
                    "value": parameter.value,
                }
                for parameter in result.parameters
            ],
            "parameter_count": len(result.parameters),
            "clarification_question": result.clarification_question,
        }
