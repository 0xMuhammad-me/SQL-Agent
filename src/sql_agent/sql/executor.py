from __future__ import annotations
from dataclasses import dataclass
from time import perf_counter
from typing import Any, LiteralString, Mapping, cast
import psycopg
from psycopg.rows import dict_row


@dataclass(frozen=True, slots=True)
class DatabaseExecutionResult:
    success: bool
    rows: tuple[Mapping[str, Any], ...] = ()
    columns: tuple[str, ...] = ()
    row_count: int = 0
    execution_ms: float = 0.0
    truncated: bool = False
    error_type: str | None = None
    error_message: str | None = None


class DatabaseExecutor:
    def __init__(self, connection_string: str, *, statement_timeout_ms: int = 30000, max_rows: int = 1000) -> None:
        self._conn = connection_string;self._timeout = statement_timeout_ms;self._max_rows = max_rows

    def execute(self, sql: str, parameters: Mapping[str, Any]) -> DatabaseExecutionResult:
        start = perf_counter()
        try:
            with psycopg.connect(self._conn, row_factory=dict_row) as con:
                with con.cursor() as cur:
                    cur.execute("SET TRANSACTION READ ONLY")
                    cur.execute(
                        "SELECT set_config('statement_timeout', %s, true)",
                        (str(int(self._timeout)),),
                    )
                    cur.execute(cast(LiteralString, self._to_psycopg(sql)),dict(parameters))
                    fetched = cur.fetchmany(self._max_rows + 1)
                    truncated = len(fetched) > self._max_rows
                    rows = tuple(dict(r) for r in fetched[:self._max_rows])
                    cols = tuple(rows[0].keys()) if rows else ()
                con.rollback()
            return DatabaseExecutionResult(True, rows, cols, len(rows), (perf_counter() - start) * 1000.0, truncated)
        except Exception as exc:
            return DatabaseExecutionResult(False, execution_ms=(perf_counter() - start) * 1000.0,
                                           error_type=type(exc).__name__, error_message=str(exc))

    def explain(self, sql: str, parameters: Mapping[str, Any]) -> Mapping[str, Any]:
        with psycopg.connect(self._conn, row_factory=dict_row) as con:
            with con.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute(
                    "SELECT set_config('statement_timeout', %s, true)",
                    (str(int(self._timeout)),),
                )
                cur.execute(
                    cast(LiteralString,"EXPLAIN (FORMAT JSON) " + self._to_psycopg(sql)),
                    dict(parameters),
                )
                row = cur.fetchone()
            con.rollback()
        if not row: raise RuntimeError("EXPLAIN returned no plan.")
        value = next(iter(row.values()))
        if not isinstance(value, list) or not value or not isinstance(value[0], Mapping):
            raise RuntimeError("Unexpected EXPLAIN response shape.")
        return value[0]["Plan"]

    @staticmethod
    def _to_psycopg(sql: str) -> str:
        out: list[str] = []
        i = 0
        quote = None
        while i < len(sql):
            ch = sql[i]
            if quote:
                out.append(ch)
                if ch == quote:
                    if i + 1 < len(sql) and sql[i + 1] == quote:
                        out.append(sql[i + 1]);i += 1
                    else:
                        quote = None
                i += 1
                continue
            if ch in ("'", '"'): quote = ch;out.append(ch);i += 1;continue
            if ch == ":" and i + 1 < len(sql) and sql[i + 1] != ":":
                j = i + 1
                if sql[j].isalpha() or sql[j] == '_':
                    j += 1
                    while j < len(sql) and (sql[j].isalnum() or sql[j] == '_'): j += 1
                    out.append("%(" + sql[i + 1:j] + ")s")
                    i = j
                    continue
            out.append(ch)
            i += 1
        return "".join(out)
