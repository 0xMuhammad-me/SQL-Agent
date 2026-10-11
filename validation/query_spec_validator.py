from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from agent_schemas import QuerySpec, RequestType
from tools.metadata_tools import RelevantMetadata


@dataclass(frozen=True, slots=True)
class QuerySpecValidationResult:
    valid: bool
    issues: tuple[str, ...] = ()


class QuerySpecValidator:
    """Deterministically validate a QuerySpec against retrieved metadata."""

    def validate(self, query_spec: QuerySpec, metadata: RelevantMetadata) -> QuerySpecValidationResult:
        """Validate QuerySpec references against already retrieved metadata."""

        if query_spec.request_type != RequestType.QUERY:
            return QuerySpecValidationResult(True)

        issues: list[str] = []

        if query_spec.metric:
            metric_exists: bool = any(
                str(metric.get("name", "")).strip().lower()
                == query_spec.metric.strip().lower()
                for metric in metadata.metrics
            )

            if not metric_exists:
                issues.append(f"Unknown metric: {query_spec.metric}")

        fields: list[str] = [
            *query_spec.dimensions,
            *(item.field for item in query_spec.filters),
            *(item.field for item in query_spec.sort),
        ]

        if query_spec.time_range is not None:
            fields.append(query_spec.time_range.field)

        for field in fields:
            if not self._field_exists(field, metadata):
                issues.append(f"Unresolvable semantic field: {field}")

        return QuerySpecValidationResult(valid=not issues, issues=tuple(dict.fromkeys(issues)))

    @classmethod
    def _field_exists(cls, field: str, metadata: RelevantMetadata) -> bool:
        """Check whether a semantic field can be matched to retrieved schema metadata."""

        normalized: str = cls._normalize_field(field)

        if not normalized:
            return False

        if "." in normalized:
            table_name, column_name = normalized.split(".", 1)

            for table in metadata.schema:
                if cls._normalize_field(str(table.get("name", ""))) != table_name:
                    continue

                columns: tuple[dict[str, Any], ...] = tuple(table.get("columns", ()))

                return any(
                    cls._normalize_field(str(column.get("name", ""))) == column_name for column in columns)

            return False

        for table in metadata.schema:
            columns: tuple[dict[str, Any], ...] = tuple(table.get("columns", ()))

            for column in columns:
                column_name: str = cls._normalize_field(str(column.get("name", "")))

                if column_name == normalized:
                    return True

        return False

    @staticmethod
    def _normalize_field(value: str) -> str:
        """Normalize natural-language and SQL-style field names for comparison."""

        normalized: str = value.strip().lower()

        normalized = re.sub(r"[^a-z0-9_]+", "_", normalized)

        normalized = re.sub(r"_+", "_", normalized)
        return normalized.strip("_")
