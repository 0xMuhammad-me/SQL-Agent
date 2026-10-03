from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .evaluator import BenchmarkEvaluator, EvaluationResult
from .metrics import EvaluationMetrics, MetricsCalculator


class BenchmarkRunner:
    """
    Loads benchmark questions and runs evaluation.
    """

    def __init__(self, evaluator: BenchmarkEvaluator, metrics_calculator: MetricsCalculator | None = None) -> None:
        self._evaluator: BenchmarkEvaluator = evaluator
        self._metrics_calculator: MetricsCalculator = (
            metrics_calculator
            if metrics_calculator is not None
            else MetricsCalculator()
        )

    def run(self, benchmark_path: str | Path) -> tuple[list[EvaluationResult], EvaluationMetrics]:
        """
        Run the complete benchmark.
        """

        questions: list[dict[str, Any]] = self._load_csv(benchmark_path)

        results: list[EvaluationResult] = []

        for item in questions:
            result: EvaluationResult = (
                self._evaluator.evaluate(
                    question_id=int(item["question_id"]),
                    category=str(item["category"]),
                    difficulty=str(item["difficulty"]),
                    question=str(item["question"]),
                    expected_sql=str(item["expected_sql"]),
                )
            )

            results.append(result)

        metrics: EvaluationMetrics = self._metrics_calculator.calculate(results)
        return results, metrics

    @staticmethod
    def _load_csv(benchmark_path: str | Path) -> list[dict[str, Any]]:
        """
        Load benchmark CSV.
        """

        path: Path = Path(benchmark_path)

        if not path.exists():
            raise FileNotFoundError(f"Benchmark file not found: {path}")

        rows: list[dict[str, Any]] = []
        with path.open(mode="r", encoding="utf-8", newline="") as file_handle:
            reader: csv.DictReader[str] = csv.DictReader(file_handle)

            required_columns: set[str] = {
                "question_id",
                "category",
                "difficulty",
                "question",
                "expected_sql",
                "tables_required",
            }

            actual_columns: set[str] = set(reader.fieldnames or [])

            missing_columns: set[str] = (required_columns - actual_columns)

            if missing_columns:
                raise ValueError(f"Benchmark CSV is missing columns: {sorted(missing_columns)}")

            for row in reader:
                rows.append(dict(row))

        return rows
