from __future__ import annotations

import time

from dataclasses import dataclass
from typing import Any

from core.context import AgentContext
from core.tool_registry import ToolRegistry

from observability.events import (
    AgentEvent,
    EventType,
)

from observability.logger import AgentLogger
from errors.exceptions import ToolExecutionError


@dataclass(frozen=True)
class ToolExecutionResult:
    """Structured result produced by tool runtime."""
    tool_name: str
    arguments: dict[str, Any]
    output: Any
    latency_ms: float
    success: bool


class ReferenceResolver:
    """
    Resolve planner-generated *_from references against AgentContext.
    """
    REFERENCE_SUFFIX: str = "_from"

    def resolve_arguments(self, arguments: dict[str, Any], context: AgentContext) -> dict[str, Any]:
        """
        Resolve all dynamic argument references.

        Example:

            {
                "price_from": "context.product.price"
            }

        becomes:

            {
                "price": 100
            }

        Args:
            arguments:
                Raw tool arguments.

            context:
                Current execution context.

        Returns:
            Arguments ready for handler invocation.
        """

        return self._resolve_mapping(arguments, context)

    def _resolve_mapping(self, values: dict[str, Any], context: AgentContext) -> dict[str, Any]:

        resolved: dict[str, Any] = {}
        for key, value in values.items():

            if key.endswith(self.REFERENCE_SUFFIX):

                target_key: str = key[: -len(self.REFERENCE_SUFFIX)]

                if not target_key:
                    raise ValueError(f"Invalid reference argument: {key}")

                if not isinstance(value, str):
                    raise TypeError(f"Reference value must be a string: {key}")

                resolved[target_key] = context.resolve_path(value)
                continue

            resolved[key] = self._resolve_value(value, context)

        return resolved

    def _resolve_value(self, value: Any, context: AgentContext) -> Any:

        if isinstance(value, dict):
            return self._resolve_mapping(value, context)

        if isinstance(value, list):
            return [self._resolve_value(item, context) for item in value]

        if isinstance(value, tuple):
            return tuple(self._resolve_value(item, context) for item in value)
        return value


class ToolRuntime:
    """
    Low-level runtime responsible for reference resolution
    and tool invocation.

    Authorization and security checks belong outside this class.
    """

    def __init__(
            self,
            *,
            registry: ToolRegistry,
            logger: AgentLogger,
            resolver: ReferenceResolver | None = None,
    ) -> None:

        self.registry: ToolRegistry = registry
        self.logger: AgentLogger = logger
        self.resolver: ReferenceResolver = (
                resolver
                or ReferenceResolver()
        )

    def execute(
            self,
            *,
            context: AgentContext,
            tool_name: str,
            arguments: dict[str, Any],
            agent_name: str,
            stage_name: str,
    ) -> ToolExecutionResult:
        """
        Resolve and execute one registered tool.

        Args:
            context:
                Current execution state.

            tool_name:
                Registered tool name.

            arguments:
                Planner-generated arguments.

            agent_name:
                Name of the agent/stage caller.

            stage_name:
                Current workflow stage.

        Returns:
            ToolExecutionResult.

        Raises:
            ToolExecutionError:
                When tool execution fails.
        """
        started_at: float = time.perf_counter()

        try:
            registration = (self.registry.get_registration(tool_name))
            resolved_arguments: dict[str, Any] = (self.resolver.resolve_arguments(arguments, context, ))

            self.logger.log(
                AgentEvent(
                    event_type=EventType.TOOL_STARTED,
                    trace_id=context.trace_id,
                    agent_name=agent_name,
                    stage_name=stage_name,
                    tool_name=tool_name,
                    input_data=resolved_arguments,
                    status="started",
                )
            )

            output: Any = registration.handler(**resolved_arguments)

            latency_ms: float = (time.perf_counter() - started_at) * 1000

            self.logger.log(
                AgentEvent(
                    event_type=EventType.TOOL_COMPLETED,
                    trace_id=context.trace_id,
                    agent_name=agent_name,
                    stage_name=stage_name,
                    tool_name=tool_name,
                    input_data=resolved_arguments,
                    output_data=self._output_metadata(
                        output
                    ),
                    latency_ms=latency_ms,
                    status="success",
                )
            )

            return ToolExecutionResult(
                tool_name=tool_name,
                arguments=resolved_arguments,
                output=output,
                latency_ms=latency_ms,
                success=True,
            )

        except Exception as exc:
            latency_ms = (time.perf_counter() - started_at) * 1000

            self.logger.log(
                AgentEvent(
                    event_type=EventType.ERROR,
                    trace_id=context.trace_id,
                    agent_name=agent_name,
                    stage_name=stage_name,
                    tool_name=tool_name,
                    latency_ms=latency_ms,
                    status="error",
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
            )

            if isinstance(exc, ToolExecutionError):
                raise

            raise ToolExecutionError(
                f"Tool execution failed: {tool_name}",
                retryable=False,
                cause=exc,
                details={
                    "tool_name": tool_name,
                    "agent_name": agent_name,
                    "stage_name": stage_name,
                },
            ) from exc

    @staticmethod
    def _output_metadata(output: Any) -> dict[str, Any]:
        """
        Create a lightweight log-safe representation of tool output.

        Full outputs remain in runtime context and should not be copied
        blindly into observability logs.
        """

        if output is None:
            return {"type": "none"}

        if isinstance(output, dict):
            return {"type": "dict", "keys": list(output.keys())}

        if isinstance(output, (list, tuple)):
            return {"type": type(output).__name__, "length": len(output)}

        return {"type": type(output).__name__, }
