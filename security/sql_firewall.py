from __future__ import annotations

from dataclasses import dataclass

import sqlglot
from sqlglot import exp

from .policy import SecurityPolicy


@dataclass(frozen=True, slots=True)
class SQLFirewallResult:
    allowed: bool
    statement_type: str | None
    tables: tuple[str, ...]
    forbidden_functions: tuple[str, ...] = ()
    issues: tuple[str, ...] = ()


class SQLFirewall:
    """Enforce deterministic SQL security policy after validation."""

    _FORBIDDEN_NODES = frozenset(
        node
        for node in (
            getattr(exp, "Insert", None),
            getattr(exp, "Update", None),
            getattr(exp, "Delete", None),
            getattr(exp, "Drop", None),
            getattr(exp, "Alter", None),
            getattr(exp, "Create", None),
            getattr(exp, "TruncateTable", None),
            getattr(exp, "Grant", None),
            getattr(exp, "Revoke", None),
            getattr(exp, "Command", None),
            getattr(exp, "Copy", None),
            getattr(exp, "Merge", None),
        )
        if node is not None
    )
    _FORBIDDEN_FUNCTIONS = frozenset(
        {
            "PG_READ_FILE",
            "PG_READ_BINARY_FILE",
            "PG_LS_DIR",
            "PG_STAT_FILE",
            "PG_SLEEP",
            "DBLINK",
            "DBLINK_CONNECT",
        }
    )

    def __init__(self, policy: SecurityPolicy) -> None:
        self._policy: SecurityPolicy = policy

    def validate(self, sql: str) -> SQLFirewallResult:
        if not sql.strip():
            return SQLFirewallResult(False, None, (), issues=("SQL query is empty.",))
        if len(sql) > self._policy.max_sql_length:
            return SQLFirewallResult(False, None, (), issues=("SQL query exceeds configured maximum length.",))

        try:
            statements = sqlglot.parse(sql, read="postgres")
        except Exception as exc:
            return SQLFirewallResult(False, None, (), issues=(f"SQL parsing failed: {type(exc).__name__}",))

        issues: list[str] = []
        if len(statements) != 1:
            issues.append("Multiple SQL statements are not allowed.")
        parsed: exp.Expression | None = statements[0] if statements else None
        if parsed is None:
            return SQLFirewallResult(False, None, (), issues=tuple(issues or ["No SQL statement parsed."]))
        if not isinstance(parsed, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
            issues.append("Only read-only SELECT queries are allowed.")

        for node in parsed.walk():
            if type(node) in self._FORBIDDEN_NODES:
                issues.append(f"Forbidden SQL operation: {type(node).__name__}")

        for select in parsed.find_all(exp.Select):
            for projection in select.expressions:
                if isinstance(projection, exp.Star):
                    issues.append("SELECT * is not allowed.")
                elif isinstance(projection, exp.Column) and projection.name == "*":
                    issues.append("SELECT table.* is not allowed.")

        forbidden_functions: set[str] = set()
        for function in parsed.find_all(exp.Func):
            name: str = str(getattr(function, "name", "") or "").upper()
            if not name:
                try:
                    name = function.sql_name().upper()
                except Exception:
                    name = ""
            if name in self._FORBIDDEN_FUNCTIONS:
                forbidden_functions.add(name)
                issues.append(f"Forbidden SQL function: {name}")

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
                    if table.name and table.name.lower() not in cte_names
                }
            )
        )
        for table in tables:
            if not self._policy.is_table_allowed(table):
                issues.append(f"Table is not allowed: {table}")

        return SQLFirewallResult(
            allowed=not issues,
            statement_type=type(parsed).__name__,
            tables=tables,
            forbidden_functions=tuple(sorted(forbidden_functions)),
            issues=tuple(dict.fromkeys(issues)),
        )
