from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Any, Callable, Generic, Mapping, Sequence, TypeVar, cast
from openai import APIConnectionError, APIError, APITimeoutError, OpenAI, RateLimitError as OpenAIRateLimitError
from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionMessageParam,
    ChatCompletionToolMessageParam,
    ChatCompletionToolUnionParam, ChatCompletionFunctionToolParam, ChatCompletionMessageFunctionToolCallParam,
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
            tools: Sequence[ChatCompletionToolUnionParam],
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
        self.client: OpenAI = OpenAI(api_key=key, base_url=LLM_CONFIG.base_url)
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
            tools: Sequence[ChatCompletionToolUnionParam],
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
            messages: list[ChatCompletionMessageParam] = [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ]
            response: Any = self.client.chat.completions.create(
                model=model,
                messages=messages,
                timeout=self.timeout_seconds,
            )

            output: str = (response.choices[0].message.content or "").strip()

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
            schema_json: str = json.dumps(response_model.model_json_schema(), ensure_ascii=False)
            structured_prompt: str = (
                f"{user_prompt}\n\n"
                "Return only valid JSON matching this schema:\n"
                f"{schema_json}"
            )

            messages: list[ChatCompletionMessageParam] = [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": structured_prompt,
                },
            ]

            response: Any = self.client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
                timeout=self.timeout_seconds,
            )

            output: str | None = response.choices[0].message.content

            if not output:
                raise LLMError("LLM did not return structured content.", details={"model": model})

            parsed_data: Any = json.loads(output)

            output: T = response_model.model_validate(parsed_data)
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
            tools: Sequence[ChatCompletionToolUnionParam],
            tool_executor: ToolExecutor,
            model: str,
            max_tool_calls: int,
    ) -> LLMResponse[T]:
        try:
            messages: list[ChatCompletionMessageParam] = [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ]

            tools_payload: list[ChatCompletionToolUnionParam] = [
                cast(ChatCompletionFunctionToolParam, dict(tool))
                for tool in tools
            ]

            first_response: Any = (
                self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    tools=tools_payload,
                    tool_choice="auto",
                    parallel_tool_calls=False,
                    timeout=self.timeout_seconds,
                )
            )

            message: Any = first_response.choices[0].message

            tool_calls: list[Any] = list(
                getattr(message, "tool_calls", None) or []
            )

            # ----------------------------------------------------------
            # No tool call -> parse structured response
            # ----------------------------------------------------------

            if not tool_calls:
                content: str | None = message.content

                if not content:
                    raise LLMError("LLM did not return a structured result.", details={"model": model})

                output: T = response_model.model_validate_json(content)

                return LLMResponse(
                    output=output,
                    model_name=model,
                    response_id=getattr(first_response,"id",None),
                    usage=self._usage(first_response),
                )

            # ----------------------------------------------------------
            # Validate number of tool calls
            # ----------------------------------------------------------

            if len(tool_calls) > max_tool_calls:
                raise LLMError(
                    "LLM exceeded the allowed tool-call limit.",
                    details={
                        "model": model,
                        "max_tool_calls": max_tool_calls,
                        "actual_tool_calls": len(tool_calls),
                    },
                )

            if len(tool_calls) != 1:
                raise LLMError(
                    "QuerySpec agent must issue exactly one metadata tool call.",
                    details={
                        "model": model,
                        "actual_tool_calls": len(tool_calls),
                    },
                )

            tool_call: Any = tool_calls[0]
            tool_name: str = str(tool_call.function.name)
            tool_arguments: dict[str, Any] = json.loads(str(tool_call.function.arguments))

            # ----------------------------------------------------------
            # Execute tool
            # ----------------------------------------------------------

            tool_output: Any = tool_executor(tool_name, tool_arguments)

            # ----------------------------------------------------------
            # Continue conversation with tool result
            # ----------------------------------------------------------

            tool_calls_payload: list[ChatCompletionMessageFunctionToolCallParam] = []

            for tool_call in tool_calls:
                payload: dict[str, Any] = tool_call.model_dump(
                    mode="json",
                    exclude_none=True,
                )

                if "extra_content" not in payload:
                    extra_content: Any = getattr(
                        tool_call,
                        "extra_content",
                        None,
                    )

                    if extra_content is None:
                        model_extra: Mapping[str, Any] = (
                                getattr(tool_call, "model_extra", None) or {}
                        )
                        extra_content = model_extra.get("extra_content")

                    if extra_content is not None:
                        payload["extra_content"] = extra_content

                tool_calls_payload.append(cast(ChatCompletionMessageFunctionToolCallParam, payload))

            assistant_message: ChatCompletionAssistantMessageParam = {
                "role": "assistant",
                "content": message.content,
                "tool_calls": tool_calls_payload,
            }

            messages.append(assistant_message)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(
                        tool_output,
                        ensure_ascii=False,
                        default=str,
                    ),
                }
            )

            # ----------------------------------------------------------
            # Second request -> structured final response
            # ----------------------------------------------------------

            second_response: Any = (
                self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    response_format={
                        "type": "json_object"
                    },
                    timeout=self.timeout_seconds,
                )
            )

            second_message: Any = second_response.choices[0].message
            unexpected_tool_calls: list[Any] = list(getattr(second_message, "tool_calls", None) or [])

            if unexpected_tool_calls:
                raise LLMError("QuerySpec agent attempted more than one tool call.", details={"model": model}, )

            content: str | None = second_message.content

            if not content:
                raise LLMError("LLM did not return a final structured QuerySpec.", details={"model": model})

            output: T = response_model.model_validate_json(content)

            first_usage: LLMUsage = self._usage(first_response)
            second_usage: LLMUsage = self._usage(second_response)

            total_usage: LLMUsage = LLMUsage(
                input_tokens=(first_usage.input_tokens + second_usage.input_tokens),
                output_tokens=(first_usage.output_tokens + second_usage.output_tokens),
                total_tokens=(first_usage.total_tokens + second_usage.total_tokens),
            )

            return LLMResponse(
                output=output,
                model_name=model,
                response_id=getattr(second_response, "id", None, ),
                usage=total_usage,
            )

        except OpenAIRateLimitError as exc:
            raise RateLimitError("LLM rate limit was reached.", cause=exc, details={"model": model},
                                 ) from exc

        except APITimeoutError as exc:
            raise ExternalTimeoutError("LLM request timed out.", cause=exc, details={"model": model},
                                       ) from exc

        except APIConnectionError as exc:
            raise NetworkError("Connection to LLM provider failed.", cause=exc, details={"model": model},
                               ) from exc

        except APIError as exc:
            raise LLMError(
                "LLM provider returned an API error.",
                cause=exc,
                details={"model": model, "status_code": getattr(exc, "status_code", None)},
            ) from exc

    @staticmethod
    def _usage(response: Any) -> LLMUsage:
        usage: Any = getattr(response, "usage", None)

        if usage is None:
            return LLMUsage()

        def read_count(*names: str) -> int:
            for name in names:
                if isinstance(usage, dict):
                    value = usage.get(name)
                else:
                    value = getattr(usage, name, None)

                if value is not None:
                    try:
                        return int(value or 0)
                    except (TypeError, ValueError):
                        continue

            return 0

        input_tokens = read_count("input_tokens", "prompt_tokens", "input_token_count")
        output_tokens = read_count("output_tokens", "completion_tokens", "output_token_count")
        total_tokens = read_count("total_tokens", "total_token_count")

        if total_tokens == 0:
            total_tokens = input_tokens + output_tokens

        return LLMUsage(input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=total_tokens)
