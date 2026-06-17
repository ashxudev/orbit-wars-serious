"""Planner mission evaluation contracts.

Mission Evaluation Cycle 1 extracts deterministic facts available directly
from mission candidates. It does not inspect game state, run simulator
comparisons, score, rank, prune, or select missions.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from ow_sim.state import GameState

from .candidates import CandidateOutcome, MissionCandidate, MissionType


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
    """Deterministic facts available directly from a mission candidate."""

    mission_type: MissionType
    target_planet_id: int | None
    source_planet_ids: tuple[int, ...]
    launch_count: int
    ships_spent: int
    launch_angles: tuple[float, ...]
    candidate_outcome: CandidateOutcome
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
    """Return candidate-fact evaluations for ``candidates``.

    Cycle 1 extracts only facts already present on each ``MissionCandidate``.
    The state argument is intentionally unused and preserved for future API
    compatibility. Input order is preserved.
    """

    _ = state
    _ = config or EvaluationConfig()
    return tuple(
        MissionEvaluation(
            candidate=candidate,
            status=MissionEvaluationStatus.EVALUATED,
            facts=extract_candidate_facts(candidate),
        )
        for candidate in candidates
    )


def extract_candidate_facts(candidate: MissionCandidate) -> MissionEvaluationFacts:
    """Return deterministic facts carried directly by ``candidate``."""

    return MissionEvaluationFacts(
        mission_type=candidate.mission_type,
        target_planet_id=candidate.target_planet_id,
        source_planet_ids=candidate.source_planet_ids,
        launch_count=len(candidate.launches),
        ships_spent=sum(launch.ships for launch in candidate.launches),
        launch_angles=tuple(launch.angle for launch in candidate.launches),
        candidate_outcome=candidate.outcome,
    )


__all__ = (
    "EvaluationConfig",
    "MissionEvaluation",
    "MissionEvaluationFacts",
    "MissionEvaluationStatus",
    "ScoreComponent",
    "evaluate_candidates",
    "extract_candidate_facts",
)
