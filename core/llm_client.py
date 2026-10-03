# core/llm_client.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    OpenAI,
    RateLimitError,
)

from pydantic import BaseModel

from config.settings import LLM_CONFIG

from errors.exceptions import (
    ExternalTimeoutError,
    LLMError,
    NetworkError,
    RateLimitError as AgentRateLimitError,
)

# Generic type for any LLM output.
# It is intentionally NOT bound to BaseModel because text responses
# are also valid LLM outputs.
OutputT = TypeVar("OutputT")
# Generic type specifically for structured Pydantic outputs.
StructuredT = TypeVar("StructuredT", bound=BaseModel)


@dataclass(frozen=True)
class LLMUsage:
    """Token usage metadata for one model request."""

    input_tokens: int
    output_tokens: int
    total_tokens: int


@dataclass(frozen=True)
class LLMResponse(Generic[OutputT]):
    """
    Standardized response returned by the LLM client.
    """

    output: OutputT
    model_name: str
    response_id: str | None
    usage: LLMUsage


class LLMClient:
    """
    Provider abstraction for text and structured LLM generation.

    The rest of the application depends on this interface instead
    of directly importing a provider SDK.
    """

    def generate_text(
            self,
            *,
            system_prompt: str,
            user_prompt: str,
            model: str | None = None,
    ) -> LLMResponse[str]:
        """
        Generate plain text.

        Args:
            system_prompt:
                System/developer-level instructions.

            user_prompt:
                User request and bounded context.

            model:
                Optional model override.

        Returns:
            LLMResponse containing generated text and usage metadata.

        Raises:
            LLMError:
                When the provider returns an unrecoverable error.
        """

        raise NotImplementedError

    def generate_structured(
            self,
            *,
            system_prompt: str,
            user_prompt: str,
            response_model: type[OutputT],
            model: str | None = None,
    ) -> LLMResponse[OutputT]:
        """
        Generate a Pydantic-validated structured response.

        Args:
            system_prompt:
                System/developer-level instructions.

            user_prompt:
                User request and bounded context.

            response_model:
                Pydantic model defining the expected output schema.

            model:
                Optional model override.

        Returns:
            LLMResponse containing a validated Pydantic object.

        Raises:
            LLMError:
                When generation or structured parsing fails.
        """

        raise NotImplementedError


class OpenAIClient(LLMClient):
    """
    OpenAI implementation of the provider-agnostic LLM interface.

    Uses the Responses API and Pydantic structured parsing.
    """

    def __init__(
            self,
            *,
            api_key: str | None = None,
            default_model: str | None = None,
            timeout_seconds: float | None = None,
    ) -> None:

        resolved_api_key: str | None = api_key or getattr(LLM_CONFIG, "api_key", None)

        if not resolved_api_key:
            raise ValueError("OPENAI_API_KEY is not configured.")

        self.client: OpenAI = OpenAI(api_key=resolved_api_key)
        self.default_model: str = (default_model or getattr(LLM_CONFIG, "model", "gpt-5.6-luna"))

        self.timeout_seconds: float = (
            timeout_seconds
            if timeout_seconds is not None
            else float(getattr(LLM_CONFIG, "timeout_seconds", 60)))

    def generate_text(
            self,
            *,
            system_prompt: str,
            user_prompt: str,
            model: str | None = None,
    ) -> LLMResponse[str]:

        selected_model: str = (model or self.default_model)

        try:

            response = self.client.responses.create(
                model=selected_model,
                instructions=system_prompt,
                input=user_prompt,
                timeout=self.timeout_seconds,
            )

            output_text: str = response.output_text.strip()

            if not output_text:
                raise LLMError(
                    "LLM returned empty text.",
                    retryable=False,
                    details={"model": selected_model, "response_id": response.id},
                )

            return LLMResponse(
                output=output_text,
                model_name=selected_model,
                response_id=response.id,
                usage=self._extract_usage(response)
            )

        except RateLimitError as exc:

            raise AgentRateLimitError(
                "LLM rate limit was reached.",
                details={"model": selected_model},
                cause=exc) from exc

        except APITimeoutError as exc:

            raise ExternalTimeoutError(
                "LLM request timed out.",
                details={"model": selected_model},
                cause=exc) from exc

        except APIConnectionError as exc:

            raise NetworkError(
                "Connection to LLM provider failed.",
                details={"model": selected_model},
                cause=exc) from exc

        except APIError as exc:

            raise LLMError(
                "LLM provider returned an API error.",
                retryable=False,
                details={"model": selected_model, "status_code": getattr(exc, "status_code", None)},
                cause=exc) from exc

    def generate_structured(
            self,
            *,
            system_prompt: str,
            user_prompt: str,
            response_model: type[StructuredT],
            model: str | None = None,
    ) -> LLMResponse[StructuredT]:

        selected_model: str = model or self.default_model
        try:

            response = self.client.responses.parse(
                model=selected_model,
                instructions=system_prompt,
                input=user_prompt,
                text_format=response_model,
                timeout=self.timeout_seconds,
            )

            parsed: StructuredT | None = response.output_parsed

            if parsed is None:
                raise LLMError(
                    "LLM did not return a structured parsed response.",
                    retryable=False,
                    details={
                        "model": selected_model,
                        "response_id": response.id,
                        "response_model": response_model.__name__,
                    },
                )

            return LLMResponse(
                output=parsed,
                model_name=selected_model,
                response_id=response.id,
                usage=self._extract_usage(
                    response
                ),
            )

        except RateLimitError as exc:

            raise AgentRateLimitError(
                "LLM rate limit was reached.",
                details={"model": selected_model},
                cause=exc) from exc

        except APITimeoutError as exc:

            raise ExternalTimeoutError(
                "LLM structured request timed out.",
                details={"model": selected_model},
                cause=exc) from exc

        except APIConnectionError as exc:

            raise NetworkError(
                "Connection to LLM provider failed.",
                details={"model": selected_model},
                cause=exc) from exc

        except APIError as exc:

            raise LLMError(
                "LLM provider returned an API error.",
                retryable=False,
                details={"model": selected_model, "status_code": getattr(exc, "status_code", None)}, cause=exc) from exc

    @staticmethod
    def _extract_usage(response: Any) -> LLMUsage:

        usage: Any = getattr(response, "usage", None)

        if usage is None:
            return LLMUsage(input_tokens=0, output_tokens=0, total_tokens=0)

        input_tokens: int = int(getattr(usage, "input_tokens", 0) or 0)
        output_tokens: int = int(getattr(usage, "output_tokens", 0, ) or 0)
        total_tokens: int = int(getattr(usage, "total_tokens", input_tokens + output_tokens) or 0)

        return LLMUsage(input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=total_tokens)
