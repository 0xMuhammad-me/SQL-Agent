from __future__ import annotations

from typing import Any, Mapping

from sql.query_cost import CostGuardResult, QueryCostGuard
from sql.validator import SQLValidationResult, SQLValidator


class SQLTools:
    """
    Backend-controlled SQL validation and cost-checking tools.
    """

    def __init__(self, validator: SQLValidator, cost_guard: QueryCostGuard) -> None:
        self._validator: SQLValidator = validator
        self._cost_guard: QueryCostGuard = cost_guard

    def validate(self, sql: str, parameters: Mapping[str, Any]) -> SQLValidationResult:
        """
        Validate generated SQL before execution.
        """
        return self._validator.validate(sql=sql, parameters=parameters)

    def check_cost(self, sql: str, parameters: Mapping[str, Any]) -> CostGuardResult:
        """
        Check whether the query is within configured cost limits.
        """

        return self._cost_guard.validate(sql=sql, parameters=parameters)

    def validate_and_check_cost(self, sql: str, parameters: Mapping[str, Any]) -> dict[str, Any]:
        """
        Validate SQL and then check query cost.
        """
        validation_result: SQLValidationResult = self.validate(sql=sql, parameters=parameters)

        if not validation_result.valid:
            return {
                "valid": False,
                "validation": validation_result,
                "cost": None,
            }

        cost_result: CostGuardResult = self.check_cost(sql=sql, parameters=parameters)
        return {
            "valid": cost_result.allowed,
            "validation": validation_result,
            "cost": cost_result,
        }
