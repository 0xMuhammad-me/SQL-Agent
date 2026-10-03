from __future__ import annotations

from .schema_catalog import SCHEMA_CATALOG, TableSchema


class SchemaIndex:
    """
    Fast lookup over schema metadata.
    """

    def __init__(self) -> None:
        self.tables: dict[str, TableSchema] = { table.name: table for table in SCHEMA_CATALOG}
        self.columns = {}

        for table in SCHEMA_CATALOG:
            for column in table.columns:
                self.columns.setdefault(column.name,[]).append(table.name)


    def has_table( self, table_name: str) -> bool:
        return table_name.lower() in self.tables

    def has_column( self, table_name: str, column_name: str) -> bool:
        columns = self.get_table_columns(table_name)

        return column_name.lower() in columns

    def find_column_tables(  self,  column_name: str,) -> list[str]:
        return self.columns.get( column_name.lower(), [])

    def get_table_columns(  self, table_name: str ) -> list[str]:
        table: TableSchema | None = self.tables.get(table_name.lower())

        if table is None:
            return []

        return [ column.name.lower() for column in table.columns]