from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, Mapping, Sequence

from agent_schemas import QuerySpec, RequestType
from core import LLMClient
from errors import PlanningError
from observability import AgentLogger
from tools.metadata_tools import MetadataTools, RelevantMetadata
from core.context import AgentContext
from prompts.query_spec_generator_prompt import (
    PROMPT_NAME,
    PROMPT_VERSION,
    QUERY_SPEC_GENERATOR_SYSTEM_PROMPT,
    build_query_spec_generator_prompt,
)
from openai.types.responses import FunctionToolParam
from .base_agent import BaseAgent, agent_lifecycle


class QuerySpecGeneratorAgent(BaseAgent[QuerySpec]):
    """Convert a natural-language request into a draft QuerySpec."""

    def __init__(
            self,
            *,
            llm_client: LLMClient,
            logger: AgentLogger,
            metadata_tools: MetadataTools,
            model_name: str | None = None,
    ) -> None:
        super().__init__(
            llm_client=llm_client,
            logger=logger,
            model_name=model_name,
        )
        self.metadata_tools: MetadataTools = metadata_tools

    agent_name: str = "query_spec_generator"
    prompt_name: str = PROMPT_NAME
    prompt_version: str = PROMPT_VERSION

    @agent_lifecycle
    def run(
            self,
            *,
            context: AgentContext,
            question: str,
            available_capabilities: Sequence[str] = (),
    ) -> QuerySpec:
        user_prompt: str = build_query_spec_generator_prompt(
            question=question,
            available_capabilities=list(available_capabilities or []),
        )
        context.set("_query_spec_metadata", None)

        result: QuerySpec = self._structured_with_tools(
            context=context,
            system_prompt=QUERY_SPEC_GENERATOR_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=QuerySpec,
            tools=[
                self._metadata_retrieval_tool_definition()
            ],
            tool_executor=lambda tool_name, arguments: (
                self._execute_tool(
                    context=context,
                    tool_name=tool_name,
                    arguments=arguments,
                )
            ),
            max_tool_calls=1,
        )

        if (
                result.request_type == RequestType.QUERY
                and not isinstance(context.get("_query_spec_metadata"), RelevantMetadata)
        ):
            raise PlanningError(
                "QuerySpec agent must retrieve metadata before "
                "returning a query specification."
            )

        return result

    def _start_metadata(self, kwargs: dict[str, object]) -> dict[str, object]:
        return {"question_length": len(str(kwargs.get("question", "")))}

    def _result_metadata(self, result: QuerySpec) -> dict[str, object]:
        return {
            "request_type": result.request_type.value,
            "metric": result.metric,
            "dimension_count": len(result.dimensions),
            "filter_count": len(result.filters),
            "needs_clarification": result.needs_clarification,
        }

    @staticmethod
    def _metadata_retrieval_tool_definition() -> FunctionToolParam:
        """Return the only tool available to the QuerySpec agent."""

        return {
            "type": "function",
            "name": "retrieve_metadata",
            "description": (
                "Retrieve relevant schema, relationships, business definitions, "
                "metric definitions, and glossary entries for the draft QuerySpec. "
                "Call this tool exactly once for query requests before returning "
                "the final grounded QuerySpec."
            ),
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "query_spec": {
                        "type": "string",
                        "description": (
                            "JSON-encoded draft QuerySpec. "
                            "The value must contain exactly the QuerySpec fields."
                        ),
                    },
                },
                "required": ["query_spec"],
                "additionalProperties": False,
            },
        }

    def _execute_tool(self, *, context: AgentContext, tool_name: str, arguments: Mapping[str, Any]) -> Any:
        """Execute the single tool exposed to the QuerySpec agent."""

        if tool_name != "retrieve_metadata":
            raise PlanningError(f"Unsupported QuerySpec tool: {tool_name}")

        raw_query_spec: Any = arguments.get("query_spec")

        if not isinstance(raw_query_spec, str):
            raise PlanningError("retrieve_metadata requires a JSON-encoded QuerySpec.")

        try:
            parsed_query_spec: Any = json.loads(raw_query_spec)
        except json.JSONDecodeError as exc:
            raise PlanningError("retrieve_metadata received invalid QuerySpec JSON.") from exc

        if not isinstance(parsed_query_spec, Mapping):
            raise PlanningError("retrieve_metadata QuerySpec JSON must decode to an object.")

        draft_query_spec: QuerySpec = QuerySpec.model_validate(parsed_query_spec)
        metadata: RelevantMetadata = self.metadata_tools.retrieve(draft_query_spec)
        context.set("_query_spec_metadata", metadata)

        return asdict(metadata)
