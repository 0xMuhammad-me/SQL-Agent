from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Any

from agent_schemas import QuerySpec
from memory import CacheStore, MemoryContext, MemoryRetriever
from metadata.glossary import GLOSSARY
from metadata.relationship_catalog import RELATIONSHIPS


@dataclass(frozen=True, slots=True)
class RelevantMetadata:
    schema: tuple[dict[str, Any], ...]
    relationships: tuple[str, ...]
    business: tuple[dict[str, Any], ...]
    metrics: tuple[dict[str, Any], ...]
    glossary: tuple[dict[str, Any], ...]


class MetadataTools:
    """Retrieve the minimal relevant metadata package for SQL generation."""

    def __init__(
            self,
            memory_retriever: MemoryRetriever,
            cache: CacheStore | None = None,
            *,
            cache_ttl_seconds: float = 300.0
    ) -> None:
        self._memory: MemoryRetriever = memory_retriever
        self._cache: CacheStore | None = cache
        self._ttl: float = cache_ttl_seconds

    def retrieve(self, query_spec: QuerySpec) -> RelevantMetadata:
        key: str = self._key(query_spec)
        if self._cache is not None:
            cached: Any | None = self._cache.get(key)
            if isinstance(cached, RelevantMetadata):
                return cached

        memory: MemoryContext = self._memory.retrieve(query_spec)
        seed_tables: set[str] = {item.table.name.lower() for item in memory.schema}
        seed_tables.update(self._tables_from_query_fields(query_spec))
        seed_tables.update(self._tables_from_semantic_definitions(memory, query_spec))

        relationships: tuple[str, ...] = self._relevant_relationships(seed_tables)
        connected_tables: set[str] = set(seed_tables)
        for relationship in relationships:
            connected_tables.update(self._relationship_tables(relationship))
        schema_results = self._memory.get_tables(connected_tables)

        glossary: tuple[dict[str, Any], ...] = tuple(self._search_glossary(self._query_text(query_spec), 6))
        business_items = self._select_business(memory, query_spec)
        metric_items = self._select_metrics(memory, query_spec)
        output = RelevantMetadata(
            schema=tuple(asdict(item.table) for item in schema_results),
            relationships=relationships,
            business=tuple({"name": item.name, "definition": item.definition} for item in business_items),
            metrics=tuple({"name": item.name, "definition": item.definition} for item in metric_items),
            glossary=glossary,
        )
        if self._cache is not None:
            self._cache.set(key, output, ttl_seconds=self._ttl)

        return output

    @staticmethod
    def _tables_from_query_fields(query_spec: QuerySpec) -> set[str]:
        fields: list[str] = list(query_spec.dimensions)
        fields.extend(item.field for item in query_spec.filters)
        fields.extend(item.field for item in query_spec.sort)
        if query_spec.time_range is not None:
            fields.append(query_spec.time_range.field)
        return {field.split(".", 1)[0].lower() for field in fields if "." in field}

    @staticmethod
    def _tables_from_semantic_definitions(memory: MemoryContext, query_spec: QuerySpec) -> set[str]:
        texts: list[str] = []
        if query_spec.metric:
            exact_metrics = [item for item in memory.metrics if item.name.lower() == query_spec.metric.lower()]

            selected_metrics = (exact_metrics if exact_metrics else list(memory.metrics[:1]))

            texts.extend(item.definition for item in selected_metrics)
        query_lower: str = (query_spec.intent or "").lower()
        texts.extend(
            item.definition
            for item in memory.business
            if item.name.lower() in query_lower
        )
        tables: set[str] = set()
        for text in texts:
            tables.update(
                match.lower() for match in re.findall(
                    r"\b([a-zA-Z_][a-zA-Z0-9_]*)\.[a-zA-Z_][a-zA-Z0-9_]*\b",
                    text,
                )
            )
        return tables

    @staticmethod
    def _relationship_tables(relationship: str) -> set[str]:
        return {
            match.lower()
            for match in re.findall(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\.[a-zA-Z_][a-zA-Z0-9_]*\b", relationship)
        }

    @classmethod
    def _relevant_relationships(cls, seed_tables: set[str]) -> tuple[str, ...]:
        graph: dict[str, list[str]] = {}
        for relationship in RELATIONSHIPS:
            tables: set[str] = cls._relationship_tables(relationship)
            if len(tables) != 2:
                continue
            left, right = sorted(tables)
            graph.setdefault(left, []).append(right)
            graph.setdefault(right, []).append(left)

        selected_edges: set[tuple[str, str]] = set()
        seeds: list[str] = sorted(seed_tables)
        for index, start in enumerate(seeds):
            for target in seeds[index + 1:]:
                path: list[str] = cls._shortest_path(graph, start, target)
                for offset in range(len(path) - 1):
                    left: str = path[offset]
                    right: str = path[offset + 1]

                    selected_edges.add((left, right) if left <= right else (right, left))
        return tuple(
            relationship
            for relationship in RELATIONSHIPS
            if cls._relationship_edge(relationship) in selected_edges
        )

    @classmethod
    def _relationship_edge(cls, relationship: str) -> tuple[str, str]:
        tables: set[str] = cls._relationship_tables(relationship)
        if len(tables) != 2:
            return "", ""

        ordered: list[str] = sorted(tables)
        return ordered[0], ordered[1]

    @staticmethod
    def _shortest_path(graph: dict[str, list[str]], start: str, target: str) -> list[str]:
        if start == target:
            return [start]
        queue: list[list[str]] = [[start]]
        visited: set[str] = {start}
        while queue:
            path: list[str] = queue.pop(0)
            node: str = path[-1]
            for neighbor in graph.get(node, []):
                if neighbor in visited:
                    continue
                next_path: list[str] = [*path, neighbor]
                if neighbor == target:
                    return next_path
                visited.add(neighbor)
                queue.append(next_path)
        return []

    @staticmethod
    def _select_metrics(memory: MemoryContext, query_spec: QuerySpec) -> tuple[Any, ...]:
        if query_spec.metric:
            exact = tuple(item for item in memory.metrics if item.name.lower() == query_spec.metric.lower())

            if exact:
                return exact

        if not memory.metrics:
            return ()

        max_score: float = max(item.score for item in memory.metrics)

        return tuple(item for item in memory.metrics if item.score == max_score)

    @staticmethod
    def _select_business(memory: MemoryContext, query_spec: QuerySpec) -> tuple[Any, ...]:
        intent: str = (query_spec.intent or "").lower()
        matched = tuple(item for item in memory.business if item.name.lower() in intent)
        if matched:
            return matched
        return tuple(memory.business[:3])

    @staticmethod
    def _query_text(query_spec: QuerySpec) -> str:
        parts: list[str] = [query_spec.intent or "", query_spec.metric or ""]
        parts.extend(query_spec.dimensions)
        parts.extend(item.field for item in query_spec.filters)
        if query_spec.time_range is not None:
            parts.append(query_spec.time_range.field)
        parts.extend(item.field for item in query_spec.sort)
        return " ".join(part for part in parts if part)

    @staticmethod
    def _search_glossary(query: str, limit: int) -> list[dict[str, Any]]:
        query_tokens: set[str] = set(re.findall(r"[a-zA-Z0-9_]+", query.lower()))
        scored: list[tuple[int, str, list[str]]] = []
        for name, synonyms in GLOSSARY.items():
            terms: list[str] = [name, *[str(item) for item in synonyms]]
            tokens: set[str] = set(re.findall(r"[a-zA-Z0-9_]+", " ".join(terms).lower()))
            score: int = len(query_tokens & tokens)
            if score:
                scored.append((score, name, [str(item) for item in synonyms]))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [{"term": name, "synonyms": synonyms} for _, name, synonyms in scored[:limit]]

    @staticmethod
    def _key(query_spec: QuerySpec) -> str:
        payload: bytes = (json.dumps(query_spec.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
                          .encode("utf-8"))
        return "metadata:" + hashlib.sha256(payload).hexdigest()
