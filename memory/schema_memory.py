from __future__ import annotations

import re

from dataclasses import dataclass
from typing import Iterable

from metadata.schema_catalog import (
    SCHEMA_CATALOG,
    TableSchema,
)


@dataclass(frozen=True)
class SchemaSearchResult:
    """Represents a schema retrieval result."""

    table: TableSchema
    score: float


class SchemaMemory:
    """
    Provides deterministic retrieval over the database schema catalog.
    """

    def __init__(self, tables: Iterable[TableSchema] = SCHEMA_CATALOG) -> None:
        self._tables: tuple[TableSchema, ...] = tuple(tables)
        self._table_map: dict[str, TableSchema] = {table.name: table for table in self._tables}

    @staticmethod
    def _tokenize(text: str) -> set[str]:

        return {token for token in re.findall(r"[a-zA-Z0-9_]+", text.lower()) if len(token) > 1}

    def get_table(self, table_name: str) -> TableSchema | None:
        """
        Get a table by exact name.

        Returns:
            TableSchema when the table exists, otherwise None.
        """

        return self._table_map.get(table_name)

    def search(self, query: str, top_k: int = 8,) -> list[SchemaSearchResult]:
        """
        Retrieve the most relevant tables for a query.

        This deterministic retriever is intentionally simple.
        It can later be replaced by an embedding-based retriever.
        """

        query_tokens: set[str] = self._tokenize(query)

        results: list[SchemaSearchResult] = []

        for table in self._tables:

            searchable_text: str = (table.name
                                    + " "
                                    + table.description
                                    + " "
                                    + " ".join(
                        column.name
                        for column in table.columns
                    )
                                    )

            table_tokens: set[str] = self._tokenize(searchable_text)

            overlap: int = len(query_tokens & table_tokens)

            exact_table_match: bool = (table.name.lower() in query.lower())

            score: float = float(overlap + (3 if exact_table_match else 0))

            if score > 0:
                results.append(SchemaSearchResult(table=table, score=score))

        results.sort(key=lambda item: item.score, reverse=True)

        return results[:top_k]

    def all_tables(self) -> tuple[TableSchema, ...]:
        """Return all registered tables."""

        return self._tables
