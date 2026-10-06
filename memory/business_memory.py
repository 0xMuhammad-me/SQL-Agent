from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Mapping
from metadata.business_catalog import BUSINESS_DEFINITIONS


@dataclass(frozen=True, slots=True)
class BusinessSearchResult: name: str;definition: str;score: float


class BusinessMemory:
    def __init__(self, definitions: Mapping[str, str] = BUSINESS_DEFINITIONS) -> None:
        self._defs = dict(definitions)

    def get_definition(self, name: str) -> str | None:
        return self._defs.get(name.lower())

    def search(self, query: str, top_k: int = 8) -> list[BusinessSearchResult]:
        qt = set(re.findall(r"[a-zA-Z0-9_]+", query.lower()));
        out = []
        for n, d in self._defs.items():
            ct = set(re.findall(r"[a-zA-Z0-9_]+", f"{n} {d}".lower()));
            score = float(len(qt & ct) + (3 if n.lower() in query.lower() else 0))
            if score > 0: out.append(BusinessSearchResult(n, d.strip(), score))
        out.sort(key=lambda x: (-x.score, x.name));
        return out[:top_k]
