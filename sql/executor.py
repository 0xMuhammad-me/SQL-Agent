from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Mapping

import psycopg
from psycopg.rows import dict_row


@dataclass(frozen=True, slots=True)
class DatabaseExecutionResult:
    """
    Result of one database execution.
    """

    success: bool
    rows: tuple[Mapping[str, Any], ...] = ()
    columns: tuple[str, ...] = ()

    validation_passed: bool = False
    cost_check_passed: bool = False

    row_count: int = 0
    execution_ms: float = 0.0

    error_type: str | None = None
    error_message: str | None = None


class DatabaseExecutor:
    """
    Read-only PostgreSQL executor.
    """

    def __init__(self, connection_string: str, *, statement_timeout_ms: int = 10_000, max_rows: int = 1_000) -> None:
        self._connection_string: str = connection_string
        self._statement_timeout_ms: int = statement_timeout_ms
        self._max_rows: int = max_rows

    def execute(self, sql: str, parameters: Mapping[str, Any], *, validated: bool = False) -> DatabaseExecutionResult:
        """
        Execute a read-only SQL query.
        """
        started_at: float = perf_counter()
        try:
            rows: list[Mapping[str, Any]]
            with psycopg.connect(self._connection_string, row_factory=dict_row) as connection:
                connection.autocommit = False

                with connection.cursor() as cursor:
                    cursor.execute("SET TRANSACTION READ ONLY")
                    cursor.execute("SET LOCAL statement_timeout = %s",(self._statement_timeout_ms,))
                    if not validated:
                        raise RuntimeError("SQL must be validated before execution.")

                    cursor.execute(sql, dict(parameters))
                    fetched_rows: list[Mapping[str, Any]] = cursor.fetchmany(self._max_rows)
                    rows = [dict(row) for row in fetched_rows]

                connection.rollback()

            execution_ms: float = (perf_counter() - started_at) * 1000.0
            columns: tuple[str, ...] = (tuple(rows[0].keys()) if rows else ())

            return DatabaseExecutionResult(
                success=True,
                rows=tuple(rows),
                columns=columns,
                row_count=len(rows),
                execution_ms=execution_ms,
                validation_passed=True,
                cost_check_passed=True
            )

        except psycopg.Error as exc:
            execution_ms: float = (perf_counter() - started_at) * 1000.0

            return DatabaseExecutionResult(
                success=False,
                rows=(),
                columns=(),
                row_count=0,
                execution_ms=execution_ms,
                error_type=type(exc).__name__,
                error_message=str(exc)
            )

        except Exception as exc:
            execution_ms: float = (perf_counter() - started_at) * 1000.0

            return DatabaseExecutionResult(
                success=False,
                rows=(),
                columns=(),
                row_count=0,
                execution_ms=execution_ms,
                error_type=type(exc).__name__,
                error_message=str(exc)
            )
