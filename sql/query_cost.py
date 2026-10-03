from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol


class CostDatabase(Protocol):
    """
    Minimal database interface required by the cost guard.
    """

    def explain(self, sql: str, parameters: Mapping[str, Any]) -> Mapping[str, Any]:
        """
        Return query execution plan information.
        """
        ...


@dataclass(frozen=True, slots=True)
class CostGuardResult:
    """
    Result of query cost validation.
    """

    allowed: bool
    estimated_cost: float | None
    estimated_rows: int | None
    validation_required: bool = True
    reason: str | None = None


class QueryCostGuard:
    """
    Prevents execution of excessively expensive queries.
    """

    def __init__(self, database: CostDatabase, *, max_cost: float = 100_000.0,
                 max_estimated_rows: int = 1_000_000) -> None:
        self._database: CostDatabase = database
        self._max_cost: float = max_cost
        self._max_estimated_rows: int = max_estimated_rows

    def validate(self, sql: str, parameters: Mapping[str, Any], *, validated: bool = False) -> CostGuardResult:
        """
        Validate query cost using EXPLAIN.
        """

        try:
            if not validated:
                return CostGuardResult(
                    allowed=False,
                    estimated_cost=None,
                    estimated_rows=None,
                    reason="SQL validation required before cost analysis."
                )

            plan: Mapping[str, Any] = self._database.explain(sql, parameters)
            estimated_cost: float | None = self._extract_cost(plan)
            estimated_rows: int | None = self._extract_rows(plan)

            if estimated_cost is not None and estimated_cost > self._max_cost:
                return CostGuardResult(
                    allowed=False,
                    estimated_cost=estimated_cost,
                    estimated_rows=estimated_rows,
                    reason=(
                        "Estimated query cost exceeds "
                        "the configured maximum."
                    ),
                )

            if estimated_rows is not None and estimated_rows > self._max_estimated_rows:
                return CostGuardResult(
                    allowed=False,
                    estimated_cost=estimated_cost,
                    estimated_rows=estimated_rows,
                    reason="Estimated row count exceeds the configured maximum."
                )

            return CostGuardResult(allowed=True, estimated_cost=estimated_cost, estimated_rows=estimated_rows)

        except Exception as exc:
            return CostGuardResult(
                allowed=False,
                estimated_cost=None,
                estimated_rows=None,
                reason=f"Unable to determine query cost: {type(exc).__name__}: {exc}"
            )

    @staticmethod
    def _extract_cost(plan: Mapping[str, Any]) -> float | None:
        """
        Extract estimated total cost from EXPLAIN output.
        """
        value: Any = plan.get("Total Cost")
        if value is None:
            return None
        return float(value)

    @staticmethod
    def _extract_rows(plan: Mapping[str, Any], ) -> int | None:
        """
        Extract estimated row count from EXPLAIN output.
        """
        value: Any = plan.get("Plan Rows")
        if value is None:
            return None

        return int(value)
