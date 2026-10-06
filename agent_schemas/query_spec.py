from __future__ import annotations
from enum import Enum
from typing import TypeAlias
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RequestType(str, Enum): QUERY = "query"; CLARIFICATION = "clarification"; UNSUPPORTED = "unsupported"


class FilterOperator(str, Enum):
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


class SortDirection(str, Enum): ASC = "asc"; DESC = "desc"


class TimeRangeType(str, Enum):
    EXPLICIT = "explicit"
    RELATIVE = "relative"


FilterValue: TypeAlias = str | int | float | bool | None


class QueryFilter(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    field: str = Field(min_length=1, max_length=200)
    operator: FilterOperator
    value: FilterValue = Field(
        default=None,
        description="Single JSON-compatible filter value used by scalar operators.",
    )

    values: list[FilterValue] = Field(
        default_factory=list,
        description="Multiple JSON-compatible values used by IN, NOT_IN, or BETWEEN-style filters.",
    )

    @field_validator("field")
    @classmethod
    def normalize_field(cls, v: str) -> str:
        v = v.strip()
        if not v: raise ValueError("Filter field cannot be empty.")
        return v

    @model_validator(mode="after")
    def validate_value_shape(self) -> "QueryFilter":
        multi = {FilterOperator.IN, FilterOperator.NOT_IN, FilterOperator.BETWEEN}
        unary = {FilterOperator.IS_NULL, FilterOperator.IS_NOT_NULL}
        if self.operator in unary:
            if self.value is not None or self.values: raise ValueError("Null-check operators cannot contain values.")
        elif self.operator in multi:
            if not self.values: raise ValueError("This operator requires a non-empty values list.")
            if self.value is not None: raise ValueError("Multi-value operators cannot use value.")
            if self.operator == FilterOperator.BETWEEN and len(self.values) != 2: raise ValueError(
                "BETWEEN requires exactly two values.")
        elif self.value is None:
            raise ValueError("Scalar filter operators require value.")
        elif self.values:
            raise ValueError("Scalar filter operators cannot contain values.")
        return self


class TimeRange(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    field: str = Field(min_length=1, max_length=200)
    range_type: TimeRangeType
    start: str | None = None
    end: str | None = None
    relative_expression: str | None = None
    include_start: bool = True
    include_end: bool = False

    @field_validator("field")
    @classmethod
    def normalize_field(cls, v: str) -> str:
        v = v.strip()
        if not v: raise ValueError("Time range field cannot be empty.")
        return v

    @model_validator(mode="after")
    def validate_range(self) -> "TimeRange":
        if self.range_type == TimeRangeType.EXPLICIT:
            if not self.start or not self.end: raise ValueError("Explicit time ranges require start and end.")
            if self.relative_expression is not None: raise ValueError(
                "Explicit time ranges cannot contain relative_expression.")
        else:
            if not self.relative_expression: raise ValueError("Relative time ranges require relative_expression.")
            if self.start is not None or self.end is not None: raise ValueError(
                "Relative time ranges cannot contain explicit boundaries.")
        return self


class SortSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    field: str = Field(min_length=1, max_length=200)
    direction: SortDirection = SortDirection.ASC

    @field_validator("field")
    @classmethod
    def normalize_field(cls, v: str) -> str:
        v = v.strip()
        if not v: raise ValueError("Sort field cannot be empty.")
        return v


class QuerySpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request_type: RequestType = RequestType.QUERY
    intent: str | None = Field(default=None, max_length=200)
    metric: str | None = Field(
        default=None,
        max_length=200,
        description="Semantic metric during drafting and canonical metric name after metadata grounding."
    )
    dimensions: list[str] = Field(default_factory=list)
    filters: list[QueryFilter] = Field(default_factory=list)
    time_range: TimeRange | None = None
    sort: list[SortSpec] = Field(default_factory=list)
    limit: int | None = Field(default=None, ge=1, le=1000)
    needs_clarification: bool = False
    clarification_question: str | None = Field(default=None, max_length=1000)
    sensitive_data_requested: bool = False
    unsupported_reason: str | None = Field(default=None, max_length=1000)

    @field_validator("dimensions")
    @classmethod
    def normalize_dimensions(cls, vals: list[str]) -> list[str]:
        out = []
        seen = set()
        for v in vals:
            v = v.strip()
            if not v: raise ValueError("Dimension names cannot be empty.")
            if v.lower() not in seen: out.append(v); seen.add(v.lower())
        return out

    @field_validator("intent", "metric", "unsupported_reason", "clarification_question")
    @classmethod
    def normalize_text(cls, v: str | None) -> str | None:
        if v is None: return None
        v = v.strip()
        return v or None

    @model_validator(mode="after")
    def validate_state_consistency(self) -> "QuerySpec":
        if self.needs_clarification != (self.request_type == RequestType.CLARIFICATION): raise ValueError(
            "needs_clarification must match request_type.")
        if self.request_type == RequestType.CLARIFICATION and not self.clarification_question: raise ValueError(
            "Clarification requests require clarification_question.")
        if self.request_type != RequestType.CLARIFICATION and self.clarification_question is not None: raise ValueError(
            "clarification_question is only valid for clarification requests.")
        if self.request_type == RequestType.UNSUPPORTED and not self.unsupported_reason: raise ValueError(
            "Unsupported requests require unsupported_reason.")
        if self.request_type != RequestType.UNSUPPORTED and self.unsupported_reason is not None: raise ValueError(
            "unsupported_reason is only valid for unsupported requests.")
        return self
