from __future__ import annotations

import csv
from dataclasses import dataclass
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
    exact_sql_match: bool
    execution_result_match: bool | None
    latency_ms: float
    status: str
    generated_sql: str | None
    expected_sql: str
    error: str | None = None


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
                        expected_sql=str(raw["expected_sql"]),
                        tables_required=tuple(BenchmarkEvaluator._parse_tables(raw.get("tables_required", ""))),
                    )
                )
        return rows

    def evaluate(self, item: BenchmarkQuestion) -> EvaluationResult:
        started_at: float = perf_counter()
        try:
            workflow: WorkflowResult = self._agent.run(AgentRequest(question=item.question))
            latency_ms: float = (perf_counter() - started_at) * 1000.0
            generation_success: bool = workflow.sql is not None and workflow.status not in {
                WorkflowStatus.SQL_GENERATION_CLARIFICATION,
                WorkflowStatus.CLARIFICATION_REQUIRED,
                WorkflowStatus.UNSUPPORTED,
            }
            execution_success: bool = workflow.status in {WorkflowStatus.ANSWERED, WorkflowStatus.REFLECTION_REJECTED}
            exact_match: bool = self._sql_equal(workflow.sql, item.expected_sql) if workflow.sql else False

            result_match: bool | None = None
            error: str | None = None
            if generation_success and workflow.sql is not None and execution_success:
                generated_execution = self._database.execute(workflow.sql, workflow.parameters)
                expected_execution = self._database.execute(item.expected_sql, {})
                if generated_execution.success and expected_execution.success:
                    result_match = self._rows_equal(
                        generated_execution.rows,
                        expected_execution.rows,
                        order_sensitive=self._has_ordering(item.expected_sql),
                    )
                else:
                    error = (
                        generated_execution.error_message
                        or expected_execution.error_message
                        or "Reference or generated SQL execution failed during evaluation."
                    )

            return EvaluationResult(
                question_id=item.question_id,
                category=item.category,
                difficulty=item.difficulty,
                generation_success=generation_success,
                execution_success=execution_success,
                exact_sql_match=exact_match,
                execution_result_match=result_match,
                latency_ms=latency_ms,
                status=workflow.status.value,
                generated_sql=workflow.sql,
                expected_sql=item.expected_sql,
                error=error or (workflow.issues[0] if workflow.issues else None),
            )
        except Exception as exc:
            latency_ms = (perf_counter() - started_at) * 1000.0
            return EvaluationResult(
                question_id=item.question_id,
                category=item.category,
                difficulty=item.difficulty,
                generation_success=False,
                execution_success=False,
                exact_sql_match=False,
                execution_result_match=None,
                latency_ms=latency_ms,
                status="evaluator_error",
                generated_sql=None,
                expected_sql=item.expected_sql,
                error=f"{type(exc).__name__}: {exc}",
            )

    @staticmethod
    def _sql_equal(left: str | None, right: str) -> bool:
        if left is None:
            return False
        try:
            left_sql: str = sqlglot.parse_one(left, read="postgres").sql(dialect="postgres")
            right_sql: str = sqlglot.parse_one(right, read="postgres").sql(dialect="postgres")
            return left_sql.strip() == right_sql.strip()
        except Exception:
            return " ".join(left.split()).lower() == " ".join(right.split()).lower()

    @staticmethod
    def _rows_equal(
        left: Sequence[Mapping[str, Any]],
        right: Sequence[Mapping[str, Any]],
        *,
        order_sensitive: bool,
    ) -> bool:
        if order_sensitive:
            return [dict(row) for row in left] == [dict(row) for row in right]
        return sorted((tuple(sorted(row.items())) for row in left), key=repr) == sorted(
            (tuple(sorted(row.items())) for row in right), key=repr
        )

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
