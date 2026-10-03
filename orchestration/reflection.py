from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from agent_schemas.agent_outputs import ReflectionResult


ReflectionAction = Literal[
    "accept",
    "repair",
    "clarify",
    "reject",
    "inconclusive",
]


@dataclass(frozen=True)
class ReflectionDecision:
    """
    Backend decision derived from the reflection model output.
    """

    action: ReflectionAction
    should_repair: bool
    should_finish: bool
    reason: str


class ReflectionCoordinator:
    """
    Converts probabilistic reflection output into a bounded backend action.

    The reflection model never controls execution directly.
    """

    def __init__(self,*,max_repair_attempts: int = 2,minimum_repair_confidence: float = 0.7) -> None:

        if max_repair_attempts < 0:
            raise ValueError( "max_repair_attempts cannot be negative.")

        if not 0.0 <= minimum_repair_confidence <= 1.0:
            raise ValueError("minimum_repair_confidence must be between 0 and 1.")

        self.max_repair_attempts: int = max_repair_attempts
        self.minimum_repair_confidence: float =  minimum_repair_confidence

    def decide(self,*,reflection: ReflectionResult,repair_attempts: int) -> ReflectionDecision:
        """
        Convert reflection output into a controlled workflow action.

        Args:
            reflection:
                Structured result returned by ReflectionAgent.

            repair_attempts:
                Number of repair attempts already performed.

        Returns:
            ReflectionDecision.
        """

        if repair_attempts < 0:
            raise ValueError("repair_attempts cannot be negative.")

        if reflection.verdict == "pass":

            return ReflectionDecision(
                action="accept",
                should_repair=False,
                should_finish=True,
                reason=(
                    "Reflection accepted the executed result."
                ),
            )

        if reflection.verdict == "clarify":

            return ReflectionDecision(
                action="clarify",
                should_repair=False,
                should_finish=True,
                reason=(
                    "Additional user clarification is required."
                ),
            )

        if reflection.verdict == "reject":

            return ReflectionDecision(
                action="reject",
                should_repair=False,
                should_finish=True,
                reason=(
                    "Reflection identified an unsupported request."
                ),
            )

        if reflection.verdict == "inconclusive":

            return ReflectionDecision(
                action="inconclusive",
                should_repair=False,
                should_finish=True,
                reason=(
                    "Reflection could not establish correctness "
                    "from the available evidence."
                ),
            )

        if reflection.verdict == "repair":
            if repair_attempts >= self.max_repair_attempts:

                return ReflectionDecision(
                    action="inconclusive",
                    should_repair=False,
                    should_finish=True,
                    reason=(
                        "Maximum SQL repair attempts have been reached."
                    )
                )

            if reflection.confidence < self.minimum_repair_confidence:

                return ReflectionDecision(
                    action="inconclusive",
                    should_repair=False,
                    should_finish=True,
                    reason=(
                        "Reflection confidence is below the "
                        "repair threshold."
                    )
                )

            return ReflectionDecision(
                action="repair",
                should_repair=True,
                should_finish=False,
                reason=(
                    "Reflection identified a repairable SQL issue."
                )
            )

        return ReflectionDecision(
            action="inconclusive",
            should_repair=False,
            should_finish=True,
            reason="Unknown reflection state.",
        )