from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence
from security.pii_guard import PIIGuard


@dataclass(frozen=True, slots=True)
class SanitizedResult:
    rows: tuple[Mapping[str, Any], ...]
    columns: tuple[str, ...]
    row_count: int
    truncated: bool
    redacted_pii: bool


class ResultPolicy:
    def __init__(self, *, max_rows: int = 1000, max_bytes: int = 5000000, pii_guard: PIIGuard | None = None) -> None:
        self._max_rows = max_rows;self._max_bytes = max_bytes;self._pii = pii_guard or PIIGuard()

    def apply(self, rows: Sequence[Mapping[str, Any]], *, allow_pii: bool) -> SanitizedResult:
        data = [dict(r) for r in rows[:self._max_rows]]
        truncated = len(rows) > self._max_rows
        cols = tuple(data[0].keys()) if data else ()
        redacted = False

        if self._pii.find_pii_columns(cols) and not allow_pii:
            data = list(self._pii.redact_rows(data))
            redacted = True

        truncated = len(rows) > self._max_rows

        while data and self._size(data) > self._max_bytes:
            data.pop()
            truncated = True
        result = tuple(data)
        return SanitizedResult(result, tuple(result[0].keys()) if result else cols, len(result), truncated, redacted)

    @staticmethod
    def _size(rows: Sequence[Mapping[str, Any]]) -> int:
        return len(json.dumps(list(rows), ensure_ascii=False, default=str).encode())
