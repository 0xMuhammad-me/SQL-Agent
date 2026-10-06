from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from agent_schemas import QuerySpec
from .base import BASE_SYSTEM_PROMPT

PROMPT_NAME: str = "reflection"
PROMPT_VERSION: str = "v3.1.0"

REFLECTION_SYSTEM_PROMPT: str = BASE_SYSTEM_PROMPT + """

You are the Senior Reflection Agent.
You run only after deterministic SQL validation, security, permissions,
cost checks, database execution, and ResultPolicy.
Your role is semantic verification only.
Never authorize execution or bypass a policy.
Any repaired SQL is untrusted and will pass through every deterministic gate again.
""".strip()


def build_reflection_prompt(
        *,
        question: str,
        query_spec: QuerySpec,
        sql: str,
        execution_result: Sequence[Mapping[str, Any]],
        execution_metadata: Mapping[str, Any],
        schema_context: Sequence[Mapping[str, Any]],
        relationship_context: Sequence[str],
        business_context: Sequence[Mapping[str, Any]],
        metric_context: Sequence[Mapping[str, Any]],
        glossary_context: Sequence[Mapping[str, Any]] = (),
) -> str:
    return f"""
Determine whether the executed query semantically answers the request.
Check intent, metric, grain, joins, aggregation, date logic, business rules,
and result sanity. Do not treat authorization, security, privacy, or cost
failures as semantic repair opportunities.

USER
{question}

QUERYSPEC
{json.dumps(query_spec.model_dump(mode='json'), ensure_ascii=False, indent=2, default=str)}

SQL
{sql}

RESULT
{json.dumps(list(execution_result), ensure_ascii=False, indent=2, default=str)}

EXECUTION
{json.dumps(dict(execution_metadata), ensure_ascii=False, indent=2, default=str)}

SCHEMA
{json.dumps(list(schema_context), ensure_ascii=False, indent=2, default=str)}

RELATIONSHIPS
{json.dumps(list(relationship_context), ensure_ascii=False, indent=2, default=str)}

BUSINESS
{json.dumps(list(business_context), ensure_ascii=False, indent=2, default=str)}

METRICS
{json.dumps(list(metric_context), ensure_ascii=False, indent=2, default=str)}

GLOSSARY
{json.dumps(list(glossary_context), ensure_ascii=False, indent=2, default=str)}

OUTPUT CONTRACT

Return exactly one JSON object with these fields:

{{
  "verdict": "pass",
  "confidence": 0.0,
  "issues": [],
  "repair_instructions": [],
  "clarification_question": null
}}

VERDICT RULES

1. verdict="pass"
   - issues MUST be []
   - repair_instructions MUST be []
   - clarification_question MUST be null

2. verdict="repair"
   - issues MUST contain at least one concrete issue
   - repair_instructions MUST contain at least one actionable instruction
   - clarification_question MUST be null
   - Do not return replacement SQL

3. verdict="clarify"
   - clarification_question MUST be non-null
   - issues MUST be []
   - repair_instructions MUST be []

4. verdict="reject"
   - issues MAY contain diagnostic issues
   - repair_instructions MUST be []
   - clarification_question MUST be null

5. verdict="inconclusive"
   - repair_instructions MUST be []
   - clarification_question MUST be null
   - issues MAY contain diagnostic evidence explaining why the result
     cannot be assessed confidently

IMPORTANT

When the query is semantically correct and execution succeeded, return
exactly this shape:

{{
  "verdict": "pass",
  "confidence": 0.99,
  "issues": [],
  "repair_instructions": [],
  "clarification_question": null
}}

Do not attach any issue or repair instruction to a pass verdict.

Do not return a repair verdict unless a concrete SQL-related correction
is actually required by the evidence.

Do not include replacement SQL in any response.
""".strip()
