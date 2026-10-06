from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class AgentContext:
    trace_id: str;
    user_query: str;
    user_id: str | None = None;
    metadata: dict[str, Any] = field(default_factory=dict);
    state: dict[str, Any] = field(default_factory=dict)

    def set(self, key: str, value: Any) -> None: self.state[key] = value

    def get(self, key: str, default: Any = None) -> Any: return self.state.get(key, default)

    def set_metadata(self, key: str, value: Any) -> None: self.metadata[key] = value

    def snapshot(self) -> dict[str, Any]: return {"trace_id": self.trace_id, "user_query": self.user_query,
                                                  "user_id": self.user_id, "metadata": dict(self.metadata),
                                                  "state": dict(self.state)}
