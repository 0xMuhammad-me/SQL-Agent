from __future__ import annotations

import re

from dataclasses import dataclass
from typing import Mapping

from metadata.metric_catalog import (
    METRIC_DEFINITIONS,
)


@dataclass(frozen=True)
class MetricSearchResult:
    """Represents a metric retrieval result."""
    name: str
    definition: str
    score: float


class MetricMemory:
    """Provides retrieval over metric definitions."""
    def __init__(self, metrics: Mapping[str, str] = METRIC_DEFINITIONS) -> None:
        self._metrics: dict[str, str] = dict(metrics)

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return {token for token in re.findall(r"[a-zA-Z0-9_]+", text.lower()) if len(token) > 1}


    def get_metric(self, name: str) -> str | None:
        """Return one metric definition by name."""
        return self._metrics.get(name)


    def search(self, query: str, top_k: int = 8) -> list[MetricSearchResult]:

        query_tokens: set[str] = self._tokenize(query)
        results: list[MetricSearchResult] = []

        for name, definition in self._metrics.items():
            searchable_text: str = (name + " " + definition)
            candidate_tokens: set[str] = self._tokenize(searchable_text)
            overlap: int = len(query_tokens & candidate_tokens)
            exact_name_match: bool = (name.lower() in query.lower())
            score: float = float(overlap + (3 if exact_name_match else 0))

            if score > 0:
                results.append(MetricSearchResult(name=name, definition=definition, score=score))

        results.sort(key=lambda item: item.score, reverse=True)
        return results[:top_k]


    def all(self) -> dict[str, str]:
        """Return all metric definitions."""
        return dict(self._metrics)