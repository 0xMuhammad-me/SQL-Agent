from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any


def _json_default(value: Any) -> str:
    """
    Convert common database/runtime values into JSON-safe values.

    Raises:
        TypeError: If the value cannot be safely serialized.
    """

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, Decimal):
        return str(value)

    raise TypeError(
        f"Object of type {type(value).__name__} "
        "is not JSON serializable."
    )


def serialize_json(data: Any) -> str:
    """
    Serialize prompt input as deterministic, readable JSON.

    Args:
        data: Data that will be inserted into a prompt.

    Returns:
        JSON string.

    Raises:
        TypeError: If unsupported objects are present.
    """

    return json.dumps(data, ensure_ascii=False, indent=2, default=_json_default)


def build_context_block(title: str, data: Any) -> str:
    """
    Build a clearly delimited context section.

    Args:
        title: Human-readable section title.
        data: Data to serialize into the section.

    Returns:
        Formatted prompt section.
    """

    if not isinstance(title, str):
        raise TypeError(
            "title must be a string."
        )

    normalized_title: str = title.strip()

    if not normalized_title:
        raise ValueError(
            "title cannot be empty."
        )

    return (
        f"<{normalized_title}>\n"
        f"{serialize_json(data)}\n"
        f"</{normalized_title}>"
    )


def validate_prompt_input(value: str, *, name: str, max_length: int = 10_000) -> str:
    """
    Validate text before inserting it into a prompt.

    Args:
        value: Text value.
        name: Logical field name used in error messages.
        max_length: Maximum allowed character count.

    Returns:
        Normalized input text.

    Raises:
        TypeError: If value is not a string.
        ValueError: If value is empty or too long.
    """

    if not isinstance(value, str):
        raise TypeError(
            f"{name} must be a string."
        )

    normalized_value: str = value.strip()

    if not normalized_value:
        raise ValueError(
            f"{name} cannot be empty."
        )

    if len(normalized_value) > max_length:
        raise ValueError(
            f"{name} exceeds the maximum allowed length "
            f"of {max_length} characters."
        )

    return normalized_value
