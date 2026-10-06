from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Sequence


@dataclass(frozen=True, slots=True)
class PIIFieldPolicy:
    field_name: str
    category: str
    mask_value: str = "***REDACTED***"


DEFAULT_PII_FIELDS = (PIIFieldPolicy("email", "contact"), PIIFieldPolicy("phone", "contact"),
                      PIIFieldPolicy("birth_date", "personal"))


class PIIGuard:
    def __init__(self, fields: Sequence[PIIFieldPolicy] = DEFAULT_PII_FIELDS) -> None:
        self._fields = {x.field_name.lower(): x for x in fields}

    @staticmethod
    def normalize_column(c: str) -> str:
        return c.lower().split(".")[-1]

    def find_pii_columns(self, columns: Sequence[str]) -> tuple[str, ...]:
        s = {self.normalize_column(c) for c in columns}
        return tuple(x for x in self._fields if x in s)

    def redact_rows(self, rows: Sequence[dict[str, Any]]) -> tuple[dict[str, Any], ...]:
        out = []
        for row in rows:
            r = dict(row)
            for c in row:
                p = self._fields.get(self.normalize_column(c))
                if p: r[c] = p.mask_value
            out.append(r)
        return tuple(out)
