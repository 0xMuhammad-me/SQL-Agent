from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping, Sequence

import sqlglot

from orchestration import AgentRequest, SQLAgent, WorkflowResult, WorkflowStatus
from sql import DatabaseExecutor


@dataclass(frozen=True, slots=True)
class BenchmarkQuestion:
    question_id: str
    category: str
    difficulty: str
    question: str
    expected_sql: str
    tables_required: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    question_id: str
    category: str
    difficulty: str

    generation_success: bool
    execution_success: bool
    result_sql_match: bool | None

    latency_ms: float
    status: str

    generated_sql: str | None
    expected_sql: str
    question: str = ""
    error: str | None = None

    generated_execution: dict[str, Any] | None = None
    expected_execution: dict[str, Any] | None = None

    token_usage: dict[str, int] = field(default_factory=dict)


class BenchmarkEvaluator:
    """Evaluate the production agent against a CSV benchmark."""

    def __init__(self, *, agent: SQLAgent, database_executor: DatabaseExecutor) -> None:
        self._agent: SQLAgent = agent
        self._database: DatabaseExecutor = database_executor

    @staticmethod
    def load_csv(path: str | Path) -> list[BenchmarkQuestion]:
        rows: list[BenchmarkQuestion] = []
        with Path(path).open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for raw in reader:
                rows.append(
                    BenchmarkQuestion(
                        question_id=str(raw["question_id"]),
                        category=str(raw["category"]),
                        difficulty=str(raw["difficulty"]),
                        question=str(raw["question"]),
                        expected_sql=str(raw["sql"]),
                        tables_required=tuple(BenchmarkEvaluator._parse_tables(raw.get("tables_required", ""))),
                    )
                )
        return rows

    def evaluate(self, item: BenchmarkQuestion) -> EvaluationResult:
        started_at = perf_counter()

        generated_execution_details: dict[str, Any] | None = None
        expected_execution_details: dict[str, Any] | None = None

        try:
            workflow: WorkflowResult = self._agent.run(AgentRequest(question=item.question,  metadata={"question_id": item.question_id},))
            latency_ms = (perf_counter() - started_at) * 1000.0

            generation_success = (
                    workflow.sql is not None
                    and workflow.status not in {
                        WorkflowStatus.SQL_GENERATION_CLARIFICATION,
                        WorkflowStatus.CLARIFICATION_REQUIRED,
                        WorkflowStatus.UNSUPPORTED,
                    }
            )

            execution_success = workflow.status in { WorkflowStatus.ANSWERED, WorkflowStatus.REFLECTION_REJECTED}

            result_sql_match: bool | None = None
            error: str | None = None

            expected_execution = self._database.execute(item.expected_sql,{})
            expected_execution_details = self._execution_details(expected_execution)

            if generation_success and workflow.sql is not None:
                generated_execution = self._database.execute(workflow.sql, workflow.parameters)
                generated_execution_details = self._execution_details(generated_execution)

                if  not generated_execution.success  or not expected_execution.success:
                    error = (
                            generated_execution.error_message
                            or expected_execution.error_message
                            or "SQL execution failed."
                    )

                elif  generated_execution.truncated  or expected_execution.truncated:
                    result_sql_match = None
                    error = "Comparison skipped because one or both SQL results were truncated."

                else:
                    result_sql_match = self._rows_equal(
                        generated_execution.rows,
                        expected_execution.rows,
                        order_sensitive=self._has_ordering(
                            item.expected_sql
                        ),
                    )

            elif not expected_execution.success:
                error = (expected_execution.error_message or "Reference SQL execution failed.")

            return EvaluationResult(
                question_id=item.question_id,
                category=item.category,
                difficulty=item.difficulty,
                generation_success=generation_success,
                execution_success=execution_success,
                result_sql_match=result_sql_match,
                latency_ms=latency_ms,
                status=workflow.status.value,
                generated_sql=workflow.sql,
                expected_sql=item.expected_sql,
                question=item.question,
                error=error or ( workflow.issues[0] if workflow.issues else None),
                generated_execution=generated_execution_details,
                expected_execution=expected_execution_details,
            )

        except Exception as exc:
            # Attempt to save the reference SQL output even if there is an evaluation error
            if expected_execution_details is None:
                try:
                    expected_execution = self._database.execute(item.expected_sql,{})
                    expected_execution_details = self._execution_details(expected_execution)
                except Exception:
                    pass

            latency_ms = (perf_counter() - started_at) * 1000.0

            return EvaluationResult(
                question_id=item.question_id,
                category=item.category,
                difficulty=item.difficulty,
                generation_success=False,
                execution_success=False,
                result_sql_match=None,
                latency_ms=latency_ms,
                status="evaluator_error",
                generated_sql=None,
                expected_sql=item.expected_sql,
                question=item.question,
                error=f"{type(exc).__name__}: {exc}",
                generated_execution=generated_execution_details,
                expected_execution=expected_execution_details,
            )

    @staticmethod
    def _execution_details(execution: Any) -> dict[str, Any]:
        return {
            "success": execution.success,
            "columns": list(execution.columns),
            "row_count": execution.row_count,
            "execution_ms": execution.execution_ms,
            "truncated": execution.truncated,
            "rows": [
                dict(row)
                for row in execution.rows
            ],
            "error_type": execution.error_type,
            "error_message": execution.error_message,
        }

    @staticmethod
    def _rows_equal(
            left: Sequence[Mapping[str, Any]],
            right: Sequence[Mapping[str, Any]],
            *,
            order_sensitive: bool,
    ) -> bool:
        # The number of rows must be identical.
        if len(left) != len(right):
            return False

        # Compare row values regardless of column names.
        left_values = [tuple(row.values()) for row in left]

        right_values = [tuple(row.values()) for row in right]

        # Preserve row order when the query contains ORDER BY.
        if order_sensitive:
            return left_values == right_values

        # Ignore row order when ORDER BY is not present.
        return sorted(left_values, key=repr) == sorted(right_values, key=repr)

    @staticmethod
    def _has_ordering(sql: str) -> bool:
        try:
            parsed = sqlglot.parse_one(sql, read="postgres")
            return bool(parsed.args.get("order"))
        except Exception:
            return False

    @staticmethod
    def _parse_tables(value: str) -> list[str]:
        normalized: str = value.strip().strip("{}").strip()
        if not normalized:
            return []
        return [item.strip() for item in normalized.split(",") if item.strip()]
