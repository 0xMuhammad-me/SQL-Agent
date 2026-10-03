from __future__ import annotations

from typing import Any, Mapping, Sequence

from security import PIIGuard
from sql.executor import DatabaseExecutionResult, DatabaseExecutor
from sql.result_policy import ResultPolicy, SanitizedResult


class ExecutionTools:
    """
    Backend-controlled database execution tools.
    """

    def __init__(self, executor: DatabaseExecutor, result_policy: ResultPolicy, pii_guard: PIIGuard) -> None:
        self._executor: DatabaseExecutor = executor
        self._result_policy: ResultPolicy = result_policy
        self._pii_guard = pii_guard

    def execute(self, sql: str, parameters: Mapping[str, Any]) -> DatabaseExecutionResult:
        """
        Execute one validated read-only SQL query.
        """
        return self._executor.execute(sql=sql, parameters=parameters)

    def sanitize(self, rows: Sequence[Mapping[str, Any]], allow_pii: bool) -> SanitizedResult:
        """
        Validate and redact PII, then apply result-size policies.
        """

        if not rows:
            return self._result_policy.apply(rows)

        columns: list[str] = list(rows[0].keys())
        self._pii_guard.validate_columns(columns=columns, allow_pii=allow_pii)
        rows_for_pii: list[dict[str, Any]] = [dict(row) for row in rows]
        redacted_rows: list[dict[str, Any]] = self._pii_guard.redact_rows(rows_for_pii)

        return self._result_policy.apply(redacted_rows)


def execute_and_sanitize(self, sql: str, parameters: Mapping[str, Any]) -> dict[str, Any]:
    """
    Execute SQL and sanitize successful results.
    """
    execution_result: DatabaseExecutionResult = self.execute(sql=sql, parameters=parameters)

    if not execution_result.success:
        return {"execution": execution_result, "result": None}

    sanitized_result: SanitizedResult = self.sanitize(execution_result.rows)
    return {"execution": execution_result, "result": sanitized_result}
