from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class SecurityPolicy:
    role_name: str = "analyst"
    allow_pii_access: bool = False
    max_query_rows: int = 1000
    max_result_bytes: int = 5_000_000
    max_sql_length: int = 50_000
    allowed_tables: frozenset[str] = field(default_factory=frozenset)

    def is_table_allowed(self, name: str) -> bool: return not self.allowed_tables or name.lower() in self.allowed_tables
