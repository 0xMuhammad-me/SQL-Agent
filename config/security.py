from dataclasses import dataclass

@dataclass(frozen=True)
class SecurityConfig:

    allow_write_queries:bool=False
    allow_pii_access:bool=False
    max_query_rows:int=1000
    sql_timeout_seconds:int=30
    

SECURITY_CONFIG = SecurityConfig()