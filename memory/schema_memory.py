from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Iterable
from metadata.schema_catalog import SCHEMA_CATALOG, TableSchema


@dataclass(frozen=True, slots=True)
class SchemaSearchResult: table: TableSchema; score: float


class SchemaMemory:
    def __init__(self, tables: Iterable[TableSchema] = SCHEMA_CATALOG) -> None:
        self._tables = tuple(tables);self._map = {t.name.lower(): t for t in self._tables}

    def get_table(self, name: str) -> TableSchema | None:
        return self._map.get(name.lower())

    def search(self, query: str, top_k: int = 8) -> list[SchemaSearchResult]:
        qt = set(re.findall(r"[a-zA-Z0-9_]+", query.lower()));
        out = []
        for t in self._tables:
            txt = f"{t.name} {t.description} {' '.join(c.name for c in t.columns)}".lower();
            ct = set(re.findall(r"[a-zA-Z0-9_]+", txt));
            score = float(len(qt & ct) + (3 if t.name.lower() in query.lower() else 0))
            if score > 0: out.append(SchemaSearchResult(t, score))
        out.sort(key=lambda x: (-x.score, x.table.name));
        return out[:top_k]

    def all_tables(self) -> tuple[TableSchema, ...]:
        return self._tables
