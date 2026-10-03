from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RequestType(str, Enum):
    """High-level classification of the user request."""

    QUERY = "query"
    CLARIFICATION = "clarification"
    UNSUPPORTED = "unsupported"


class FilterOperator(str, Enum):
    """Supported semantic filter operators."""

    EQ = "eq"
    NE = "ne"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    IN = "in"
    NOT_IN = "not_in"
    BETWEEN = "between"
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"


class SortDirection(str, Enum):
    """Allowed sort directions."""
    ASC = "asc"
    DESC = "desc"


class TimeRangeType(str, Enum):
    """Defines how a requested time range was expressed."""
    EXPLICIT = "explicit"
    RELATIVE = "relative"


class QueryFilter(BaseModel):
    """
    Represents one semantic filter extracted from the user request.

    The field is a semantic field name at this stage and is not treated
    as a trusted SQL identifier.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    field: str = Field(min_length=1, max_length=200, description=
    "Semantic field requested by the user, such as "
    "'brand', 'city', or 'order status'."
                       )

    operator: FilterOperator
    value: Any | None = Field(default=None, description="Single filter value used by scalar operators.")

    values: list[Any] = Field(default_factory=list,
                              description="Multiple values used by IN, NOT_IN, or BETWEEN-style filters."
                              )

    @field_validator("field")
    @classmethod
    def validate_field(cls, value: str) -> str:
        """Reject empty semantic field names."""

        normalized: str = value.strip()
        if not normalized:
            raise ValueError("Filter field cannot be empty.")

        return normalized


class TimeRange(BaseModel):
    """
    Represents a user-requested time constraint.

    The request analyzer extracts the user's intent.
    The runtime may later normalize relative expressions into concrete
    date/time boundaries.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    field: str = Field(min_length=1, max_length=200, description=
    "Semantic timestamp/date field, such as "
    "'order date' or 'event time'."
                       )

    range_type: TimeRangeType

    start: str | None = Field(default=None, description=
    "Explicit start boundary in a parseable date/time format."
                              )

    end: str | None = Field(default=None, description=
    "Explicit end boundary in a parseable date/time format."
                            )

    relative_expression: str | None = Field(default=None, description=
    "Original relative expression such as "
    "'last 30 days' or 'previous month'."
                                            )

    include_start: bool = True
    include_end: bool = False


class SortSpec(BaseModel):
    """Represents one requested ordering criterion."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    field: str = Field(min_length=1, max_length=200)
    direction: SortDirection = SortDirection.ASC


class QuerySpec(BaseModel):
    """
    Structured semantic representation of one user request.

    This model is shared between the request analyzer and downstream
    SQL generation components.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)
    request_type: RequestType = RequestType.QUERY
    intent: str | None = Field(
        default=None,
        max_length=200,
        description=
        "Short semantic intent such as "
        "'revenue_analysis' or 'customer_retention'."
    )
    metric: str | None = Field(default=None, max_length=200, description=
    "Canonical metric name when one is explicitly identified "
    "from the available metric catalog."
                               )
    dimensions: list[str] = Field(default_factory=list, description=
    "Requested grouping dimensions expressed semantically."
                                  )
    filters: list[QueryFilter] = Field(default_factory=list)
    time_range: TimeRange | None = None
    sort: list[SortSpec] = Field(default_factory=list)
    limit: int | None = Field(default=None, ge=1, le=1000, description="User-requested result limit.")
    needs_clarification: bool = False
    clarification_question: str | None = Field(default=None, max_length=1000)
    sensitive_data_requested: bool = False
    unsupported_reason: str | None = Field(default=None, max_length=1000)

    @field_validator("dimensions")
    @classmethod
    def validate_dimensions(cls, values: list[str]) -> list[str]:
        """Normalize requested dimension names."""

        normalized: list[str] = []
        for value in values:
            item: str = value.strip()
            if not item:
                raise ValueError(
                    "Dimension names cannot be empty."
                )

            normalized.append(item)
        return normalized

    @field_validator("clarification_question")
    @classmethod
    def validate_clarification_question(cls, value: str | None) -> str | None:
        """Normalize clarification text."""

        if value is None:
            return None

        normalized: str = value.strip()
        return normalized or None

    def validate_state_consistency(self) -> "QuerySpec":
        """
        Validate cross-field semantic consistency.

        This is intentionally separate from Pydantic field validation
        because these rules depend on relationships between fields.
        """

        if self.needs_clarification and self.request_type != RequestType.CLARIFICATION:
            raise ValueError(
                "needs_clarification requires request_type='clarification'."
            )

        if self.request_type == RequestType.CLARIFICATION and not self.needs_clarification:
            raise ValueError(
                "Clarification request must set needs_clarification=true."
            )

        if self.request_type == RequestType.CLARIFICATION and not self.clarification_question:
            raise ValueError(
                "A clarification question is required."
            )

        if self.request_type != RequestType.CLARIFICATION:
            if self.clarification_question is not None:
                raise ValueError(
                    "clarification_question must be null unless clarification is required."
                )

        if self.request_type == RequestType.UNSUPPORTED:
            if not self.unsupported_reason:
                raise ValueError(
                    "Unsupported requests must provide unsupported_reason."
                )

        if self.request_type == RequestType.QUERY and self.unsupported_reason is not None:
            raise ValueError(
                "unsupported_reason must be null for normal queries."
            )

        return self
