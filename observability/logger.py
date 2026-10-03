import json
import logging

from observability.events import AgentEvent
from config.settings import LOG_CONFIG


class AgentLogger:
    """
    Central logger for agent execution events.
    """

    def __init__(self):

        self.logger = logging.getLogger(LOG_CONFIG.service_name)
        self.logger.setLevel(LOG_CONFIG.log_level)
        self._setup_handlers()

    def _setup_handlers(self):
        """
        Configure log output handlers.
        """

        formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

        if LOG_CONFIG.enable_console:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)

        if LOG_CONFIG.enable_file:
            file_handler = logging.FileHandler(LOG_CONFIG.log_file_path)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

    def log(self,event: AgentEvent) -> None:
        """
        Write an agent event into logs.

        Args:
            event:
                AgentEvent instance

        Returns:
            None
        """

        payload = {
            "event_type":
                event.event_type.value,
            "trace_id":
                event.trace_id,
            "timestamp":
                event.timestamp.isoformat(),
            "agent_name":
                event.agent_name,
            "stage_name":
                event.stage_name,
            "tool_name":
                event.tool_name,
            "input_data":
                event.input_data,
            "output_data":
                event.output_data,
            "latency_ms":
                event.latency_ms,
            "model_name":
                event.model_name,
            "prompt_version":
                event.prompt_version,
            "token_usage":
                event.token_usage,
            "status":
                event.status,
            "error_type":
                event.error_type,
            "error_message":
                event.error_message,
            "metadata":
                event.metadata
        }

        self.logger.info(json.dumps(payload,ensure_ascii=False))
