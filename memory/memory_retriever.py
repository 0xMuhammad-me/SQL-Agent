from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from agent_schemas import QuerySpec
from metadata.schema_catalog import TableSchema

from .business_memory import BusinessMemory, BusinessSearchResult
from .metric_memory import MetricMemory, MetricSearchResult
from .schema_memory import SchemaMemory, SchemaSearchResult


@dataclass(frozen=True, slots=True)
class MemoryContext:
    schema: tuple[SchemaSearchResult, ...]
    business: tuple[BusinessSearchResult, ...]
    metrics: tuple[MetricSearchResult, ...]


class MemoryRetriever:
    """Retrieve relevant semantic metadata from memory indexes."""

    def __init__(
        self,
        schema_memory: SchemaMemory,
        business_memory: BusinessMemory,
        metric_memory: MetricMemory,
    ) -> None:
        self.schema_memory: SchemaMemory = schema_memory
        self.business_memory: BusinessMemory = business_memory
        self.metric_memory: MetricMemory = metric_memory

    def retrieve(
        self,
        query_spec: QuerySpec,
        *,
        schema_top_k: int = 6,
        business_top_k: int = 5,
        metric_top_k: int = 20,
    ) -> MemoryContext:
        query_text: str = self._query_text(query_spec)
        metrics: list[MetricSearchResult] = self.metric_memory.search(query_text, metric_top_k)
        business: list[BusinessSearchResult] = self.business_memory.search(query_text, business_top_k)
        schema: list[SchemaSearchResult] = self.schema_memory.search(query_text, schema_top_k)
        return MemoryContext(tuple(schema), tuple(business), tuple(metrics))

    def get_tables(self, names: Iterable[str]) -> tuple[SchemaSearchResult, ...]:
        results: list[SchemaSearchResult] = []
        for name in dict.fromkeys(item.lower() for item in names if item):
            table: TableSchema | None = self.schema_memory.get_table(name)
            if table is not None:
                results.append(SchemaSearchResult(table, 100.0))
        results.sort(key=lambda item: item.table.name)
        return tuple(results)

    @staticmethod
    def _query_text(query_spec: QuerySpec) -> str:
        parts: list[str] = [query_spec.intent or "", query_spec.metric or ""]
        parts.extend(query_spec.dimensions)
        parts.extend(item.field for item in query_spec.filters)
        if query_spec.time_range is not None:
            parts.append(query_spec.time_range.field)
        parts.extend(item.field for item in query_spec.sort)
        return " ".join(part for part in parts if part)
