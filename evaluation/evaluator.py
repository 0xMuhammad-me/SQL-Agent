from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence


class TextToSQLAgent(Protocol):
    """
    Interface required from the production Text-to-SQL agent.
    """

    def run(self, question: str) -> Any:
        """
        Run one natural-language question through the agent.
        """
        ...


class SQLExecutor(Protocol):
    """
    Interface required for benchmark SQL execution.
    """

    def execute(self, sql: str, parameters: Mapping[str, Any]) -> Any:
        """
        Execute one read-only SQL query.
        """
        ...


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    """
    Evaluation result for one benchmark question.
    """

    question_id: int
    category: str
    difficulty: str

    question: str
    expected_sql: str
    generated_sql: str | None

    sql_exact_match: bool
    execution_match: bool

    generation_success: bool
    execution_success: bool

    execution_ms: float | None

    error_type: str | None
    error_message: str | None


class BenchmarkEvaluator:
    """
    Evaluates generated SQL against benchmark expectations.
    """

    def __init__(self, agent: TextToSQLAgent, executor: SQLExecutor) -> None:
        self._agent: TextToSQLAgent = agent
        self._executor: SQLExecutor = executor

    def evaluate(self, question_id: int, category: str, difficulty: str, question: str,
                 expected_sql: str, ) -> EvaluationResult:
        """
        Evaluate one benchmark question.
        """

        try:
            agent_result: Any = self._agent.run(question)
            generated_sql_value: Any = getattr(agent_result, "sql", None)
            generated_sql: str | None = (str(generated_sql_value) if generated_sql_value is not None else None)

            if not generated_sql:
                return EvaluationResult(
                    question_id=question_id,
                    category=category,
                    difficulty=difficulty,
                    question=question,
                    expected_sql=expected_sql,
                    generated_sql=None,
                    sql_exact_match=False,
                    execution_match=False,
                    generation_success=False,
                    execution_success=False,
                    execution_ms=None,
                    error_type="generation_error",
                    error_message="Agent did not generate SQL.",
                )

            parameters_value: Any = getattr(agent_result, "parameters", {})
            parameters: Mapping[str, Any] = parameters_value if isinstance(parameters_value, Mapping) else {}
            sql_exact_match: bool = self._compare_sql(generated_sql, expected_sql)
            expected_execution: Any = self._executor.execute(expected_sql, {})
            generated_execution: Any = self._executor.execute(generated_sql, parameters)
            expected_success: bool = self._execution_success(expected_execution)
            generated_success: bool = self._execution_success(generated_execution)
            execution_match: bool = False

            if expected_success and generated_success:
                expected_rows: Sequence[Any] = self._extract_rows(expected_execution)
                generated_rows: Sequence[Any] = self._extract_rows(generated_execution)
                execution_match = self._compare_results(generated_rows, expected_rows)

            execution_ms: float | None = self._extract_execution_ms(generated_execution)

            return EvaluationResult(
                question_id=question_id,
                category=category,
                difficulty=difficulty,
                question=question,
                expected_sql=expected_sql,
                generated_sql=generated_sql,
                sql_exact_match=sql_exact_match,
                execution_match=execution_match,
                generation_success=True,
                execution_success=generated_success,
                execution_ms=execution_ms,
                error_type=self._extract_error_type(generated_execution),
                error_message=self._extract_error_message(generated_execution)
            )

        except Exception as exc:
            return EvaluationResult(
                question_id=question_id,
                category=category,
                difficulty=difficulty,
                question=question,
                expected_sql=expected_sql,
                generated_sql=None,
                sql_exact_match=False,
                execution_match=False,
                generation_success=False,
                execution_success=False,
                execution_ms=None,
                error_type=type(exc).__name__,
                error_message=str(exc),
            )

    @staticmethod
    def _compare_sql(generated_sql: str, expected_sql: str) -> bool:
        """
        Compare SQL after basic normalization.
        """
        generated_normalized: str = (" ".join(generated_sql.strip().split()).rstrip(";").lower())
        expected_normalized: str = (" ".join(expected_sql.strip().split()).rstrip(";").lower())
        return generated_normalized == expected_normalized

    @staticmethod
    def _compare_results(generated_rows: Sequence[Any], expected_rows: Sequence[Any]) -> bool:
        """
        Compare result sets without depending on row ordering.
        """
        generated_normalized: list[str] = sorted(repr(row) for row in generated_rows)
        expected_normalized: list[str] = sorted(repr(row) for row in expected_rows)

        return generated_normalized == expected_normalized

    @staticmethod
    def _execution_success(execution_result: Any) -> bool:
        """
        Extract execution success status.
        """
        value: Any = getattr(execution_result, "success", False)
        return bool(value)

    @staticmethod
    def _extract_rows(execution_result: Any) -> Sequence[Any]:
        """
        Extract rows from an execution result.
        """
        rows: Any = getattr(execution_result, "rows", ())

        if isinstance(rows, Sequence):
            return rows
        return ()

    @staticmethod
    def _extract_execution_ms(execution_result: Any) -> float | None:
        """
        Extract execution latency.
        """
        value: Any = getattr(execution_result, "execution_ms", None)
        if value is None:
            return None
        return float(value)

    @staticmethod
    def _extract_error_type(execution_result: Any) -> str | None:
        """
        Extract execution error type.
        """
        value: Any = getattr(execution_result, "error_type", None)
        return str(value) if value is not None else None

    @staticmethod
    def _extract_error_message(execution_result: Any) -> str | None:
        """
        Extract execution error message.
        """
        value: Any = getattr(execution_result, "error_message", None)
        return str(value) if value is not None else None
