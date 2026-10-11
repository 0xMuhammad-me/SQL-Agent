from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
from typing import Any, Iterable

from .evaluator import EvaluationResult


def calculate_metrics(results: Iterable[EvaluationResult], *, include_breakdowns: bool = True) -> dict[str, Any]:
    items: list[EvaluationResult] = list(results)
    total = len(items)

    result_matches: list[bool] = [item.result_sql_match for item in items if item.result_sql_match is not None]

    report: dict[str, Any] = {
        "total_questions": total,

        "generation_success_rate": _rate(sum(item.generation_success for item in items), total),

        "execution_success_rate": _rate(sum(item.execution_success for item in items), total),

        "result_sql_match_rate": (_rate(sum(result_matches), len(result_matches)) if result_matches else None),

        "result_sql_match_evaluated_questions": len(result_matches),

        "result_sql_match_unavailable_questions": (total - len(result_matches)),

        "average_latency_ms": (sum(item.latency_ms for item in items) / total if total else 0.0),

        "status_counts": _counts(item.status for item in items)
    }

    if include_breakdowns:
        report["by_category"] = _breakdown(items, lambda item: item.category)
        report["by_difficulty"] = _breakdown(items, lambda item: item.difficulty, )

    return report


def results_to_dicts(results: Iterable[EvaluationResult]) -> list[dict[str, Any]]:
    return [asdict(item) for item in results]


def _breakdown(items: list[EvaluationResult], key_fn: Any) -> dict[str, Any]:
    groups: dict[str, list[EvaluationResult]] = defaultdict(list)

    for item in items:
        groups[str(key_fn(item))].append(item)

    return {
        key: calculate_metrics(group, include_breakdowns=False)
        for key, group in sorted(groups.items())
    }


def _counts(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)

    for value in values:
        counts[value] += 1

    return dict(sorted(counts.items()))


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0
