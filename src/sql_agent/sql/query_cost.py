from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Protocol


class CostStatus(str, Enum):
    ALLOWED = "allowed"
    TOO_EXPENSIVE = "too_expensive"
    INCONCLUSIVE = "inconclusive"


class CostDatabase(Protocol):
    def explain(self, sql: str, parameters: Mapping[str, Any]) -> Mapping[str, Any]: ...


@dataclass(frozen=True, slots=True)
class CostGuardResult:
    status: CostStatus
    estimated_cost: float | None = None
    estimated_rows: int | None = None
    reason: str | None = None

    @property
    def allowed(self) -> bool: return self.status == CostStatus.ALLOWED


class QueryCostGuard:
    def __init__(self, database: CostDatabase, *, max_cost: float = 100000.0,
                 max_estimated_rows: int = 1000000) -> None:
        self._db = database
        self._max_cost = max_cost
        self._max_rows = max_estimated_rows

    def validate(self, sql: str, parameters: Mapping[str, Any]) -> CostGuardResult:
        try:
            plan = self._db.explain(sql, parameters)
            cost = self._number(plan, "Total Cost")
            rows = self._integer(plan, "Plan Rows")

            if cost is not None and cost > self._max_cost:
                return CostGuardResult(
                    CostStatus.TOO_EXPENSIVE,
                    cost,
                    rows,
                    (
                        f"Estimated query cost {cost:.2f} "
                        f"exceeds configured maximum {self._max_cost:.2f}."
                    ),
                )

            if rows is not None and rows > self._max_rows:
                return CostGuardResult(
                    CostStatus.TOO_EXPENSIVE,
                    cost,
                    rows,
                    (
                        f"Estimated row count {rows} "
                        f"exceeds configured maximum {self._max_rows}."
                    ),
                )

            return CostGuardResult(CostStatus.ALLOWED, cost, rows)
        except Exception as exc:
            return CostGuardResult(
                CostStatus.INCONCLUSIVE,
                reason=f"Unable to determine query cost: {type(exc).__name__}: {str(exc)}")

    @staticmethod
    def _number(plan: Mapping[str, Any], key: str) -> float | None:
        v = plan.get(key)
        return None if v is None else float(v)

    @staticmethod
    def _integer(plan: Mapping[str, Any], key: str) -> int | None:
        v = plan.get(key)
        return None if v is None else int(v)
