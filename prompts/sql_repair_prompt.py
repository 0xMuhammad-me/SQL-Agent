from __future__ import annotations

import json

from typing import Any, Mapping, Sequence

from .base import (
    BASE_SYSTEM_PROMPT,
    READ_ONLY_SQL_RULES,
    SEMANTIC_SQL_RULES,
)

PROMPT_NAME: str = "sql_repair"
PROMPT_VERSION: str = "v1.0.0"

SQL_REPAIR_SYSTEM_PROMPT: str = (
        BASE_SYSTEM_PROMPT
        + """

You are the Senior SQL Repair Agent.

Your task is to repair an existing SQL query based on a concrete,
SQL-related validation error, execution error, or reflection finding.

Preserve the original user intent and fix only the identified problem.
""".strip()
)


def build_sql_repair_prompt(
        question: str,
        current_sql: str,
        current_parameters: Mapping[str, Any],
        issues: Sequence[Mapping[str, Any]],
        schema_context: Sequence[Mapping[str, Any]],
        relationship_context: Sequence[str],
        business_context: Sequence[Mapping[str, Any]],
        metric_context: Sequence[Mapping[str, Any]],
        *,
        dialect: str = "postgresql",
) -> str:
    """
    Build the SQL repair prompt.

    The backend should call this prompt only for repairable SQL issues.
    Do not send raw infrastructure, authorization, privacy, or policy
    failures to the repair model.
    """

    parameters_json: str = json.dumps(dict(current_parameters), ensure_ascii=False, indent=2, default=str)
    issues_json: str = json.dumps(list(issues), ensure_ascii=False, indent=2, default=str)
    schema_json: str = json.dumps(list(schema_context), ensure_ascii=False, indent=2, default=str)
    relationships_json: str = json.dumps(list(relationship_context), ensure_ascii=False, indent=2)
    business_json: str = json.dumps(list(business_context), ensure_ascii=False, indent=2, default=str)
    metrics_json: str = json.dumps(list(metric_context), ensure_ascii=False, indent=2, default=str)

    return f"""
TARGET DIALECT

{dialect}

{READ_ONLY_SQL_RULES}

{SEMANTIC_SQL_RULES}

REPAIR RULES

1. Preserve the original analytical intent.
2. Fix only the identified SQL-related problems.
3. Do not invent tables or columns.
4. Do not introduce unsupported relationships.
5. Do not circumvent security validation.
6. Do not attempt to repair infrastructure, connection, timeout,
   authorization, privacy, or policy failures by changing SQL.
7. Do not add filters that were not requested unless a supplied business
   definition requires them.
8. Do not remove explicitly requested filters.
9. Preserve correct parts of the current query.
10. Use named placeholders such as :p1 for values.
11. Return parameter values separately from SQL.
12. Never interpolate parameter values into SQL.
13. Parameter placeholder names in SQL must exactly match keys in
    "parameters", without the leading colon.
14. Keep the original parameter values unless the identified issue
    specifically requires a supported change.
15. The repaired SQL and parameters will be independently validated
    by the backend.

OUTPUT CONTRACT

Return exactly one JSON object in one of these forms.

Repaired query:

{{
  "status": "repaired",
  "sql": "SELECT ... WHERE id = :p1",
  "parameters": {{
    "p1": 123
  }},
  "clarification_question": null
}}

Clarification required:

{{
  "status": "clarification_required",
  "sql": null,
  "parameters": {{}},
  "clarification_question": "..."
}}

Cannot safely repair:

{{
  "status": "cannot_repair",
  "sql": null,
  "parameters": {{}},
  "clarification_question": null
}}

Do not include Markdown, explanations, comments, reasoning, or extra keys.

USER REQUEST

<user_request>
{question}
</user_request>

CURRENT SQL

<current_sql>
{current_sql}
</current_sql>

CURRENT PARAMETERS

<current_parameters>
{parameters_json}
</current_parameters>

IDENTIFIED ISSUES

<issues>
{issues_json}
</issues>

TRUSTED SCHEMA

<schema>
{schema_json}
</schema>

ALLOWED RELATIONSHIPS

<relationships>
{relationships_json}
</relationships>

BUSINESS DEFINITIONS

<business_definitions>
{business_json}
</business_definitions>

METRIC DEFINITIONS

<metric_definitions>
{metrics_json}
</metric_definitions>

Return JSON only.
""".strip()
