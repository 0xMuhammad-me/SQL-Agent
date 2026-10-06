from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from agent_schemas import ReflectionResult


@dataclass(frozen=True, slots=True)
class ReflectionDecision:
    """Translate reflection output into a bounded workflow action."""

    action: str
    clarification_question: str | None = None
    issues: tuple[str, ...] = ()
    repair_instructions: tuple[str, ...] = ()


class ReflectionCoordinator:
    """Coordinate semantic reflection without enforcing security policy."""

    def __init__(self, *, max_repair_attempts: int, minimum_repair_confidence: float) -> None:
        self._max_repair_attempts: int = max_repair_attempts
        self._minimum_repair_confidence: float = minimum_repair_confidence

    @property
    def max_repair_attempts(self) -> int:
        return self._max_repair_attempts

    def decide(self, reflection: ReflectionResult, *, repair_attempts: int) -> ReflectionDecision:
        if reflection.verdict == "pass":
            return ReflectionDecision(action="accept")
        if reflection.verdict == "clarify":
            return ReflectionDecision(
                action="clarify",
                clarification_question=reflection.clarification_question,
                issues=tuple(issue.description for issue in reflection.issues),
            )
        if reflection.verdict == "reject":
            return ReflectionDecision(action="reject", issues=tuple(issue.description for issue in reflection.issues))
        if reflection.verdict == "inconclusive":
            return ReflectionDecision(action="inconclusive", issues=tuple(issue.description for issue in reflection.issues))

        if repair_attempts >= self._max_repair_attempts:
            return ReflectionDecision(action="inconclusive", issues=("Maximum repair attempts reached.",))
        if reflection.confidence < self._minimum_repair_confidence:
            return ReflectionDecision(action="inconclusive", issues=("Reflection confidence is below the repair threshold.",))

        return ReflectionDecision(
            action="repair",
            issues=tuple(issue.description for issue in reflection.issues),
            repair_instructions=tuple(reflection.repair_instructions),
        )
