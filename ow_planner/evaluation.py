"""Planner mission evaluation contracts.

Mission Evaluation Cycle 4 extracts deterministic candidate facts, before-state
source/target lookups, idle baseline future lookups, and mechanical candidate
future lookups. It does not score, rank, prune, or select missions.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from ow_sim.state import GameState, Planet
from ow_sim.timeline import simulate_ticks
from ow_sim.whatif import simulate_launch_orders

from .actions import mission_candidate_to_orders
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
    baseline_horizon_ticks: int = 0
    target_baseline: PlanetEvaluationFacts | None = None
    sources_baseline: tuple[PlanetEvaluationFacts, ...] = ()
    missing_baseline_target_planet_id: int | None = None
    missing_baseline_source_planet_ids: tuple[int, ...] = ()
    mission_horizon_ticks: int = 0
    target_mission: PlanetEvaluationFacts | None = None
    sources_mission: tuple[PlanetEvaluationFacts, ...] = ()
    missing_mission_target_planet_id: int | None = None
    missing_mission_source_planet_ids: tuple[int, ...] = ()
    mission_simulation_error: str | None = None
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

    Cycle 4 adds shared idle baseline facts and per-candidate mechanical mission
    future source/target planet facts. Input order is preserved.
    """

    effective_config = config or EvaluationConfig()
    horizon_ticks = (
        0
        if effective_config.horizon_ticks is None
        else effective_config.horizon_ticks
    )
    if not candidates:
        return ()
    baseline_state = baseline_state_after_horizon(state, horizon_ticks)
    evaluations: list[MissionEvaluation] = []
    for candidate in candidates:
        mission_state = None
        mission_simulation_error = None
        try:
            mission_state = candidate_state_after_horizon(
                state,
                candidate,
                horizon_ticks,
            )
        except ValueError as exc:
            mission_simulation_error = str(exc)

        evaluations.append(
            MissionEvaluation(
                candidate=candidate,
                status=MissionEvaluationStatus.EVALUATED,
                facts=extract_candidate_facts(
                    candidate,
                    state,
                    baseline_state=baseline_state,
                    baseline_horizon_ticks=horizon_ticks,
                    mission_state=mission_state,
                    mission_horizon_ticks=horizon_ticks,
                    mission_simulation_error=mission_simulation_error,
                ),
            ),
        )
    return tuple(evaluations)


def extract_candidate_facts(
    candidate: MissionCandidate,
    state: GameState | None = None,
    *,
    baseline_state: GameState | None = None,
    baseline_horizon_ticks: int = 0,
    mission_state: GameState | None = None,
    mission_horizon_ticks: int = 0,
    mission_simulation_error: str | None = None,
) -> MissionEvaluationFacts:
    """Return deterministic candidate facts and optional state lookups."""

    EvaluationConfig(horizon_ticks=baseline_horizon_ticks)
    EvaluationConfig(horizon_ticks=mission_horizon_ticks)
    before_lookup = _lookup_candidate_planets(candidate, state)
    if baseline_state is None and state is not None:
        baseline_state = state
    baseline_lookup = _lookup_candidate_planets(candidate, baseline_state)
    if (
        mission_state is None
        and mission_simulation_error is None
        and baseline_state is not None
    ):
        mission_state = baseline_state
    mission_lookup = _lookup_candidate_planets(candidate, mission_state)

    return MissionEvaluationFacts(
        mission_type=candidate.mission_type,
        target_planet_id=candidate.target_planet_id,
        source_planet_ids=candidate.source_planet_ids,
        launch_count=len(candidate.launches),
        ships_spent=sum(launch.ships for launch in candidate.launches),
        launch_angles=tuple(launch.angle for launch in candidate.launches),
        candidate_outcome=candidate.outcome,
        target_before=before_lookup.target,
        sources_before=before_lookup.sources,
        missing_target_planet_id=before_lookup.missing_target_planet_id,
        missing_source_planet_ids=before_lookup.missing_source_planet_ids,
        baseline_horizon_ticks=baseline_horizon_ticks,
        target_baseline=baseline_lookup.target,
        sources_baseline=baseline_lookup.sources,
        missing_baseline_target_planet_id=baseline_lookup.missing_target_planet_id,
        missing_baseline_source_planet_ids=baseline_lookup.missing_source_planet_ids,
        mission_horizon_ticks=mission_horizon_ticks,
        target_mission=mission_lookup.target,
        sources_mission=mission_lookup.sources,
        missing_mission_target_planet_id=mission_lookup.missing_target_planet_id,
        missing_mission_source_planet_ids=mission_lookup.missing_source_planet_ids,
        mission_simulation_error=mission_simulation_error,
    )


def baseline_state_after_horizon(
    state: GameState,
    horizon_ticks: int,
) -> GameState:
    """Return idle baseline state after ``horizon_ticks`` ticks."""

    EvaluationConfig(horizon_ticks=horizon_ticks)
    if horizon_ticks == 0:
        return state
    return simulate_ticks(state, horizon_ticks)


def candidate_state_after_horizon(
    state: GameState,
    candidate: MissionCandidate,
    horizon_ticks: int,
    player_id: int | None = None,
) -> GameState:
    """Return candidate future state after inserting mission launches."""

    EvaluationConfig(horizon_ticks=horizon_ticks)
    if not candidate.launches:
        return baseline_state_after_horizon(state, horizon_ticks)
    orders = mission_candidate_to_orders(state, candidate, player_id=player_id)
    return simulate_launch_orders(
        state,
        orders,
        ticks=horizon_ticks,
        player_id=player_id,
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


@dataclass(frozen=True, slots=True)
class _CandidatePlanetLookup:
    target: PlanetEvaluationFacts | None
    sources: tuple[PlanetEvaluationFacts, ...]
    missing_target_planet_id: int | None
    missing_source_planet_ids: tuple[int, ...]


def _lookup_candidate_planets(
    candidate: MissionCandidate,
    state: GameState | None,
) -> _CandidatePlanetLookup:
    planets_by_id = _planets_by_id(state)
    target = None
    missing_target_planet_id = None
    if state is not None and candidate.target_planet_id is not None:
        target_planet = planets_by_id.get(candidate.target_planet_id)
        if target_planet is None:
            missing_target_planet_id = candidate.target_planet_id
        else:
            target = planet_evaluation_facts(target_planet)

    sources: list[PlanetEvaluationFacts] = []
    missing_source_planet_ids: list[int] = []
    if state is not None:
        for source_planet_id in candidate.source_planet_ids:
            source = planets_by_id.get(source_planet_id)
            if source is None:
                missing_source_planet_ids.append(source_planet_id)
            else:
                sources.append(planet_evaluation_facts(source))

    return _CandidatePlanetLookup(
        target=target,
        sources=tuple(sources),
        missing_target_planet_id=missing_target_planet_id,
        missing_source_planet_ids=tuple(missing_source_planet_ids),
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
    "baseline_state_after_horizon",
    "candidate_state_after_horizon",
    "evaluate_candidates",
    "extract_candidate_facts",
    "planet_evaluation_facts",
)
