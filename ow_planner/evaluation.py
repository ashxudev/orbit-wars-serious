"""Planner mission evaluation contracts.

Mission Evaluation Cycle 2 extracts deterministic facts available directly
from mission candidates and before-state source/target planet lookups. It does
not run simulator comparisons, score, rank, prune, or select missions.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from ow_sim.state import GameState, Planet

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
class PlanetEvaluationFacts:
    """Before-state facts for one planet referenced by a candidate."""

    planet_id: int
    owner: int
    ships: int
    production: int
    is_comet: bool = False


@dataclass(frozen=True, slots=True)
class MissionEvaluationFacts:
    """Deterministic candidate facts plus before-state planet lookups."""

    mission_type: MissionType
    target_planet_id: int | None
    source_planet_ids: tuple[int, ...]
    launch_count: int
    ships_spent: int
    launch_angles: tuple[float, ...]
    candidate_outcome: CandidateOutcome
    target_before: PlanetEvaluationFacts | None = None
    sources_before: tuple[PlanetEvaluationFacts, ...] = ()
    missing_target_planet_id: int | None = None
    missing_source_planet_ids: tuple[int, ...] = ()
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

    Cycle 2 adds current-state source/target planet facts only. Input order is
    preserved.
    """

    _ = config or EvaluationConfig()
    return tuple(
        MissionEvaluation(
            candidate=candidate,
            status=MissionEvaluationStatus.EVALUATED,
            facts=extract_candidate_facts(candidate, state),
        )
        for candidate in candidates
    )


def extract_candidate_facts(
    candidate: MissionCandidate,
    state: GameState | None = None,
) -> MissionEvaluationFacts:
    """Return deterministic candidate facts and optional state lookups."""

    planets_by_id = _planets_by_id(state)
    target_before = None
    missing_target_planet_id = None
    if state is not None and candidate.target_planet_id is not None:
        target = planets_by_id.get(candidate.target_planet_id)
        if target is None:
            missing_target_planet_id = candidate.target_planet_id
        else:
            target_before = planet_evaluation_facts(target)

    sources_before: list[PlanetEvaluationFacts] = []
    missing_source_planet_ids: list[int] = []
    if state is not None:
        for source_planet_id in candidate.source_planet_ids:
            source = planets_by_id.get(source_planet_id)
            if source is None:
                missing_source_planet_ids.append(source_planet_id)
            else:
                sources_before.append(planet_evaluation_facts(source))

    return MissionEvaluationFacts(
        mission_type=candidate.mission_type,
        target_planet_id=candidate.target_planet_id,
        source_planet_ids=candidate.source_planet_ids,
        launch_count=len(candidate.launches),
        ships_spent=sum(launch.ships for launch in candidate.launches),
        launch_angles=tuple(launch.angle for launch in candidate.launches),
        candidate_outcome=candidate.outcome,
        target_before=target_before,
        sources_before=tuple(sources_before),
        missing_target_planet_id=missing_target_planet_id,
        missing_source_planet_ids=tuple(missing_source_planet_ids),
    )


def planet_evaluation_facts(planet: Planet) -> PlanetEvaluationFacts:
    """Return before-state evaluation facts for ``planet``."""

    return PlanetEvaluationFacts(
        planet_id=planet.planet_id,
        owner=planet.owner,
        ships=planet.ships,
        production=planet.production,
        is_comet=planet.is_comet,
    )


def _planets_by_id(state: GameState | None) -> dict[int, Planet]:
    if state is None:
        return {}
    return {
        planet.planet_id: planet
        for planet in state.planets
    }


__all__ = (
    "EvaluationConfig",
    "MissionEvaluation",
    "MissionEvaluationFacts",
    "MissionEvaluationStatus",
    "PlanetEvaluationFacts",
    "ScoreComponent",
    "evaluate_candidates",
    "extract_candidate_facts",
    "planet_evaluation_facts",
)
