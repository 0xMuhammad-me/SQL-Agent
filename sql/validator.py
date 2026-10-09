from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, cast

import sqlglot
from sqlglot import exp

from metadata.schema_index import SchemaIndex


@dataclass(frozen=True, slots=True)
class SQLValidationResult:
    valid: bool
    tables: tuple[str, ...] = ()
    columns: tuple[str, ...] = ()
    parameters_used: tuple[str, ...] = ()
    issues: tuple[str, ...] = ()


class SQLValidator:
    """
    Perform deterministic SQL parsing, physical identifier validation,
    and parameter binding validation.
    """

    def __init__(self, schema_index: SchemaIndex) -> None:
        self._schema: SchemaIndex = schema_index

    def validate(self, sql: str, parameters: Mapping[str, Any]) -> SQLValidationResult:
        issues: list[str] = []

        parsed: exp.Expression | None = self._parse(sql, issues)

        if parsed is None:
            return SQLValidationResult(valid=False, issues=tuple(dict.fromkeys(issues)))

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

        cte_names: set[str] = {
            cte.alias_or_name.lower()
            for cte in parsed.find_all(exp.CTE)
            if cte.alias_or_name
        }

        tables: tuple[str, ...] = tuple(
            sorted(
                {
                    table.name.lower()
                    for table in parsed.find_all(exp.Table)
                    if (table.name and table.name.lower() not in cte_names)
                }
            )
        )

        for table in tables:
            if not self._schema.has_table(table):
                issues.append(
                    f"Unknown table: {table}"
                )

        aliases: dict[str, str] = {
            table: table
            for table in tables
        }

        for table in parsed.find_all(exp.Table):
            table_name: str = table.name.lower()
            alias: str = (
                table.alias.lower()
                if table.alias
                else ""
            )

            if table_name in tables and alias:
                aliases[alias] = table_name

        cte_columns: dict[str, set[str]] = (
            self._infer_cte_columns(parsed)
        )

        alias_reference_ids: set[int] = (
            self._select_alias_reference_ids(parsed)
        )

        referenced_columns: set[str] = set()

        for column in parsed.find_all(exp.Column):
            column_name: str = column.name.lower()
            qualifier: str = (column.table.lower() if column.table else "")

            if not qualifier and id(column) in alias_reference_ids:
                continue

            if qualifier in cte_columns:
                if column_name not in cte_columns[qualifier]:
                    issues.append(f"Unknown CTE column: {qualifier}.{column_name}")
                else:
                    referenced_columns.add(column_name)
                continue

            if qualifier:
                resolved: str | None = aliases.get(qualifier)

                if resolved is None:
                    issues.append(f"Unknown table reference: {qualifier}")
                    continue

                if not self._schema.has_column(resolved, column_name):
                    issues.append(f"Unknown column: {resolved}.{column_name}")
                    continue

                referenced_columns.add(column_name)
                continue

            matches: tuple[str, ...] = tuple(table for table in tables if self._schema.has_column(table, column_name))

            cte_matches: tuple[str, ...] = tuple(
                name
                for name, cte_cols in cte_columns.items()
                if column_name in cte_cols
            )

            total_matches: tuple[str, ...] = matches + cte_matches

            if not total_matches:
                issues.append(f"Unknown column: {column_name}")

            elif len(total_matches) > 1:
                issues.append(f"Ambiguous column without table qualifier: {column_name}")

            else:
                referenced_columns.add(column_name)

        used_parameters: set[str] = (self._extract_parameter_names(parsed))

        supplied_parameters: set[str] = {str(key).lower() for key in parameters}

        missing: set[str] = used_parameters - supplied_parameters

        unused: set[str] = supplied_parameters - used_parameters

        if missing:
            issues.append("Missing parameters: " + ", ".join(sorted(missing)))

        if unused:
            issues.append("Unused parameters: " + ", ".join(sorted(unused)))

        return SQLValidationResult(
            valid=not issues,
            tables=tables,
            columns=tuple(sorted(referenced_columns)),
            parameters_used=tuple(sorted(used_parameters)),
            issues=tuple(dict.fromkeys(issues)),
        )

    @staticmethod
    def _parse(sql: str, issues: list[str]) -> exp.Expression | None:
        if not sql.strip():
            issues.append("SQL is empty.")
            return None

        try:
            statements: list[exp.Expression] = sqlglot.parse(sql, read="postgres")
        except Exception as exc:
            issues.append(f"SQL parse error: {type(exc).__name__}")
            return None

        if len(statements) != 1:
            issues.append("Only one SQL statement is allowed.")

        return cast(exp.Expression, statements[0] if statements else None)

    @staticmethod
    def _infer_cte_columns(parsed: exp.Expression) -> dict[str, set[str]]:
        result: dict[str, set[str]] = {}

        for cte in parsed.find_all(exp.CTE):
            name: str = (cte.alias_or_name or "").lower()

            query: exp.Expression | None = cte.this

            if not name or not isinstance(query, exp.Select):
                continue

            names: set[str] = set()

            for projection in query.expressions:
                output_name: str = (projection.alias_or_name.lower() if projection.alias_or_name else "")

                if output_name:
                    names.add(output_name)

                elif isinstance(projection, exp.Column) and projection.name:
                    names.add(projection.name.lower())

            result[name] = names

        return result

    @staticmethod
    def _select_alias_reference_ids(parsed: exp.Expression) -> set[int]:
        aliases: set[str] = set()

        for select in parsed.find_all(exp.Select):
            for projection in select.expressions:
                if projection.alias_or_name:
                    aliases.add(projection.alias_or_name.lower())

        if not aliases:
            return set()

        references: set[int] = set()

        for select in parsed.find_all(exp.Select):
            for clause_name in ("order", "group"):
                clause: exp.Expression | None = (select.args.get(clause_name))

                if clause is None:
                    continue

                for column in clause.find_all(exp.Column):
                    if not column.table and column.name.lower() in aliases:
                        references.add(id(column))

        return references

    @staticmethod
    def _extract_parameter_names(parsed: exp.Expression) -> set[str]:
        names: set[str] = set()

        parameter_type: type[exp.Expression] | None = getattr(exp, "Parameter", None)

        placeholder_type: type[exp.Expression] | None = getattr(exp, "Placeholder", None)

        node_types: tuple[type[exp.Expression], ...] = tuple(
            node_type
            for node_type in (parameter_type, placeholder_type)
            if node_type is not None
        )

        if not node_types:
            return names

        pattern: re.Pattern[str] = re.compile(r"^[:@]([A-Za-z_][A-Za-z0-9_]*)$")

        for node in parsed.walk():
            if not isinstance(node, node_types):
                continue

            rendered: str = node.sql(dialect="postgres").strip()
            match = pattern.fullmatch(rendered)

            if match:
                names.add(match.group(1).lower())
                continue

            for attribute_name in ("name", "this"):
                value: Any = getattr(node, attribute_name, None, )

                if not isinstance(value, str):
                    continue

                value = value.strip()
                value_match = pattern.fullmatch(value)
                if value_match:
                    names.add(value_match.group(1).lower())
                    break

                if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
                    names.add(value.lower())
                    break

        return names
