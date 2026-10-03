from __future__ import annotations

import time

from typing import Any, Mapping, Sequence

from core.context import AgentContext

from observability import AgentEvent, EventType
from observability.logger import AgentLogger

from prompts.answer_prompt import (
    PROMPT_VERSION as ANSWER_PROMPT_VERSION,
    PROMPT_NAME as ANSWER_PROMPT_NAME,
    ANSWER_SYSTEM_PROMPT,
    build_answer_prompt,
)

from .base_agent import LLMClient


class AnswerAgent:
    """
    Generate the final user-facing answer from a sanitized result.

    This agent intentionally returns plain text because no downstream
    machine-readable decision is required.
    """
    agent_name: str = "answer"
    prompt_name: str = ANSWER_PROMPT_NAME
    prompt_version: str = ANSWER_PROMPT_VERSION

    def __init__(self, *, llm_client: LLMClient, logger: AgentLogger, model_name: str | None = None) -> None:
        self.llm_client: LLMClient = llm_client
        self.logger: AgentLogger = logger
        self.model_name: str | None = model_name

    def run(
            self,
            *,
            context: AgentContext,
            question: str,
            result: Sequence[Mapping[str, Any]]
                    | Sequence[Any],
            result_metadata: Mapping[str, Any],
    ) -> str:

        stage_name: str = "answer_generation"
        started_at: float = time.perf_counter()

        self.logger.log(
            AgentEvent(
                event_type=EventType.AGENT_STARTED,
                trace_id=context.trace_id,
                agent_name=self.agent_name,
                stage_name=stage_name,
                input_data={
                    "question": question,
                    "row_count":
                        result_metadata.get("row_count"),
                    "status":
                        result_metadata.get("status"),
                },
                model_name=self.model_name,
                prompt_version=self.prompt_version,
                metadata={"prompt_name": self.prompt_name},
            )
        )

        try:

            user_prompt: str = (
                build_answer_prompt(question=question, result=list(result), result_metadata=dict(result_metadata))
            )

            answer: str = (
                self.llm_client.generate_text(
                    system_prompt=(
                        ANSWER_SYSTEM_PROMPT
                    ),
                    user_prompt=user_prompt,
                    model=self.model_name,
                )
            )

            answer = answer.strip()

            if not answer:
                raise ValueError(
                    "Answer agent returned empty output."
                )

            elapsed_ms: float = (time.perf_counter() - started_at) * 1000

            self.logger.log(
                AgentEvent(
                    event_type=EventType.AGENT_COMPLETED,
                    trace_id=context.trace_id,
                    agent_name=self.agent_name,
                    stage_name=stage_name,
                    output_data={"answer_length": len(answer)},
                    latency_ms=elapsed_ms,
                    model_name=self.model_name,
                    prompt_version=self.prompt_version,
                    metadata={"prompt_name": self.prompt_name},
                )
            )

            return answer

        except Exception as exc:

            self.logger.log(
                AgentEvent(
                    event_type=EventType.ERROR,
                    trace_id=context.trace_id,
                    agent_name=self.agent_name,
                    stage_name=stage_name,
                    status="error",
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    model_name=self.model_name,
                    prompt_version=self.prompt_version,
                    metadata={"prompt_name": self.prompt_name},
                )
            )

            raise
