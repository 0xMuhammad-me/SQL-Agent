from dataclasses import dataclass

@dataclass(frozen=True)
class LoggingConfig:
    service_name:str = "sql-agent"
    log_level:str = "INFO"
    log_file_path:str = "logs/sql_agent.log"
    enable_console:bool = True
    enable_json_logging:bool = True


LOG_CONFIG = LoggingConfig()