from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Any, Callable, Generic, Mapping, Sequence, TypeVar, cast
from openai import APIConnectionError, APIError, APITimeoutError, OpenAI, RateLimitError as OpenAIRateLimitError
from openai.types.responses import (
    FunctionToolParam,
    ResponseInputItemParam,
)
from config.settings import LLM_CONFIG
from errors import ExternalTimeoutError, LLMError, NetworkError, RateLimitError
from errors.retry import retry_call

T = TypeVar("T")
ToolExecutor = Callable[[str, Mapping[str, Any]], Any]


@dataclass(frozen=True, slots=True)
class LLMUsage:
    """Token usage metadata for one LLM request."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass(frozen=True, slots=True)
class LLMResponse(Generic[T]):
    """Standardized LLM response returned to the agent layer."""

    output: T
    model_name: str
    response_id: str | None
    usage: LLMUsage


class LLMClient:
    """Provider-neutral LLM interface."""

    def generate_text(
            self,
            *,
            system_prompt: str,
            user_prompt: str,
            model: str | None = None,
    ) -> LLMResponse[str]:
        raise NotImplementedError

    def generate_structured(
            self,
            *,
            system_prompt: str,
            user_prompt: str,
            response_model: type[T],
            model: str | None = None,
    ) -> LLMResponse[T]:
        raise NotImplementedError

    def generate_structured_with_tools(
            self,
            *,
            system_prompt: str,
            user_prompt: str,
            response_model: type[T],
            tools: Sequence[Mapping[str, Any]],
            tool_executor: ToolExecutor,
            model: str | None = None,
            max_tool_calls: int = 1,
    ) -> LLMResponse[T]:
        raise NotImplementedError


class ProviderClient(LLMClient):
    """LLM Responses API implementation of the provider-neutral client."""

    def __init__(
            self,
            *,
            api_key: str | None = None,
            default_model: str | None = None,
            timeout_seconds: float | None = None,
    ) -> None:
        key: str = api_key or LLM_CONFIG.api_key
        if not key:
            raise ValueError("PROVIDER_API_KEY is not configured.")
        self.client: OpenAI = OpenAI(api_key=key, base_url="https://api.avalai.ir/v1")
        self.default_model: str = default_model or LLM_CONFIG.model
        self.timeout_seconds: float = (
            timeout_seconds if timeout_seconds is not None else LLM_CONFIG.timeout_seconds
        )

    def generate_text(
            self,
            *,
            system_prompt: str,
            user_prompt: str,
            model: str | None = None,
    ) -> LLMResponse[str]:
        selected_model: str = model or self.default_model
        return retry_call(
            lambda: self._generate_text_once(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=selected_model,
            ),
            max_attempts=LLM_CONFIG.max_retry,
        )

    def generate_structured(
            self,
            *,
            system_prompt: str,
            user_prompt: str,
            response_model: type[T],
            model: str | None = None,
    ) -> LLMResponse[T]:
        selected_model: str = model or self.default_model
        return retry_call(
            lambda: self._generate_structured_once(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=response_model,
                model=selected_model,
            ),
            max_attempts=LLM_CONFIG.max_retry,
        )

    def generate_structured_with_tools(
            self,
            *,
            system_prompt: str,
            user_prompt: str,
            response_model: type[T],
            tools: Sequence[Mapping[str, Any]],
            tool_executor: ToolExecutor,
            model: str | None = None,
            max_tool_calls: int = 1,
    ) -> LLMResponse[T]:
        selected_model: str = model or self.default_model

        return retry_call(
            lambda: self._generate_structured_with_tools_once(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=response_model,
                tools=tools,
                tool_executor=tool_executor,
                model=selected_model,
                max_tool_calls=max_tool_calls,
            ),
            max_attempts=LLM_CONFIG.max_retry,
        )

    def _generate_text_once(
            self,
            *,
            system_prompt: str,
            user_prompt: str,
            model: str,
    ) -> LLMResponse[str]:
        try:
            response: Any = self.client.responses.create(
                model=model,
                instructions=system_prompt,
                input=user_prompt,
                timeout=self.timeout_seconds,
            )
            output: str = str(response.output_text or "").strip()
            if not output:
                raise LLMError("LLM returned empty text.", details={"model": model})
            return LLMResponse(
                output=output,
                model_name=model,
                response_id=getattr(response, "id", None),
                usage=self._usage(response),
            )
        except OpenAIRateLimitError as exc:
            raise RateLimitError(
                "LLM rate limit was reached.",
                cause=exc,
                details={"model": model},
            ) from exc
        except APITimeoutError as exc:
            raise ExternalTimeoutError(
                "LLM request timed out.",
                cause=exc,
                details={"model": model},
            ) from exc
        except APIConnectionError as exc:
            raise NetworkError(
                "Connection to LLM provider failed.",
                cause=exc,
                details={"model": model},
            ) from exc
        except APIError as exc:
            raise LLMError(
                "LLM provider returned an API error.",
                cause=exc,
                details={"model": model, "status_code": getattr(exc, "status_code", None)},
            ) from exc

    def _generate_structured_once(
            self,
            *,
            system_prompt: str,
            user_prompt: str,
            response_model: type[T],
            model: str,
    ) -> LLMResponse[T]:
        try:
            response: Any = self.client.responses.parse(
                model=model,
                instructions=system_prompt,
                input=user_prompt,
                text_format=response_model,
                timeout=self.timeout_seconds,
            )
            output: T | None = getattr(response, "output_parsed", None)
            if output is None:
                raise LLMError(
                    "LLM did not return a parsed structured response.",
                    details={"model": model},
                )
            return LLMResponse(
                output=output,
                model_name=model,
                response_id=getattr(response, "id", None),
                usage=self._usage(response),
            )
        except OpenAIRateLimitError as exc:
            raise RateLimitError(
                "LLM rate limit was reached.",
                cause=exc,
                details={"model": model},
            ) from exc
        except APITimeoutError as exc:
            raise ExternalTimeoutError(
                "LLM structured request timed out.",
                cause=exc,
                details={"model": model},
            ) from exc
        except APIConnectionError as exc:
            raise NetworkError(
                "Connection to LLM provider failed.",
                cause=exc,
                details={"model": model},
            ) from exc
        except APIError as exc:
            raise LLMError(
                "LLM provider returned an API error.",
                cause=exc,
                details={"model": model, "status_code": getattr(exc, "status_code", None)},
            ) from exc

    def _generate_structured_with_tools_once(
            self,
            *,
            system_prompt: str,
            user_prompt: str,
            response_model: type[T],
            tools: Sequence[Mapping[str, Any]],
            tool_executor: ToolExecutor,
            model: str,
            max_tool_calls: int,
    ) -> LLMResponse[T]:
        try:
            first_response: Any = self.client.responses.parse(
                model=model,
                instructions=system_prompt,
                input=user_prompt,
                text_format=response_model,
                tools=list(tools),
                tool_choice="auto",
                max_tool_calls=max_tool_calls,
                parallel_tool_calls=False,
                timeout=self.timeout_seconds,
            )

            function_calls: list[Any] = [
                item
                for item in (first_response.output or [])
                if getattr(item, "type", None) == "function_call"
            ]

            if not function_calls:
                output: T | None = getattr(first_response, "output_parsed", None)

                if output is None:
                    raise LLMError(
                        "LLM did not return a structured result.",
                        details={"model": model},
                    )

                return LLMResponse(
                    output=output,
                    model_name=model,
                    response_id=getattr(first_response, "id", None),
                    usage=self._usage(first_response),
                )

            if len(function_calls) > max_tool_calls:
                raise LLMError(
                    "LLM exceeded the allowed tool-call limit.",
                    details={
                        "model": model,
                        "max_tool_calls": max_tool_calls,
                        "actual_tool_calls": len(function_calls),
                    },
                )

            if len(function_calls) != 1:
                raise LLMError(
                    "QuerySpec agent must issue exactly one metadata tool call.",
                    details={
                        "model": model,
                        "actual_tool_calls": len(function_calls),
                    },
                )

            function_call: Any = function_calls[0]
            tool_name: str = str(function_call.name)
            tool_arguments: dict[str, Any] = json.loads(
                str(function_call.arguments)
            )

            tool_output: Any = tool_executor(
                tool_name,
                tool_arguments,
            )

            function_call_output: FunctionCallOutput = {
                "type": "function_call_output",
                "call_id": function_call.call_id,
                "output": json.dumps(
                    tool_output,
                    ensure_ascii=False,
                    default=str,
                ),
            }

            continuation_input: ResponseInputItemParam = cast(
                ResponseInputItemParam,
                function_call_output,
            )
            second_response: Any = self.client.responses.parse(
                model=model,
                instructions=system_prompt,
                previous_response_id=first_response.id,
                input=[continuation_input],
                text_format=response_model,
                timeout=self.timeout_seconds,
            )

            unexpected_tool_calls: list[Any] = [
                item
                for item in (second_response.output or [])
                if getattr(item, "type", None) == "function_call"
            ]

            if unexpected_tool_calls:
                raise LLMError(
                    "QuerySpec agent attempted more than one tool call.",
                    details={"model": model},
                )

            output = getattr(second_response, "output_parsed", None)

            if output is None:
                raise LLMError(
                    "LLM did not return a final structured QuerySpec.",
                    details={"model": model},
                )

            first_usage: LLMUsage = self._usage(first_response)
            second_usage: LLMUsage = self._usage(second_response)

            total_usage: LLMUsage = LLMUsage(
                input_tokens=first_usage.input_tokens + second_usage.input_tokens,
                output_tokens=first_usage.output_tokens + second_usage.output_tokens,
                total_tokens=first_usage.total_tokens + second_usage.total_tokens,
            )

            return LLMResponse(
                output=output,
                model_name=model,
                response_id=getattr(second_response, "id", None),
                usage=total_usage,
            )

        except OpenAIRateLimitError as exc:
            raise RateLimitError(
                "LLM rate limit was reached.",
                cause=exc,
                details={"model": model},
            ) from exc

        except APITimeoutError as exc:
            raise ExternalTimeoutError(
                "LLM request timed out.",
                cause=exc,
                details={"model": model},
            ) from exc

        except APIConnectionError as exc:
            raise NetworkError(
                "Connection to LLM provider failed.",
                cause=exc,
                details={"model": model},
            ) from exc

        except APIError as exc:
            raise LLMError(
                "LLM provider returned an API error.",
                cause=exc,
                details={
                    "model": model,
                    "status_code": getattr(exc, "status_code", None),
                },
            ) from exc

    @staticmethod
    def _usage(response: Any) -> LLMUsage:
        usage: Any = getattr(response, "usage", None)
        if usage is None:
            return LLMUsage()
        input_tokens: int = int(getattr(usage, "input_tokens", 0) or 0)
        output_tokens: int = int(getattr(usage, "output_tokens", 0) or 0)
        total_tokens: int = int(getattr(usage, "total_tokens", input_tokens + output_tokens) or 0)
        return LLMUsage(input_tokens, output_tokens, total_tokens)
