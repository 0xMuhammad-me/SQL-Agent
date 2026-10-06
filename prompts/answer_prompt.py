from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from .base import BASE_SYSTEM_PROMPT

PROMPT_NAME: str = "answer"
PROMPT_VERSION: str = "v1.0.0"

ANSWER_SYSTEM_PROMPT: str = BASE_SYSTEM_PROMPT + """

You are the Final Answer Agent.
Use only the sanitized result and trusted execution metadata.
Do not invent facts or expose SQL unless explicitly requested.
""".strip()


def build_answer_prompt(
        question: str,
        result: Sequence[Mapping[str, Any]],
        *,
        result_metadata: Mapping[str, Any] | None = None,
) -> str:
    return f"""
USER QUESTION
{question}

SANITIZED RESULT
{json.dumps(list(result), ensure_ascii=False, indent=2, default=str)}

RESULT METADATA
{json.dumps(dict(result_metadata or {}), ensure_ascii=False, indent=2, default=str)}

Answer concisely using only the supplied evidence.
""".strip()
