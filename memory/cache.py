from __future__ import annotations
import time
from dataclasses import dataclass
from threading import RLock
from typing import Any, Protocol


class CacheStore(Protocol):
    def get(self, key: str) -> Any | None: ...

    def set(self, key: str, value: Any, *, ttl_seconds: float) -> None: ...

    def delete(self, key: str) -> None: ...


@dataclass(slots=True)
class _Entry: value: Any; expires_at: float


class InMemoryCache(CacheStore):
    def __init__(self) -> None:
        self._data: dict[str, _Entry] = {};self._lock = RLock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            e: _Entry | None = self._data.get(key)
            if e is None: return None
            if e.expires_at <= time.monotonic(): self._data.pop(key, None);return None
            return e.value

    def set(self, key: str, value: Any, *, ttl_seconds: float) -> None:
        if ttl_seconds <= 0: return
        with self._lock: self._data[key] = _Entry(value, time.monotonic() + ttl_seconds)

    def delete(self, key: str) -> None:
        with self._lock: self._data.pop(key, None)
