from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from agent_schemas import QuerySpec
from .base import BASE_SYSTEM_PROMPT

PROMPT_NAME: str = "sql_repair"
PROMPT_VERSION: str = "v5.0.0"

SQL_REPAIR_SYSTEM_PROMPT: str = BASE_SYSTEM_PROMPT + """

You are the Senior SQL Repair Agent.
Repair only concrete SQL or semantic defects.
Never change SQL to bypass firewall, permissions, PII, cost, or infrastructure controls.
Repaired SQL is untrusted and will re-enter every deterministic gate.
""".strip()


def build_sql_repair_prompt(
        *,
        question: str,
        query_spec: QuerySpec,
        current_sql: str,
        current_parameters: Mapping[str, Any],
        issues: Sequence[Mapping[str, Any]],
        schema_context: Sequence[Mapping[str, Any]],
        relationship_context: Sequence[str],
        business_context: Sequence[Mapping[str, Any]],
        metric_context: Sequence[Mapping[str, Any]],
        repair_instructions: Sequence[str] = (),
        glossary_context: Sequence[Mapping[str, Any]] = (),
        dialect: str = "postgresql",
) -> str:
    return f"""
DIALECT
{dialect}

USER REQUEST
{question}

QUERY SPEC
{json.dumps(query_spec.model_dump(mode="json"), ensure_ascii=False, indent=2, default=str)}

CURRENT SQL
{current_sql}

CURRENT PARAMETERS
{json.dumps(dict(current_parameters), ensure_ascii=False, indent=2, default=str)}

ISSUES
{json.dumps(list(issues), ensure_ascii=False, indent=2, default=str)}

REPAIR INSTRUCTIONS
{json.dumps(list(repair_instructions), ensure_ascii=False, indent=2, default=str)}

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

RULES
Preserve user intent. Fix only listed SQL or semantic defects.
Never bypass security, permissions, PII, cost, or infrastructure controls.
The backend will independently re-run every validation and security gate.

The deterministic validation issues are authoritative diagnostics.
Do not reinterpret, suppress, or bypass a reported validation failure.
Use each issue to identify the defect, then repair the minimum necessary
SQL or parameter state.

The metric name from the QuerySpec is a semantic/canonical metric identifier,
not a database column.

Never use a metric name directly as a SQL column.

When repairing metric-related SQL, use the exact supplied metric
definition to determine the correct SQL formula.

The metric name itself is metadata only. Do not use it as a SQL
identifier, column, expression, or function unless the supplied metric
definition explicitly requires that exact database identifier.


For each reported issue:

- identify the exact SQL defect
- repair that defect
- preserve all valid parts of the query
- do not introduce unrelated changes
- ensure every table and column exists in SCHEMA
- ensure every join exists in RELATIONSHIPS
- ensure every parameter is both declared and used
- ensure no declared parameter is unused


Parameter rules:

1. Preserve existing parameter names exactly when they are already valid.
2. If SQL contains :p1, the parameters list must contain an entry with name "p1".
3. Never convert :p1 into :1, $1, or another placeholder style.
4. Every SQL placeholder must exactly match one "name" field in the parameters list.
5. Every parameter must be referenced by SQL.
6. Do not add a parameter unless its placeholder is used in SQL.
7. Do not remove a parameter unless its placeholder is also removed from SQL.
8. When repairing an "Unused parameters" issue, first determine whether
   the parameter represents a required QuerySpec constraint. If it does,
   add or restore its SQL placeholder. Otherwise remove the parameter.
9. When repairing a "Missing parameters" issue, use the exact missing
   placeholder name reported by validation.
10. Do not invent a new parameter name when validation already identifies
    the missing placeholder.
    

Parameter values are data, not repair targets.
Do not change an existing parameter value unless the reported defect
requires correcting its representation.


PARAMETER REPAIR RULES

When validation reports an unused parameter:

1. Determine which QuerySpec filter or other required constraint
   the parameter represents.

2. If the parameter corresponds to a QuerySpec filter, preserve both:
   - the QuerySpec constraint
   - the parameter
   and add or restore the matching SQL placeholder.

3. If the parameter does not correspond to any QuerySpec filter or
   other required constraint, remove the unused parameter.

4. Never remove a QuerySpec filter merely to eliminate an unused parameter.

5. Never silently drop an explicit user constraint.

6. Never remove an explicit QuerySpec filter merely because the selected
   metric also contains the same business rule.

   If the QuerySpec contains the filter, preserve its semantic constraint.

   If the SQL already implements the same constraint through the trusted
   metric definition, do not introduce a contradictory or duplicate
   condition unless the QuerySpec requires the constraint independently.

7. After repair:
   - every required QuerySpec filter is represented in SQL
   - every SQL placeholder has exactly one parameter
   - every supplied parameter is referenced by SQL
   - no required user constraint has been dropped


PARAMETER REPAIR EXAMPLE

QuerySpec filter:
{{
  "field": "products.brand",
  "operator": "eq",
  "value": "Oakley"
}}

Current SQL:
SELECT AVG(products.price)
FROM products

Current parameters:
[
  {{
    "name": "p1",
    "value": "Oakley"
  }}
]

Validation issue:
Unused parameters: p1

Correct repair:
SELECT AVG(products.price)
FROM products
WHERE products.brand = :p1

Parameters:
[
  {{
    "name": "p1",
    "value": "Oakley"
  }}
]

Do not remove p1 merely to make validation pass.
The required QuerySpec filter must remain represented in SQL.


OUTPUT JSON

Repaired:
{{
    "status":"repaired",
    "sql":"SELECT ...",
    "parameters":[ {{ "name": "p1", "value": 123 }} ],
    "clarification_question":null
}}

Clarification required:
{{
    "status": "clarification_required",
    "sql": null,
    "parameters": [],
    "clarification_question": "..."
}}

Cannot safely repair:
{{
    "status": "cannot_repair",
    "sql": null,
    "parameters": [],
    "clarification_question": null
}}
""".strip()
