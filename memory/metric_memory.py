from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Mapping
from metadata.metric_catalog import METRIC_DEFINITIONS


@dataclass(frozen=True, slots=True)
class MetricSearchResult: name: str;definition: str;score: float


class MetricMemory:
    def __init__(self, metrics: Mapping[str, str] = METRIC_DEFINITIONS) -> None:
        self._metrics = dict(metrics)

    def get_metric(self, name: str) -> str | None:
        return self._metrics.get(name.lower())

    def search(self, query: str, top_k: int = 8) -> list[MetricSearchResult]:
        query_tokens: set[str] = self._semantic_tokens(query)
        scored: list[MetricSearchResult] = []

        for name, definition in self._metrics.items():
            name_tokens: set[str] = self._semantic_tokens(name)
            definition_tokens: set[str] = self._semantic_tokens(definition)

            name_overlap: int = len(query_tokens & name_tokens)
            definition_overlap: int = len(query_tokens & definition_tokens)

            normalized_query: str = " ".join(sorted(query_tokens))
            normalized_name: str = " ".join(sorted(name_tokens))

            score: float = (name_overlap * 5.0 + definition_overlap )

            if normalized_query == normalized_name:
                score += 20.0

            if score > 0:
                scored.append(
                    MetricSearchResult(
                        name=name,
                        definition=definition.strip(),
                        score=score,
                    )
                )

        scored.sort(key=lambda item: (-item.score, item.name))
        return scored[:top_k]

    @staticmethod
    def _semantic_tokens(text: str) -> set[str]:
        normalized: str = text.lower().replace("_", " ")

        raw_tokens: list[str] = re.findall(r"[a-zA-Z0-9]+",normalized)

        equivalents: dict[str, str] = {
            "number": "count",
            "numbers": "count",
            "frequency": "count",
            "frequencies": "count",
            "view": "view",
            "views": "view",
            "event": "event",
            "events": "event",
            "customer": "customer",
            "customers": "customer",
            "product": "product",
            "products": "product",
            "order": "order",
            "orders": "order",
        }

        ignored: set[str] = {
            "of",
            "the",
            "a",
            "an",
            "is",
            "are",
            "what",
            "how",
        }

        return {equivalents.get(token, token)for token in raw_tokens if token not in ignored}