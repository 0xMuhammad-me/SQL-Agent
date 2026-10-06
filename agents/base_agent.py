from __future__ import annotations

from functools import wraps
from time import perf_counter
from typing import Any, Callable, Concatenate, Generic, Mapping, ParamSpec, Sequence, TypeVar
from pydantic import BaseModel

from core.context import AgentContext
from core.llm_client import LLMClient, LLMResponse
from errors import AgentError
from observability import AgentEvent, AgentLogger, EventType

P = ParamSpec("P")
R = TypeVar("R")
T = TypeVar("T")


def agent_lifecycle(
        func: Callable[Concatenate["BaseAgent[Any]", P], R],
) -> Callable[Concatenate["BaseAgent[Any]", P], R]:
    """Wrap a typed agent method with shared telemetry and timing."""

    @wraps(func)
    def wrapper(self: BaseAgent[Any], *args: P.args, **kwargs: P.kwargs) -> R:
        context: AgentContext = _extract_context(kwargs)
        stage_name: str = self.stage_name
        started_at: float = perf_counter()
        self._log_started(context=context, stage_name=stage_name, input_data=self._start_metadata(dict(kwargs)))

        try:
            result: R = func(self, *args, **kwargs)
        except Exception as exc:
            latency_ms: float = (perf_counter() - started_at) * 1000.0
            self._log_error(context=context, stage_name=stage_name, error=exc, latency_ms=latency_ms)
            raise

        latency_ms = (perf_counter() - started_at) * 1000.0
        self._log_completed(
            context=context,
            stage_name=stage_name,
            output_data=self._result_metadata(result),
            latency_ms=latency_ms,
        )
        return result

    return wrapper


def _extract_context(kwargs: dict[str, Any]) -> AgentContext:
    """Extract and validate the request context from method arguments."""
    context: Any = kwargs.get("context")
    if not isinstance(context, AgentContext):
        raise TypeError("Agent methods require a valid 'context' argument.")
    return context


class BaseAgent(Generic[T]):
    """Shared dependencies and observability helpers for LLM-driven agents."""

    agent_name: str
    prompt_name: str
    prompt_version: str

    def __init__(
            self,
            *,
            llm_client: LLMClient,
            logger: AgentLogger,
            model_name: str | None = None,
    ) -> None:
        self.llm_client: LLMClient = llm_client
        self.logger: AgentLogger = logger
        self.model_name: str | None = model_name

    @property
    def stage_name(self) -> str:
        """Return the stable workflow stage name."""
        return self.agent_name

    def _effective_model_name(self) -> str | None:
        """Resolve the configured model without mutating shared agent state."""
        return self.model_name or getattr(self.llm_client, "default_model", None)

    def _start_metadata(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        """Return safe, lightweight input metadata for telemetry."""
        return {
            "argument_names": sorted(
                key for key in kwargs.keys() if key != "context"
            )
        }

    def _result_metadata(self, result: Any) -> dict[str, Any]:
        """Return safe, lightweight output metadata for telemetry."""
        if isinstance(result, BaseModel):
            return {"result_type": type(result).__name__}
        if isinstance(result, str):
            return {"result_type": "str", "length": len(result)}
        return {"result_type": type(result).__name__}

    def _log_started(
            self,
            *,
            context: AgentContext,
            stage_name: str,
            input_data: dict[str, Any],
    ) -> None:
        """Record agent start."""
        self.logger.log(
            AgentEvent(
                event_type=EventType.AGENT_STARTED,
                trace_id=context.trace_id,
                agent_name=self.agent_name,
                stage_name=stage_name,
                input_data=input_data,
                model_name=self._effective_model_name(),
                prompt_version=self.prompt_version,
                status="started",
                metadata={"prompt_name": self.prompt_name},
            )
        )

    def _log_completed(
            self,
            *,
            context: AgentContext,
            stage_name: str,
            output_data: dict[str, Any],
            latency_ms: float,
    ) -> None:
        """Record successful agent completion."""
        usage: dict[str, int] = dict(
            context.metadata.pop(f"_llm_usage:{self.agent_name}", {})
        )
        response_model: str | None = context.metadata.pop(
            f"_llm_model:{self.agent_name}",
            self._effective_model_name(),
        )
        self.logger.log(
            AgentEvent(
                event_type=EventType.AGENT_COMPLETED,
                trace_id=context.trace_id,
                agent_name=self.agent_name,
                stage_name=stage_name,
                output_data=output_data,
                latency_ms=latency_ms,
                model_name=response_model,
                prompt_version=self.prompt_version,
                token_usage=usage,
                status="success",
                metadata={"prompt_name": self.prompt_name},
            )
        )

    def _log_error(
            self,
            *,
            context: AgentContext,
            stage_name: str,
            error: BaseException,
            latency_ms: float,
    ) -> None:
        """Record agent failure without changing the original exception type."""
        response_model: str | None = context.metadata.pop(
            f"_llm_model:{self.agent_name}",
            self._effective_model_name(),
        )
        usage: dict[str, int] = dict(
            context.metadata.pop(f"_llm_usage:{self.agent_name}", {})
        )
        metadata: dict[str, Any] = {"prompt_name": self.prompt_name}
        if isinstance(error, AgentError):
            metadata.update(
                {
                    "category": error.category,
                    "retryable": error.retryable,
                    "cause_type": type(error.cause).__name__ if error.cause else None,
                    "cause_message": str(error.cause)[:1000] if error.cause else None,
                    "details": error.details,
                }
            )
        self.logger.log(
            AgentEvent(
                event_type=EventType.ERROR,
                trace_id=context.trace_id,
                agent_name=self.agent_name,
                stage_name=stage_name,
                latency_ms=latency_ms,
                model_name=response_model,
                prompt_version=self.prompt_version,
                token_usage=usage,
                status="error",
                error_type=type(error).__name__,
                error_message=str(error),
                metadata=metadata,
            )
        )

    def _structured(
            self,
            *,
            context: AgentContext,
            system_prompt: str,
            user_prompt: str,
            response_model: type[T],
    ) -> T:
        """Call the structured LLM interface and retain request telemetry."""
        response: LLMResponse[T] = self.llm_client.generate_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=response_model,
            model=self.model_name,
        )
        context.metadata[f"_llm_usage:{self.agent_name}"] = response.usage.as_dict()
        context.metadata[f"_llm_model:{self.agent_name}"] = response.model_name
        return response.output

    def _structured_with_tools(
            self,
            *,
            context: AgentContext,
            system_prompt: str,
            user_prompt: str,
            response_model: type[T],
            tools: Sequence[Mapping[str, Any]],
            tool_executor: Callable[[str, Mapping[str, Any]], Any],
            max_tool_calls: int = 1,
    ) -> T:
        """Call the structured LLM interface with bounded tool use."""
        response: LLMResponse[T] = self.llm_client.generate_structured_with_tools(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=response_model,
            tools=tools,
            tool_executor=tool_executor,
            model=self.model_name,
            max_tool_calls=max_tool_calls,
        )

        context.metadata[f"_llm_usage:{self.agent_name}"] = response.usage.as_dict()
        context.metadata[f"_llm_model:{self.agent_name}"] = response.model_name

        return response.output

    def _text(
            self,
            *,
            context: AgentContext,
            system_prompt: str,
            user_prompt: str,
    ) -> str:
        """Call the text LLM interface and retain request telemetry."""
        response: LLMResponse[str] = self.llm_client.generate_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=self.model_name,
        )
        context.metadata[f"_llm_usage:{self.agent_name}"] = response.usage.as_dict()
        context.metadata[f"_llm_model:{self.agent_name}"] = response.model_name
        return response.output
