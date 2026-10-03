from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp

from security.policy import SecurityPolicy


@dataclass(frozen=True)
class SQLFirewallResult:
    """Structured result returned by the SQL firewall."""

    allowed: bool
    statement_type: str | None
    tables: tuple[str, ...]
    issues: tuple[str, ...] = field(default_factory=tuple)


class SQLFirewall:
    """Validates SQL before it reaches the database executor."""

    _FORBIDDEN_NODE_NAMES: frozenset[str] = frozenset(
        {
            "Insert",
            "Update",
            "Delete",
            "Drop",
            "Alter",
            "Create",
            "TruncateTable",
            "Grant",
            "Revoke",
            "Command",
            "Copy",
        }
    )

    _FORBIDDEN_FUNCTIONS: frozenset[str] = frozenset(
        {
            "PG_READ_FILE",
            "PG_READ_BINARY_FILE",
            "PG_LS_DIR",
            "PG_STAT_FILE",
            "PG_SLEEP",
            "DBLINK_CONNECT",
            "DBLINK",
        }
    )

    def __init__(self, policy: SecurityPolicy) -> None:
        self._policy = policy

    def validate(self, sql: str) -> SQLFirewallResult:
        """Parse and validate one SQL statement."""

        issues: list[str] = []
        normalized_sql = sql.strip().upper()

        if not normalized_sql:
            return SQLFirewallResult(
                allowed=False,
                statement_type=None,
                tables=(),
                issues=("SQL query is empty.",),
            )

        if len(normalized_sql) > self._policy.max_sql_length:
            return SQLFirewallResult(
                allowed=False,
                statement_type=None,
                tables=(),
                issues=(
                    "SQL query exceeds configured maximum length.",
                ),
            )

        try:
            statements = sqlglot.parse(
                normalized_sql,
                read="postgres",
            )
        except Exception as exc:
            return SQLFirewallResult(
                allowed=False,
                statement_type=None,
                tables=(),
                issues=(
                    f"SQL parsing failed: {type(exc).__name__}",
                ),
            )

        if len(statements) != 1:
            issues.append(
                "Multiple SQL statements are not allowed."
            )
            parsed = statements[0] if statements else None
        else:
            parsed = statements[0]

        if parsed is None:
            return SQLFirewallResult(
                allowed=False,
                statement_type=None,
                tables=(),
                issues=tuple(issues),
            )

        statement_type = type(parsed).__name__

        if not isinstance(
                parsed,
                (
                        exp.Select,
                        exp.Union,
                        exp.Intersect,
                        exp.Except,
                ),
        ):
            issues.append("Only read-only SELECT queries are allowed.")

        for node in parsed.walk():
            node_name = type(node).__name__

            if node_name in self._FORBIDDEN_NODE_NAMES:
                issues.append(f"Forbidden SQL operation: {node_name}")

        table_names = tuple(
            sorted(
                {
                    table.name
                    for table in parsed.find_all(exp.Table)
                    if table.name
                }
            )
        )

        for table_name in table_names:
            if not self._policy.is_table_allowed(table_name):
                issues.append(f"Table is not allowed: {table_name}")

        sql_upper = normalized_sql.upper()

        for function_name in self._FORBIDDEN_FUNCTIONS:
            if function_name in sql_upper:
                issues.append(
                    f"Forbidden SQL function detected: "
                    f"{function_name}"
                )

        return SQLFirewallResult(
            allowed=not issues,
            statement_type=statement_type,
            tables=table_names,
            issues=tuple(sorted(set(issues))),
        )
