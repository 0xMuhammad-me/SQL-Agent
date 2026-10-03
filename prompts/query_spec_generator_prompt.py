from __future__ import annotations

from typing import Any, Mapping, Sequence

from .base import build_system_prompt
from ._utils import (
    build_context_block,
    validate_prompt_input,
)

PROMPT_NAME: str = "query_spec_generator"
PROMPT_VERSION: str = "v1.0.0"

QUERY_SPEC_GENERATOR_SYSTEM_PROMPT: str = build_system_prompt(
    """
You are the Senior Query Specification Agent in a production text-to-SQL system.

Your only responsibility is to transform the user's natural-language
request into a structured QuerySpec.

You DO NOT:

- generate SQL
- execute SQL
- call tools
- select executable tools
- create tools
- access the database
- define new metrics
- invent business rules
- resolve SQL table or column identifiers
- perform authorization
- perform security validation

The backend controls all execution and authorization.

The QuerySpec produced by you is untrusted model output and will be
validated by the application before any downstream processing.
""".strip()
)


def build_query_spec_generator_prompt(
        question: str,
        *,
        metric_catalog: Sequence[Mapping[str, Any]],
        business_catalog: Sequence[Mapping[str, Any]],
        glossary: Sequence[Mapping[str, Any]] | None = None,
        available_capabilities: Sequence[str] | None = None,
) -> str:
    """
    Build the user-side prompt for QuerySpec generation.

    Args:
        question:
            Original user request.

        metric_catalog:
            Trusted metric definitions relevant to the request.

        business_catalog:
            Trusted business definitions relevant to the request.

        glossary:
            Optional business terminology and synonyms.

        available_capabilities:
            Read-only capabilities currently exposed by the backend.

    Returns:
        Rendered prompt text to send using the provider's user role.
    """

    question = validate_prompt_input(
        question,
        name="question",
        max_length=10_000,
    )

    context: dict[str, Any] = {
        "metric_catalog": list(metric_catalog),
        "business_catalog": list(business_catalog),
        "glossary": list(glossary or []),
        "available_capabilities": list(
            available_capabilities or []
        ),
    }

    return f"""
Convert the following user request into a QuerySpec.

OUTPUT CONTRACT

Return exactly one JSON object:

{{
  "request_type": "query",
  "intent": null,
  "metric": null,
  "dimensions": [],
  "filters": [],
  "time_range": null,
  "sort": [],
  "limit": null,
  "needs_clarification": false,
  "clarification_question": null,
  "sensitive_data_requested": false,
  "unsupported_reason": null
}}

ALLOWED request_type VALUES

- "query"
- "clarification"
- "unsupported"

QUERY SPECIFICATION RULES

1. Extract the user's analytical intent without generating SQL.

2. Extract only constraints explicitly requested by the user.

3. Do not invent filters, dates, limits, dimensions, metrics,
   business definitions, or default values.

4. Use a metric name only when it is present in the supplied metric catalog
   and clearly matches the user's request.

5. If the user refers to a business concept defined in the business catalog,
   use that definition rather than inventing another interpretation.

6. Dimensions must represent what the user wants to group, compare,
   or display. Keep them semantic; do not invent SQL table or column names.

7. Filters must represent explicit user constraints.

8. Each filter must use one of the supported operators:

   eq
   ne
   gt
   gte
   lt
   lte
   in
   not_in
   between
   contains
   starts_with
   ends_with
   is_null
   is_not_null

9. For scalar operators, use "value".

10. For IN or NOT_IN, use "values".

11. For BETWEEN, put the lower and upper values in "values"
    in the order stated by the user.

12. For IS_NULL and IS_NOT_NULL, leave both "value" and "values" empty.

13. Do not convert user dates into different dates unless the conversion
    is unambiguous and supported by the application context.

14. For relative periods such as:
    "last 30 days"
    "this month"
    "previous quarter"

    preserve the original expression in:

    time_range.relative_expression

15. For explicitly supplied dates, use:

    time_range.range_type = "explicit"

    and populate start/end.

16. Do not silently decide whether an ambiguous date boundary is inclusive.

17. sort fields must represent user-requested ordering only.

18. limit must be set only when the user requests a limit.

19. sensitive_data_requested is a flag only.
    It does NOT grant permission to access sensitive data.

20. Do not classify a complex request as unsupported merely because
    it requires multiple tables.

21. Use "unsupported" only when the request is outside the supported
    analytical capability or violates an explicit application constraint.

22. If multiple materially different interpretations are possible,
    use:

    request_type = "clarification"

    needs_clarification = true

    and provide one concise clarification_question.

23. Do not ask for clarification when the supplied business catalog
    resolves the ambiguity.

24. If a required metric definition is missing and different interpretations
    could materially change the answer, request clarification.

25. Do not expose hidden reasoning.

26. Do not output any field that is not part of the output contract.

IMPORTANT DISTINCTION

You are NOT determining:

- the final SQL table
- the final SQL column
- join strategy
- SQL aggregation implementation
- SQL security
- database permissions

Those decisions belong to downstream components.

Your job is only to describe WHAT the user is asking for.

INPUT CONTEXT

{build_context_block(
        "TRUSTED BUSINESS AND METRIC CONTEXT",
        context,
    )}

USER REQUEST

<user_request>
{question}
</user_request>

FINAL CHECK

Before returning the JSON:

1. Ensure every extracted constraint came from the user request
   or trusted business metadata.

2. Ensure metric names exist in the supplied metric catalog.

3. Ensure no SQL was generated.

4. Ensure no unsupported keys were added.

5. Ensure clarification is used only when materially necessary.

Return JSON only.
""".strip()
