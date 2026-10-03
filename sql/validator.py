from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, cast
import sqlglot
from sqlglot import exp

from metadata.schema_index import SchemaIndex


@dataclass(frozen=True, slots=True)
class SQLValidationResult:
    """
    Result of SQL technical validation.
    """
    valid: bool
    tables: tuple[str, ...] = ()
    columns: tuple[str, ...] = ()
    parameters_used: tuple[str, ...] = ()
    issues: tuple[str, ...] = field(default_factory=tuple)


class SQLValidator:
    """
    Validates SQL structure and schema consistency.

    Responsibilities:
    - SQL parsing
    - SELECT-only validation
    - single statement validation
    - parameter validation
    - table/column metadata validation

    Does NOT handle:
    - permissions
    - PII rules
    - query cost
    - execution
    """

    def __init__(self, schema_index: SchemaIndex) -> None:
        self._schema_index: SchemaIndex = schema_index

    def validate(self, sql: str, parameters: Mapping[str, Any] | None = None) -> SQLValidationResult:

        issues: list[str] = []
        parsed = self._parse_sql(sql, issues, )

        if parsed is None:
            return SQLValidationResult(valid=False, issues=tuple(issues), )

        self._validate_statement_type(parsed, issues, )
        tables = self._extract_tables(parsed)
        columns = self._extract_columns(parsed)
        self._validate_tables(tables, issues, )
        table_aliases = self._build_table_aliases(parsed, )
        self._validate_columns(parsed, tables, table_aliases, issues)

        used_parameters = self._validate_parameters(parsed, parameters, issues, )

        return SQLValidationResult(
            valid=not issues,
            tables=tables,
            columns=columns,
            parameters_used=used_parameters,
            issues=tuple(issues),
        )

    # --------------------------------------------------
    # Parsing
    # --------------------------------------------------

    def _parse_sql(self, sql: str, issues: list[str]) -> exp.Expression | None:

        if not sql.strip():
            issues.append("SQL is empty.")
            return None

        try:
            statements = sqlglot.parse(sql, read="postgres")

        except Exception as exc:
            issues.append(f"SQL parse error: {type(exc).__name__}")
            return None

        if not statements:
            issues.append("SQL parser returned no statements.")

            return None

        if len(statements) != 1:
            issues.append("Only one SQL statement is allowed.")

        return cast(exp.Expression, statements[0])

    # --------------------------------------------------
    # Statement validation
    # --------------------------------------------------

    def _validate_statement_type(self, parsed: exp.Expression, issues: list[str]) -> None:

        if not isinstance(
                parsed,
                (
                        exp.Select,
                        exp.Union,
                        exp.Intersect,
                        exp.Except,
                ),
        ):
            issues.append("Query must be a SELECT statement.")

    # --------------------------------------------------
    # Extraction
    # --------------------------------------------------

    def _extract_tables(self, parsed: exp.Expression) -> tuple[str, ...]:

        return tuple(
            sorted(
                {
                    table.name.lower()
                    for table in parsed.find_all(exp.Table)
                    if table.name
                }
            )
        )

    def _extract_columns(self, parsed: exp.Expression) -> tuple[str, ...]:

        return tuple(
            sorted(
                {
                    column.name.lower()
                    for column in parsed.find_all(exp.Column)
                    if column.name
                }
            )
        )

    # --------------------------------------------------
    # Schema validation
    # --------------------------------------------------

    def _validate_tables(self, tables: tuple[str, ...], issues: list[str]) -> None:

        for table_name in tables:

            if not self._schema_index.has_table(table_name):
                issues.append(f"Unknown table: {table_name}")

    def _build_table_aliases(self, parsed: exp.Expression) -> dict[str, str]:

        aliases: dict[str, str] = {}

        for table in parsed.find_all(exp.Table):
            table_name = table.name.lower()
            aliases[table_name] = table_name

            if table.alias:
                aliases[table.alias.lower()] = table_name

        return aliases

    def _validate_columns(
            self,
            parsed: exp.Expression,
            tables: tuple[str, ...],
            table_aliases: dict[str, str],
            issues: list[str],
    ) -> None:

        for column in parsed.find_all(exp.Column):

            column_name = column.name.lower()

            # Simple mode:
            # SELECT customer_id FROM customers
            if not column.table:

                if len(tables) > 1:
                    issues.append(
                        f"Ambiguous column without table qualifier: {column_name}"
                    )

                continue

            table_reference = column.table.lower()

            resolved_table = table_aliases.get(
                table_reference
            )

            if resolved_table is None:
                issues.append(
                    f"Unknown table reference: {table_reference}"
                )

                continue

            if not self._schema_index.has_column(
                    resolved_table,
                    column_name,
            ):
                issues.append(
                    f"Unknown column: {resolved_table}.{column_name}"
                )

    # --------------------------------------------------
    # Parameter validation
    # --------------------------------------------------

    def _validate_parameters(
            self,
            parsed: exp.Expression,
            parameters: Mapping[str, Any] | None,
            issues: list[str],
    ) -> tuple[str, ...]:

        used_parameters = tuple(
            sorted(
                {
                    parameter.name
                    for parameter in parsed.find_all(exp.Parameter)
                }
            )
        )

        supplied_parameters = set(parameters.keys() if parameters else [])

        missing = (set(used_parameters) - supplied_parameters)

        if missing:
            issues.append("Missing parameters: " + ", ".join(sorted(missing)))

        unused = (supplied_parameters - set(used_parameters))

        if unused:
            issues.append("Unused parameters: " + ", ".join(sorted(unused)))
        return used_parameters
