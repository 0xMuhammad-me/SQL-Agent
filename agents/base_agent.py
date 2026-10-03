from __future__ import annotations

from abc import ABC
from typing import Any, Generic, Protocol, TypeVar

from pydantic import BaseModel

from core.context import AgentContext
from errors.exceptions import LLMError
from observability.events import AgentEvent, EventType
from observability.logger import AgentLogger

T = TypeVar("T", bound=BaseModel)


class LLMClient(Protocol):
    """
    Interface expected from the application's LLM client.

    The concrete implementation belongs in core/llm_client.py.
    """

    def generate_structured(self, *, system_prompt: str, user_prompt: str, response_model: type[T],
                            model: str | None = None,
                            ) -> T:
        """
        Generate and validate a structured response.

        Returns:
            An instance of the requested Pydantic model.
        """
        ...

    def generate_text(self, *, system_prompt: str, user_prompt: str, model: str | None = None) -> str:
        """
        Generate plain text.

        Returns:
            Generated text.
        """
        ...


class BaseAgent(ABC, Generic[T]):
    """Base functionality shared by LLM-driven agents."""

    agent_name: str
    prompt_name: str
    prompt_version: str

    def __init__(self, *, llm_client: LLMClient, logger: AgentLogger, model_name: str | None = None) -> None:
        self.llm_client: LLMClient = llm_client
        self.logger: AgentLogger = logger
        self.model_name: str | None = model_name

    def _log_started(self, *, context: AgentContext, stage_name: str, input_data: dict[str, Any]) -> None:
        """
        Record the beginning of an agent execution.

        Sensitive values should be redacted by the observability layer.
        """

        self.logger.log(
            AgentEvent(
                event_type=EventType.AGENT_STARTED,
                trace_id=context.trace_id,
                agent_name=self.agent_name,
                stage_name=stage_name,
                input_data=input_data,
                model_name=self.model_name,
                prompt_version=self.prompt_version,
                metadata={
                    "prompt_name": self.prompt_name,
                },
            )
        )

    def _log_completed(
            self,
            *,
            context: AgentContext,
            stage_name: str,
            output_data: dict[str, Any],
            latency_ms: float | None = None,
    ) -> None:
        """Record successful agent completion."""

        self.logger.log(
            AgentEvent(
                event_type=EventType.AGENT_COMPLETED,
                trace_id=context.trace_id,
                agent_name=self.agent_name,
                stage_name=stage_name,
                output_data=output_data,
                latency_ms=latency_ms,
                model_name=self.model_name,
                prompt_version=self.prompt_version,
                metadata={
                    "prompt_name": self.prompt_name,
                },
            )
        )

    def _log_error(self, *, context: AgentContext, stage_name: str, error: BaseException) -> None:
        """Record an agent failure."""

        self.logger.log(
            AgentEvent(
                event_type=EventType.ERROR,
                trace_id=context.trace_id,
                agent_name=self.agent_name,
                stage_name=stage_name,
                status="error",
                error_type=type(error).__name__,
                error_message=str(error),
                model_name=self.model_name,
                prompt_version=self.prompt_version,
                metadata={
                    "prompt_name": self.prompt_name,
                },
            )
        )

    def _raise_llm_error(self, error: BaseException) -> LLMError:
        """
        Normalize unexpected LLM client failures into an AgentError.

        Already-classified AgentError instances should normally be
        propagated by the concrete client.
        """

        if isinstance(error, LLMError):
            return error

        return LLMError(
            "LLM agent execution failed.",
            retryable=False,
            cause=error,
            details={
                "agent_name": self.agent_name,
                "prompt_name": self.prompt_name,
                "prompt_version": self.prompt_version,
            },
        )
