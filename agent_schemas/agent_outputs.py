from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class SQLGenerationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["query", "clarification_required"]
    sql: str | None = None
    parameters: list[SQLParameter] = Field(default_factory=list)
    clarification_question: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_consistency(self) -> "SQLGenerationResult":
        if self.status == "query":

            if not self.sql: raise ValueError("status='query' requires sql.")
            if self.clarification_question is not None: raise ValueError(
                "Query output cannot contain clarification_question.")
        else:
            if self.sql is not None or self.parameters: raise ValueError(
                "Clarification output cannot contain SQL or parameters.")
            if not self.clarification_question: raise ValueError(
                "Clarification output requires clarification_question.")
        return self


class SQLRepairResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["repaired", "clarification_required", "cannot_repair"]
    sql: str | None = None
    parameters: list[SQLParameter] = Field(default_factory=list)
    clarification_question: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_consistency(self) -> "SQLRepairResult":
        if self.status == "repaired":

            if not self.sql: raise ValueError("status='repaired' requires sql.")

            if self.clarification_question is not None: raise ValueError(
                "Repaired output cannot contain clarification_question.")

        elif self.status == "clarification_required":

            if self.sql is not None or self.parameters: raise ValueError(
                "Clarification output cannot contain SQL or parameters.")

            if not self.clarification_question: raise ValueError(
                "Clarification output requires clarification_question.")

        elif self.sql is not None or self.parameters or self.clarification_question is not None:
            raise ValueError("Cannot-repair output must be empty except for status.")
        return self


class SQLReviewIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal[
        "semantic",
        "metric",
        "filter",
        "time_logic",
        "sort",
        "aggregation",
        "join",
        "schema",
        "parameter",
        "business_rule",
        "grain",
        "result_shape",
    ]
    severity: Literal["low", "medium", "high", "critical"]
    description: str = Field(min_length=1, max_length=3000)
    evidence: str = Field(min_length=1, max_length=3000)


class SQLReviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: Literal[
        "pass",
        "repair",
        "clarification_required",
        "fail",
        "inconclusive",
    ]
    confidence: float = Field(ge=0.0, le=1.0)
    issues: list[SQLReviewIssue] = Field(default_factory=list)
    repair_instructions: list[str] = Field(default_factory=list)
    clarification_question: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_consistency(self) -> "SQLReviewResult":
        if self.verdict == "pass":
            if self.issues or self.repair_instructions:
                raise ValueError("Pass cannot contain issues or repair instructions.")

        if self.verdict == "repair":
            if not self.issues or not self.repair_instructions:
                raise ValueError("Repair requires issues and repair instructions.")
            if self.clarification_question is not None:
                raise ValueError("Repair cannot contain clarification_question.")

        if self.verdict == "clarification_required":
            if not self.clarification_question:
                raise ValueError("Clarification required verdict needs clarification_question.")
            if self.repair_instructions:
                raise ValueError("Clarification required cannot contain repair instructions.")

        if self.verdict == "fail" and not self.issues:
            raise ValueError("Fail requires at least one issue.")

        if self.verdict == "inconclusive" and not self.issues:
            raise ValueError("Inconclusive requires at least one issue.")

        if self.verdict != "clarification_required" and self.clarification_question is not None:
            raise ValueError("clarification_question is only valid for clarification_required.")

        return self


class ReflectionIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal[
        "syntax",
        "execution",
        "semantic",
        "schema",
        "join",
        "aggregation",
        "date_logic",
        "business_rule",
        "metric",
        "result_sanity",
        "infrastructure"]
    severity: Literal["low", "medium", "high", "critical"]
    description: str = Field(min_length=1, max_length=3000)
    evidence: str = Field(min_length=1, max_length=3000)


class ReflectionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verdict: Literal["pass", "repair", "clarify", "reject", "inconclusive"]
    confidence: float = Field(ge=0.0, le=1.0)
    issues: list[ReflectionIssue] = Field(
        default_factory=list,
        description=(
            "Diagnostic issues identified by reflection. "
            "Must be [] when verdict='pass' or verdict='clarify'."
        ),
    )
    repair_instructions: list[str] = Field(
        default_factory=list,
        description=(
            "Actionable SQL repair guidance. "
            "Must be [] unless verdict='repair'."
        ),
    )
    clarification_question: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_consistency(self) -> "ReflectionResult":
        if self.verdict == "pass" and (self.issues or self.repair_instructions): raise ValueError(
            "Pass cannot contain issues or repair instructions.")

        if self.verdict == "repair":

            if any(issue.type == "infrastructure" for issue in self.issues): raise ValueError(
                "Infrastructure issues cannot trigger semantic repair.")

            if not self.issues or not self.repair_instructions: raise ValueError(
                "Repair requires issues and repair instructions.")

            if self.clarification_question is not None: raise ValueError(
                "Repair cannot contain clarification_question.")

        elif self.repair_instructions:
            raise ValueError("repair_instructions require verdict='repair'.")

        if self.verdict == "clarify" and not self.clarification_question: raise ValueError(
            "Clarify requires clarification_question.")

        if self.verdict != "clarify" and self.clarification_question is not None: raise ValueError(
            "clarification_question is only valid for clarify verdict.")

        return self


class SQLParameter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    value: str | int | float | bool | None = None
