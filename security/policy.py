from dataclasses import dataclass, field

@dataclass(frozen=True)
class SecurityPolicy:
    """Runtime security constraints for SQL agent execution."""

    allow_write_queries: bool = False
    allow_pii_access: bool = False
    max_query_rows: int = 1000
    query_timeout_seconds: int = 30
    max_sql_length: int = 50_000
    max_result_bytes: int = 5_000_000
    allowed_tables: frozenset[str] = field(default_factory=frozenset)

    def is_table_allowed(self,table_name: str,) -> bool:
        """Check whether a table is available to the agent."""

        if not self.allowed_tables:
            return True

        return table_name in self.allowed_tables