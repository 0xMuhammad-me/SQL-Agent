from __future__ import annotations

from typing import Any, Mapping, Sequence

from core.context import AgentContext
from prompts.answer_prompt import (
    ANSWER_SYSTEM_PROMPT,
    PROMPT_NAME,
    PROMPT_VERSION,
    build_answer_prompt,
)

from .base_agent import BaseAgent, agent_lifecycle


class AnswerAgent(BaseAgent[str]):
    """Generate the final user-facing answer from sanitized evidence."""

    agent_name: str = "answer"
    prompt_name: str = PROMPT_NAME
    prompt_version: str = PROMPT_VERSION

    @agent_lifecycle
    def run(
        self,
        *,
        context: AgentContext,
        question: str,
        result: Sequence[Mapping[str, Any]],
        result_metadata: Mapping[str, Any],
    ) -> str:
        user_prompt: str = build_answer_prompt(
            question=question,
            result=result,
            result_metadata=result_metadata,
        )
        answer: str = self._text(
            context=context,
            system_prompt=ANSWER_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        ).strip()
        if not answer:
            raise ValueError("Answer agent returned empty output.")
        return answer

    def _result_metadata(self, result: str) -> dict[str, object]:
        return {"answer_length": len(result)}
