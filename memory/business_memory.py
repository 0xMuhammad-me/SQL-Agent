from __future__ import annotations

import re

from dataclasses import dataclass
from typing import Mapping

from metadata.business_catalog import (
    BUSINESS_DEFINITIONS,
)


@dataclass(frozen=True)
class BusinessSearchResult:
    """Represents a business definition retrieval result."""
    name: str
    definition: str
    score: float


class BusinessMemory:
    """Provides retrieval over business semantic definitions."""

    def __init__(self, definitions: Mapping[str, str] = BUSINESS_DEFINITIONS) -> None:

        self._definitions: dict[str, str] = dict(definitions)


    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return {token for token in re.findall(r"[a-zA-Z0-9_]+", text.lower()) if len(token) > 1}


    def get_definition(self, name: str) -> str | None:
        """Return one business definition by name."""
        return self._definitions.get(name)


    def search(self, query: str, top_k: int = 8) -> list[BusinessSearchResult]:
        query_tokens: set[str] = self._tokenize(query)

        results: list[BusinessSearchResult] = []

        for name, definition in self._definitions.items():

            searchable_text: str = (
                name
                + " "
                + definition
            )

            candidate_tokens: set[str] = self._tokenize(searchable_text)

            overlap: int = len(query_tokens & candidate_tokens)

            exact_name_match: bool = (name.lower() in query.lower())

            score: float = float(overlap + (3 if exact_name_match else 0))

            if score > 0:
                results.append(BusinessSearchResult(name=name, definition=definition, score=score))

        results.sort(key=lambda item: item.score, reverse=True)
        return results[:top_k]


    def all(self,) -> dict[str, str]:
        """Return all business definitions."""

        return dict(self._definitions)