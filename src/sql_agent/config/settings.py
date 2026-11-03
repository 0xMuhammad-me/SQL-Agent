from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()
import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LLMSettings:
    model: str = os.getenv("LLM_MODEL", "")
    api_key: str = os.getenv("PROVIDER_API_KEY", "")
    base_url: str = os.getenv("PROVIDER_BASE_URL", "https://api.openai.com/v1")
    temperature: float = float(os.getenv("LLM_TEMPERATURE", "0"))
    max_retry: int = int(os.getenv("LLM_MAX_RETRY", "3"))
    timeout_seconds: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "60"))


@dataclass(frozen=True, slots=True)
class DatabaseSettings:
    host: str = os.getenv("DB_HOST", "localhost")
    port: int = int(os.getenv("DB_PORT", "5432"))
    database: str = os.getenv("DB_NAME", "postgres")
    user: str = os.getenv("DB_USER", "postgres")
    password: str = os.getenv("DB_PASSWORD", "")
    statement_timeout_ms: int = int(os.getenv("DB_STATEMENT_TIMEOUT_MS", "30000"))

    @property
    def connection_string(
            self) -> str: return f"host={self.host} port={self.port} dbname={self.database} user={self.user} password={self.password}"


@dataclass(frozen=True, slots=True)
class SecuritySettings:
    role_name: str = os.getenv("AGENT_ROLE", "analyst")
    allow_pii_access: bool = os.getenv("ALLOW_PII_ACCESS", "false").lower() == "true"
    max_query_rows: int = int(os.getenv("MAX_QUERY_ROWS", "1000"))
    max_result_bytes: int = int(os.getenv("MAX_RESULT_BYTES", "5000000"))
    max_sql_length: int = int(os.getenv("MAX_SQL_LENGTH", "50000"))
    max_query_cost: float = float(os.getenv("MAX_QUERY_COST", "100000"))
    max_estimated_rows: int = int(os.getenv("MAX_ESTIMATED_ROWS", "1000000"))
    allowed_tables_csv: str = os.getenv("ALLOWED_TABLES", "")

    @property
    def allowed_tables(self) -> frozenset[str]: return frozenset(
        x.strip().lower() for x in self.allowed_tables_csv.split(",") if x.strip())


@dataclass(frozen=True, slots=True)
class ObservabilitySettings:
    service_name: str = os.getenv("SERVICE_NAME", "sql-agent")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_file_path: str = os.getenv("LOG_FILE_PATH", "logs/sql_agent.log")
    enable_console: bool = os.getenv("ENABLE_CONSOLE_LOG", "true").lower() == "true"
    enable_file: bool = os.getenv("ENABLE_FILE_LOG", "true").lower() == "true"
    json_logging: bool = os.getenv("JSON_LOGGING", "true").lower() == "true"


@dataclass(frozen=True, slots=True)
class AgentSettings:
    max_repair_attempts: int = int(os.getenv("MAX_REPAIR_ATTEMPTS", "2"))
    minimum_repair_confidence: float = float(os.getenv("MIN_REPAIR_CONFIDENCE", "0.70"))


@dataclass(frozen=True, slots=True)
class BenchmarkSettings:
    dataset_path: str = os.getenv("BENCHMARK_DATASET_PATH", "evaluation/benchmark_questions.csv")
    report_path: str = os.getenv("BENCHMARK_REPORT_PATH", "reports/evaluation.json")


LLM_CONFIG = LLMSettings()
DB_CONFIG = DatabaseSettings()
SECURITY_CONFIG = SecuritySettings()
OBSERVABILITY_CONFIG = ObservabilitySettings()
AGENT_CONFIG = AgentSettings()
BENCHMARK_CONFIG = BenchmarkSettings()
