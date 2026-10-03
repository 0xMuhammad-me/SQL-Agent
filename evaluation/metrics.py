from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Sequence

from .evaluator import EvaluationResult


@dataclass(frozen=True, slots=True)
class EvaluationMetrics:
    """
    Aggregate metrics for a benchmark run.
    """

    total_questions: int

    generation_success_rate: float
    execution_success_rate: float

    sql_exact_match_rate: float
    execution_accuracy: float

    average_execution_ms: float
    failure_rate: float


class MetricsCalculator:
    """
    Calculates benchmark metrics.
    """

    def calculate(self, results: Sequence[EvaluationResult]) -> EvaluationMetrics:
        """
        Calculate aggregate benchmark metrics.
        """
        total_questions: int = len(results)
        if total_questions == 0:
            return EvaluationMetrics(
                total_questions=0,
                generation_success_rate=0.0,
                execution_success_rate=0.0,
                sql_exact_match_rate=0.0,
                execution_accuracy=0.0,
                average_execution_ms=0.0,
                failure_rate=0.0,
            )

        generation_success_count: int = sum(result.generation_success for result in results)
        execution_success_count: int = sum(result.execution_success for result in results)
        sql_exact_match_count: int = sum(result.sql_exact_match for result in results)
        execution_match_count: int = sum(result.execution_match for result in results)
        failures_count: int = sum(not result.execution_success for result in results)

        execution_times: list[float] = [
            result.execution_ms
            for result in results
            if result.execution_ms is not None
        ]

        average_execution_ms: float = mean(execution_times) if execution_times else 0.0

        return EvaluationMetrics(
            total_questions=total_questions,
            generation_success_rate=(generation_success_count / total_questions),
            execution_success_rate=(execution_success_count / total_questions),
            sql_exact_match_rate=(sql_exact_match_count / total_questions),
            execution_accuracy=(execution_match_count / total_questions),
            average_execution_ms=average_execution_ms,
            failure_rate=(failures_count / total_questions)
        )
