from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

ToolHandler = Callable[..., Any]


@dataclass(frozen=True)
class ToolDefinition:
    """Public metadata describing a registered tool."""

    name: str
    description: str
    input_schema: Mapping[str, Any]
    output_schema: Mapping[str, Any]
    capabilities: frozenset[str]
    risk_level: str = "low"
    requires_approval: bool = False
    timeout_seconds: int = 30
    max_output_rows: int | None = None
    tool_type: str = "builtin"


@dataclass(frozen=True)
class ToolRegistration:
    """Internal binding between metadata and executable handler."""

    definition: ToolDefinition
    handler: ToolHandler


class ToolRegistry:
    """Central registry for tools and their metadata."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolRegistration] = {}

    def register(self, definition: ToolDefinition, handler: ToolHandler) -> None:
        """Register a tool and reject duplicate names."""

        self._validate_definition(definition)

        if definition.name in self._tools:
            raise ValueError(f"Tool already registered: {definition.name}")

        if not callable(handler):
            raise TypeError(f"Handler for tool '{definition.name}' must be callable.")

        self._tools[definition.name] = ToolRegistration(definition=definition, handler=handler)

    def exists(self, name: str) -> bool:
        """Return whether a tool exists."""

        return name in self._tools

    def get_definition(self, name: str) -> ToolDefinition:
        """Return public metadata for one tool."""

        return self._get_registration(name).definition

    def get_handler(self, name: str) -> ToolHandler:
        """Return the executable handler for one tool."""

        return self._get_registration(name).handler

    def get_registration(self, name: str) -> ToolRegistration:
        """Return the complete internal registration."""
        return self._get_registration(name)

    def list_metadata(self) -> list[dict[str, Any]]:
        """Return planner-safe metadata without executable handlers."""

        result: list[dict[str, Any]] = []
        for registration in self._tools.values():
            definition: ToolDefinition = registration.definition

            result.append(
                {
                    "name": definition.name,
                    "description": definition.description,
                    "input_schema": dict(definition.input_schema),
                    "output_schema": dict(definition.output_schema),
                    "capabilities": sorted(definition.capabilities),
                    "risk_level": definition.risk_level,
                    "requires_approval": definition.requires_approval,
                    "timeout_seconds": definition.timeout_seconds,
                    "max_output_rows": definition.max_output_rows,
                    "tool_type": definition.tool_type,
                }
            )

        return result


def names(self) -> tuple[str, ...]:
    """Return all registered tool names."""

    return tuple(self._tools.keys())


def _get_registration(self, name: str) -> ToolRegistration:
    """Get one internal tool registration."""

    registration: ToolRegistration | None = self._tools.get(name)

    if registration is None:
        raise KeyError(f"Unknown tool: {name}")

    return registration


@staticmethod
def _validate_definition(definition: ToolDefinition) -> None:
    """Validate basic metadata consistency."""

    if not definition.name.strip():
        raise ValueError("Tool name cannot be empty.")

    if not definition.description.strip():
        raise ValueError(f"Tool description cannot be empty: {definition.name}")

    if definition.timeout_seconds <= 0:
        raise ValueError("Tool timeout must be greater than zero.")

    if (definition.max_output_rows is not None) and (definition.max_output_rows <= 0):
        raise ValueError("max_output_rows must be positive.")
