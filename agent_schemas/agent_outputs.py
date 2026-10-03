from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class SQLGenerationResult(BaseModel):
    """
    Structured output returned by the SQL generation agent.

    This model validates the structure and consistency of the LLM output.
    It does NOT validate SQL safety or correctness.
    """

    model_config = ConfigDict(extra="forbid")

    status: Literal["query", "clarification_required"] = Field(
        description=(
            "Indicates whether a query was generated or "
            "clarification is required."
        ),
    )

    sql: str | None = Field(
        default=None,
        description=(
            "One generated read-only SQL statement. "
            "Backend validation is still required."
        ),
    )

    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Named bind parameters used by the SQL statement. "
            "Keys must correspond to SQL placeholders."
        ),
    )

    clarification_question: str | None = Field(
        default=None,
        max_length=2000,
        description=(
            "Concise clarification question when the request "
            "cannot be resolved safely."
        ),
    )

    @model_validator(mode="after")
    def validate_consistency(self) -> SQLGenerationResult:
        """
        Validate consistency between status, SQL, parameters,
        and clarification fields.
        """

        if self.status == "query":

            if not self.sql:
                raise ValueError(
                    "status='query' requires sql."
                )

            if self.clarification_question is not None:
                raise ValueError(
                    "status='query' cannot contain clarification_question."
                )

            return self

        if self.status == "clarification_required":

            if self.sql is not None:
                raise ValueError(
                    "status='clarification_required' requires sql=null."
                )

            if self.parameters:
                raise ValueError(
                    "Clarification output cannot contain parameters."
                )

            if not self.clarification_question:
                raise ValueError(
                    "Clarification output requires clarification_question."
                )

        return self


class SQLRepairResult(BaseModel):
    """
    Structured output returned by the SQL repair agent.

    This model only describes the repair agent response.
    The backend must independently validate the repaired SQL.
    """

    model_config = ConfigDict(extra="forbid")

    status: Literal["repaired", "clarification_required", "cannot_repair"] = Field(
        description=(
            "Indicates whether SQL was repaired, clarification "
            "is needed, or the issue cannot be safely repaired."
        ),
    )

    sql: str | None = Field(default=None, description="Repaired read-only SQL statement.")

    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Named bind parameters corresponding to the repaired SQL."
        ),
    )

    clarification_question: str | None = Field(
        default=None,
        max_length=2000,
        description=(
            "Clarification question when repair cannot proceed "
            "without additional user information."
        ),
    )

    @model_validator(mode="after")
    def validate_consistency(self) -> SQLRepairResult:
        """
        Validate consistency between repair status and returned fields.
        """

        if self.status == "repaired":

            if not self.sql:
                raise ValueError(
                    "status='repaired' requires sql."
                )

            if self.clarification_question is not None:
                raise ValueError(
                    "Repaired output cannot contain clarification_question."
                )

            return self

        if self.status == "clarification_required":

            if self.sql is not None:
                raise ValueError(
                    "Clarification output requires sql=null."
                )

            if self.parameters:
                raise ValueError(
                    "Clarification output cannot contain parameters."
                )

            if not self.clarification_question:
                raise ValueError(
                    "Clarification output requires clarification_question."
                )

            return self

        if self.status == "cannot_repair":

            if self.sql is not None:
                raise ValueError(
                    "Cannot-repair output requires sql=null."
                )

            if self.parameters:
                raise ValueError(
                    "Cannot-repair output cannot contain parameters."
                )

            if self.clarification_question is not None:
                raise ValueError(
                    "Cannot-repair output cannot contain clarification_question."
                )

        return self


class ReflectionIssue(BaseModel):
    """
    One diagnostic issue identified by the reflection agent.

    Reflection is advisory and does not replace deterministic
    backend validation or security controls.
    """

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
        "infrastructure",
    ] = Field(
        description="Category of the identified issue.",
    )

    severity: Literal[
        "low",
        "medium",
        "high",
        "critical",
    ] = Field(
        description="Severity assigned by the reflection agent.",
    )

    description: str = Field(
        min_length=1,
        max_length=3000,
        description=(
            "Concise description of the identified issue."
        ),
    )

    evidence: str = Field(
        min_length=1,
        max_length=3000,
        description=(
            "Evidence from the supplied execution context "
            "supporting the issue."
        ),
    )


class ReflectionResult(BaseModel):
    """
    Structured diagnostic output returned by the reflection agent.

    This result is a diagnostic signal only.
    It cannot authorize execution or override backend policy.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    verdict: Literal[
        "pass",
        "repair",
        "clarify",
        "reject",
        "inconclusive",
    ] = Field(description="Reflection's semantic assessment of the executed query.")

    confidence: float = Field(ge=0.0, le=1.0, description="Model confidence in the reflection assessment.")

    issues: list[ReflectionIssue] = Field(
        default_factory=list,
        description=(
            "Concrete issues identified during reflection."
        ),
    )

    repair_instructions: list[str] = Field(
        default_factory=list,
        description=(
            "Actionable SQL repair guidance when verdict='repair'."
        ),
    )

    @model_validator(mode="after")
    def validate_consistency(self) -> ReflectionResult:
        """
        Validate relationships between verdict, issues,
        and repair instructions.
        """

        if self.verdict == "pass":

            if self.issues:
                raise ValueError(
                    "verdict='pass' cannot contain issues."
                )

            if self.repair_instructions:
                raise ValueError(
                    "verdict='pass' cannot contain repair_instructions."
                )

        if self.verdict != "repair":

            if self.repair_instructions:
                raise ValueError(
                    "repair_instructions require verdict='repair'."
                )

        if self.verdict == "repair" and not self.issues:
            raise ValueError(
                "verdict='repair' requires at least one issue."
            )

        return self
