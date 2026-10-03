from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PIIFieldPolicy:
    """Policy describing one PII field."""

    field_name: str
    category: str
    mask_value: str = "***REDACTED***"


DEFAULT_PII_FIELDS: tuple[PIIFieldPolicy, ...] = (
    PIIFieldPolicy(field_name="email",category="contact"),
    PIIFieldPolicy(field_name="phone",category="contact"),
    PIIFieldPolicy(field_name="birth_date",category="personal"),
)


class PIIGuard:
    """Detects and optionally masks PII fields in query results."""

    def __init__(self, pii_fields: tuple[PIIFieldPolicy, ...] = DEFAULT_PII_FIELDS) -> None:
        self._pii_fields = {
            field.field_name: field
            for field in pii_fields
        }

    @staticmethod
    def _normalize_column(column: str) -> str:
        return column.lower().split(".")[-1]


    def find_pii_columns(self, columns: list[str]) -> list[str]:
        """Return PII columns present in a result or selection."""

        normalized_columns = {
            self._normalize_column(column)
            for column in columns
        }

        return [field_name for field_name in self._pii_fields if field_name in normalized_columns]

    def validate_columns(self, columns: list[str], allow_pii: bool) -> None:
        """Raise PermissionError when PII is present but not allowed."""

        if allow_pii:
            return

        pii_columns = self.find_pii_columns(columns)

        if pii_columns:
            raise PermissionError(
                "PII access is not allowed for columns: "
                + ", ".join(pii_columns)
            )

    def redact_rows(self, rows: list[dict[str, Any]],) -> list[dict[str, Any]]:
        """Return a copy of rows with known PII fields masked."""

        redacted_rows: list[dict[str, Any]] = []

        for row in rows:
            redacted_row = dict(row)

            for column_name in row:
                field_name = self._normalize_column(column_name)

                if field_name in self._pii_fields:
                    policy = self._pii_fields[field_name]
                    redacted_row[column_name] = policy.mask_value

            redacted_rows.append(redacted_row)

        return redacted_rows