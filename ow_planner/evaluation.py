"""Planner mission evaluation contracts.

Mission Evaluation Cycle 0 defines stable value types and a structural public
API boundary. It does not compute facts, run simulator comparisons, score,
rank, prune, or select missions.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from ow_sim.state import GameState

from .candidates import MissionCandidate


class MissionEvaluationStatus(str, Enum):
    """Status for mission evaluation lifecycle."""

    UNEVALUATED = "unevaluated"
    EVALUATED = "evaluated"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class EvaluationConfig:
    """Configuration boundary for future mission evaluation."""

    horizon_ticks: int | None = None

    def __post_init__(self) -> None:
        if self.horizon_ticks is None:
            return
        if (
            isinstance(self.horizon_ticks, bool)
            or not isinstance(self.horizon_ticks, int)
            or self.horizon_ticks < 0
        ):
            raise ValueError("horizon_ticks must be None or an integer >= 0")


@dataclass(frozen=True, slots=True)
class ScoreComponent:
    """Named score component contract for future scoring cycles."""

    name: str
    value: float
    weight: float = 1.0


@dataclass(frozen=True, slots=True)
class MissionEvaluationFacts:
    """Structural placeholder for future mission evaluation facts."""

    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MissionEvaluation:
    """Structural evaluation wrapper for one mission candidate."""

    candidate: MissionCandidate
    status: MissionEvaluationStatus = MissionEvaluationStatus.UNEVALUATED
    facts: MissionEvaluationFacts | None = None
    score_components: tuple[ScoreComponent, ...] = ()
    total_score: float | None = None
    note: str | None = None


def evaluate_candidates(
    state: GameState,
    candidates: Sequence[MissionCandidate],
    config: EvaluationConfig | None = None,
) -> tuple[MissionEvaluation, ...]:
    """Return structural unevaluated wrappers for ``candidates``.

    Cycle 0 deliberately avoids simulator rollouts, fact extraction, scoring,
    ranking, pruning, and action selection. Input order is preserved.
    """

    _ = state
    _ = config or EvaluationConfig()
    return tuple(MissionEvaluation(candidate=candidate) for candidate in candidates)


__all__ = (
    "EvaluationConfig",
    "MissionEvaluation",
    "MissionEvaluationFacts",
    "MissionEvaluationStatus",
    "ScoreComponent",
    "evaluate_candidates",
)
