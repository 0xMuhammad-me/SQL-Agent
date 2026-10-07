from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
from typing import Any, Iterable

from .evaluator import EvaluationResult


def calculate_metrics(results: Iterable[EvaluationResult]) -> dict[str, Any]:
    items: list[EvaluationResult] = list(results)
    total: int = len(items)
    execution_matches: list[bool] = [item.execution_result_match for item in items if item.execution_result_match is not None]

    report: dict[str, Any] = {
        "total_questions": total,
        "generation_success_rate": _rate(sum(item.generation_success for item in items), total),
        "execution_success_rate": _rate(sum(item.execution_success for item in items), total),
        "exact_sql_match_rate": _rate(sum(item.exact_sql_match for item in items), total),
        "execution_result_match_rate": _rate(sum(execution_matches), len(execution_matches)) if execution_matches else None,
        "average_latency_ms": sum(item.latency_ms for item in items) / total if total else 0.0,
        "status_counts": _counts(item.status for item in items),
        "by_category": _breakdown(items, lambda item: item.category),
        "by_difficulty": _breakdown(items, lambda item: item.difficulty),
    }
    return report


def results_to_dicts(results: Iterable[EvaluationResult]) -> list[dict[str, Any]]:
    return [asdict(item) for item in results]


def _breakdown(items: list[EvaluationResult], key_fn: Any) -> dict[str, Any]:
    groups: dict[str, list[EvaluationResult]] = defaultdict(list)
    for item in items:
        groups[str(key_fn(item))].append(item)
    return {key: calculate_metrics(group) for key, group in sorted(groups.items())}


def _counts(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for value in values:
        counts[value] += 1
    return dict(sorted(counts.items()))


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0
