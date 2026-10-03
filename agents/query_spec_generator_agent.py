from __future__ import annotations

import time

from typing import Any, Mapping, Sequence
from core.context import AgentContext
from errors.exceptions import PlanningError

from agent_schemas.query_spec import QuerySpec
from prompts.query_spec_generator_prompt import (
    PROMPT_VERSION as QUERY_SPEC_GENERATOR_PROMPT_VERSION,
    PROMPT_NAME as QUERY_SPEC_GENERATOR_PROMPT_NAME,
    QUERY_SPEC_GENERATOR_SYSTEM_PROMPT,
    build_query_spec_generator_prompt,
)

from observability.logger import AgentLogger
from .base_agent import BaseAgent, LLMClient


class QuerySpecGeneratorAgent(BaseAgent[QuerySpec]):
    """Convert a natural-language request into a validated QuerySpec."""

    agent_name: str = "query_spec_generator"
    prompt_name: str = QUERY_SPEC_GENERATOR_PROMPT_NAME
    prompt_version: str = QUERY_SPEC_GENERATOR_PROMPT_VERSION

    def __init__(self, *, llm_client: LLMClient, logger: AgentLogger, model_name: str | None = None) -> None:
        super().__init__(llm_client=llm_client, logger=logger, model_name=model_name)

    def run(
            self,
            *,
            context: AgentContext,
            question: str,
            metric_catalog: Sequence[Mapping[str, Any]],
            business_catalog: Sequence[Mapping[str, Any]],
            glossary: Sequence[Mapping[str, Any]] | None = None,
            available_capabilities: Sequence[str] | None = None,
    ) -> QuerySpec:

        stage_name: str = "query_spec_generation"
        started_at: float = time.perf_counter()

        self._log_started(
            context=context,
            stage_name=stage_name,
            input_data={
                "question": question,
                "metric_count": len(metric_catalog),
                "business_definition_count": len(
                    business_catalog
                ),
            },
        )

        try:

            user_prompt: str = (
                build_query_spec_generator_prompt(question=question, metric_catalog=list(metric_catalog),
                                                  business_catalog=list(business_catalog),
                                                  glossary=list(glossary or []),
                                                  available_capabilities=list(available_capabilities or []),
                                                  )
            )

            query_spec: QuerySpec = (
                self.llm_client.generate_structured(
                    system_prompt=QUERY_SPEC_GENERATOR_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    response_model=QuerySpec,
                    model=self.model_name,
                )
            )

            query_spec.validate_state_consistency()
            elapsed_ms: float = (time.perf_counter() - started_at) * 1000
            self._log_completed(context=context, stage_name=stage_name,
                                output_data={
                                    "request_type": query_spec.request_type.value,
                                    "intent": query_spec.intent,
                                    "metric": query_spec.metric,
                                    "dimension_count": len(query_spec.dimensions),
                                    "filter_count": len(query_spec.filters),
                                    "needs_clarification": query_spec.needs_clarification},
                                latency_ms=elapsed_ms)

            return query_spec

        except PlanningError as exc:
            self._log_error(context=context, stage_name=stage_name, error=exc)
            raise

        except Exception as exc:
            self._log_error(context=context, stage_name=stage_name, error=exc)
            raise self._raise_llm_error(exc) from exc
