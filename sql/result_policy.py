from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class SanitizedResult:
    """
    Result after applying output size policies.
    """
    rows: tuple[Mapping[str, Any], ...]
    columns: tuple[str, ...]
    row_count: int
    truncated: bool


class ResultPolicy:
    """
    Controls query result size and shape.
    """
    def __init__(self, *, max_rows: int = 1000 ) -> None:
        self._max_rows = max_rows

    def apply(self,   rows: Sequence[Mapping[str, Any]]) -> SanitizedResult:
        """
        Limit result size.
        """
        truncated = len(rows) > self._max_rows
        limited_rows = rows[:self._max_rows]
        columns = tuple(limited_rows[0].keys()) if limited_rows else ()

        return SanitizedResult(
            rows=tuple(limited_rows),
            columns=columns,
            row_count=len(limited_rows),
            truncated=truncated,
        )