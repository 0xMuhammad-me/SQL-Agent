from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


class ContextKeyError(KeyError):
    """Raised when a required context value does not exist."""


@dataclass
class AgentContext:
    """
    Runtime state for a single agent execution.

    Context is request-scoped and should not be reused across
    independent user requests.
    """

    trace_id: str
    user_query: str
    data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def set(self, key: str, value: Any) -> None:
        """
        Store a value in the execution context.

        Args:
            key:
                Context key.

            value:
                Runtime value to store.

        Returns:
            None.
        """

        if not key.strip():
            raise ValueError("Context key cannot be empty.")
        self.data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieve a context value.

        Args:
            key:
                Context key.

            default:
                Value returned when the key does not exist.

        Returns:
            Stored value or default.
        """

        return self.data.get(key, default)

    def require(self, key: str) -> Any:
        """
        Retrieve a required context value.

        Args:
            key:
                Context key that must exist.

        Returns:
            Stored value.

        Raises:
            ContextKeyError:
                When the requested key does not exist.
        """

        if key not in self.data:
            raise ContextKeyError(f"Required context key does not exist: {key}")

        return self.data[key]

    def has(self, key: str) -> bool:
        """
        Check whether a context key exists.

        Args:
            key:
                Context key.

        Returns:
            True when the key exists.
        """
        return key in self.data

    def update(self, values: dict[str, Any]) -> None:
        """
        Add multiple values to the context.

        Args:
            values:
                Mapping of context keys to runtime values.

        Returns:
            None.
        """

        for key, value in values.items():
            self.set(key, value)

    def resolve_path(self, path: str) -> Any:
        """
        Resolve a dotted context path.

        Example:
            context.query_spec.metric

        Args:
            path:
                Path beginning with 'context.'.

        Returns:
            Resolved value.

        Raises:
            ContextKeyError:
                When the path cannot be resolved.
        """

        if not path.startswith("context."):
            raise ContextKeyError(f"Invalid context reference: {path}")

        path_parts: list[str] = path.split(".")[1:]

        if not path_parts or not path_parts[0]:
            raise ContextKeyError(f"Invalid context reference: {path}")

        current: Any = self.require(path_parts[0])

        for part in path_parts[1:]:

            if isinstance(current, dict):

                if part not in current:
                    raise ContextKeyError(f"Path '{path}' does not exist.")

                current = current[part]

            elif isinstance(current, (list, tuple)):

                if not part.isdigit():
                    raise ContextKeyError(f"Invalid sequence index in path: {path}")

                index: int = int(part)

                try:
                    current = current[index]
                except IndexError as exc:
                    raise ContextKeyError(f"Path '{path}' does not exist.") from exc

            else:

                if not hasattr(current, part):
                    raise ContextKeyError(f"Path '{path}' does not exist.")

                current = getattr(current, par)

        return current

    def snapshot(self) -> dict[str, Any]:
        """
        Create a defensive snapshot of context data.

        Returns:
            Deep-copied context data.

        Note:
            Large database objects should normally not be copied into
            logs. Observability should create a sanitized representation.
        """

        return deepcopy(self.data)

    def set_metadata(self, key: str, value: Any) -> None:
        """
        Store runtime metadata separately from workflow data.

        Args:
            key:
                Metadata key.

            value:
                Metadata value.

        Returns:
            None.
        """
        self.metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """
        Retrieve runtime metadata.

        Args:
            key:
                Metadata key.

            default:
                Fallback value.

        Returns:
            Stored metadata or default.
        """

        return self.metadata.get(key, default)
