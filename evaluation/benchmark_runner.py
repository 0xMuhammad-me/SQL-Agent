from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .evaluator import BenchmarkEvaluator, EvaluationResult
from .metrics import calculate_metrics, results_to_dicts


class BenchmarkRunner:
    """Run the benchmark and persist a machine-readable report."""

    def __init__(self, evaluator: BenchmarkEvaluator) -> None:
        self._evaluator: BenchmarkEvaluator = evaluator

    def run(self,*,dataset_path: str | Path,report_path: str | Path | None = None,) -> dict[str, Any]:
        questions = self._evaluator.load_csv(dataset_path)
        results: list[EvaluationResult] = [self._evaluator.evaluate(item) for item in questions]

        report: dict[str, Any] = {
            "recovery": {
                "mode": "live_benchmark_execution",
                "dataset_path": str(dataset_path),
                "log_path": None,
                "dataset_questions": len(questions),
                "log_requests": None,
                "recovered_questions": len(results),
                "unrecovered_questions": len(questions) - len(results),
                "complete": len(results) == len(questions),
                "matching_method": (
                    "Questions are evaluated directly from the dataset. "
                    "Reference and generated SQL results are compared "
                    "for each question; historical log matching is not used."
                ),
                "warning": (
                    "This report comes from live benchmark execution, "
                    "not recovery from existing logs."
                ),
            },

            "metrics": calculate_metrics(results),
            "results": results_to_dicts(results),
        }

        if report_path is not None:
            path = Path(report_path)
            path.parent.mkdir(parents=True,exist_ok=True)

            path.write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str), encoding="utf-8" )

        return report
