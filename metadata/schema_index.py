from __future__ import annotations

from metadata.schema_catalog import ColumnSchema, SCHEMA_CATALOG, TableSchema


class SchemaIndex:
    """Fast lookup over the trusted schema catalog."""

    def __init__(self, tables: tuple[TableSchema, ...] = SCHEMA_CATALOG) -> None:
        self._tables: dict[str, TableSchema] = {table.name.lower(): table for table in tables}
        self._columns: dict[str, frozenset[str]] = {
            table.name.lower(): frozenset(column.name.lower() for column in table.columns)
            for table in tables
        }

    def has_table(self, table_name: str) -> bool:
        return table_name.lower() in self._tables

    def has_column(self, table_name: str, column_name: str) -> bool:
        return column_name.lower() in self._columns.get(table_name.lower(), frozenset())

    def get_table(self, table_name: str) -> TableSchema | None:
        return self._tables.get(table_name.lower())

    def get_column(self, table_name: str, column_name: str) -> ColumnSchema | None:
        table: TableSchema | None = self.get_table(table_name)
        if table is None:
            return None
        target: str = column_name.lower()
        return next((column for column in table.columns if column.name.lower() == target), None)

    def tables(self) -> tuple[str, ...]:
        return tuple(sorted(self._tables))
