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

    def run(self, *, dataset_path: str | Path, report_path: str | Path | None = None) -> dict[str, Any]:
        questions = self._evaluator.load_csv(dataset_path)
        results: list[EvaluationResult] = [self._evaluator.evaluate(item) for item in questions]
        report: dict[str, Any] = {
            "metrics": calculate_metrics(results),
            "results": results_to_dicts(results),
        }
        if report_path is not None:
            path = Path(report_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return report
