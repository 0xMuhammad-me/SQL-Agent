from __future__ import annotations

from typing import Any, Mapping, Protocol, Sequence


class SchemaMemoryProvider(Protocol):
    """
    Interface required from the schema memory layer.
    """

    def retrieve(self, query: str, *, limit: int = 10) -> Sequence[Mapping[str, Any]]:
        """
        Retrieve relevant schema information.
        """
        ...


class RelationshipCatalogProvider(Protocol):
    """
    Interface required from the relationship catalog.
    """

    def get_relationships(self, tables: Sequence[str] | None = None) -> Sequence[str]:
        """
        Return relevant table relationships.
        """
        ...


class MetadataTools:
    """
    Backend-controlled tools for schema and relationship retrieval.
    """

    def __init__(self, schema_memory: SchemaMemoryProvider, relationship_catalog: RelationshipCatalogProvider) -> None:
        self._schema_memory: SchemaMemoryProvider = schema_memory
        self._relationship_catalog: RelationshipCatalogProvider = relationship_catalog

    def get_schema_context(self, query: str, *, limit: int = 10) -> list[Mapping[str, Any]]:
        """
        Retrieve schema metadata relevant to a natural-language request.
        """

        if not query.strip():
            return []

        normalized_limit: int = max(1, min(limit, 50))

        results: Sequence[Mapping[str, Any]] = self._schema_memory.retrieve(query, limit=normalized_limit)

        return [dict(result) for result in results]

    def get_relationship_context(self, tables: Sequence[str] | None = None) -> list[str]:
        """
        Retrieve relationships relevant to the supplied tables.
        """

        normalized_tables: tuple[str, ...] = tuple(
            sorted(
                {
                    str(table).strip().lower()
                    for table in (tables or ())
                    if str(table).strip()
                }
            )
        )

        relationships: Sequence[str] = self._relationship_catalog.get_relationships(normalized_tables)

        return [str(relationship) for relationship in relationships]

    def get_context(self, query: str, *, tables: Sequence[str] | None = None, schema_limit: int = 10) -> dict[str, Any]:
        """
        Retrieve schema and relationship context together.
        """

        schema_context: list[Mapping[str, Any]] = self.get_schema_context(query, limit=schema_limit)
        relationship_context: list[str] = self.get_relationship_context(tables)

        return {"schema": schema_context, "relationships": relationship_context}
