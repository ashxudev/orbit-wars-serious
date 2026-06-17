"""Planner mission evaluation contracts.

Mission Evaluation Cycle 8 extracts deterministic candidate facts, before-state
source/target lookups, idle baseline future lookups, mechanical candidate
future lookups, mission-vs-baseline delta facts, and deterministic value
feature facts. It also exposes an opt-in evaluated-and-scored composition
helper. It does not rank, prune, or select missions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Sequence

from ow_sim.state import GameState, Planet
from ow_sim.timeline import simulate_ticks
from ow_sim.whatif import simulate_launch_orders

from .actions import mission_candidate_to_orders
from .candidates import CandidateOutcome, MissionCandidate, MissionType

if TYPE_CHECKING:
    from .scoring import MissionScoringConfig


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
class PlanetFutureDeltaFacts:
    """Deterministic before/baseline/mission comparison for one planet."""

    planet_id: int | None = None
    before_owner: int | None = None
    baseline_owner: int | None = None
    mission_owner: int | None = None
    before_ships: int | None = None
    baseline_ships: int | None = None
    mission_ships: int | None = None
    mission_ship_delta_vs_baseline: int | None = None
    mission_ship_delta_vs_before: int | None = None
    mission_owner_changed_vs_baseline: bool | None = None
    mission_owner_changed_vs_before: bool | None = None


@dataclass(frozen=True, slots=True)
class MissionFutureDeltaFacts:
    """Deterministic future comparison facts for one mission candidate."""

    target: PlanetFutureDeltaFacts | None = None
    sources: tuple[PlanetFutureDeltaFacts, ...] = ()
    total_source_ship_delta_vs_baseline: int | None = None
    total_source_ship_delta_vs_before: int | None = None


@dataclass(frozen=True, slots=True)
class MissionValueFacts:
    """Deterministic mission value features without weights or scores."""

    target_owner_before: int | None = None
    target_owner_baseline: int | None = None
    target_owner_mission: int | None = None
    target_captured_by_player: bool | None = None
    target_retained_by_player: bool | None = None
    target_lost_by_player: bool | None = None
    target_production_before: int | None = None
    target_production_baseline_controlled_by_player: int | None = None
    target_production_mission_controlled_by_player: int | None = None
    production_delta_vs_baseline: int | None = None
    target_ship_delta_vs_baseline: int | None = None
    total_source_ship_delta_vs_baseline: int | None = None
    total_source_ship_delta_vs_before: int | None = None
    ships_spent: int = 0
    mission_valid_for_value: bool = False


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
    future_delta: MissionFutureDeltaFacts = field(default_factory=MissionFutureDeltaFacts)
    value_facts: MissionValueFacts = field(default_factory=MissionValueFacts)
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

    Cycle 6 adds shared idle baseline facts, per-candidate mechanical mission
    future facts, mission-vs-baseline delta facts, and deterministic value
    feature facts. Input order is preserved.
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
                    player_id=state.player_id,
                ),
            ),
        )
    return tuple(evaluations)


def evaluate_and_score_candidates(
    state: GameState,
    candidates: Sequence[MissionCandidate],
    evaluation_config: EvaluationConfig | None = None,
    scoring_config: MissionScoringConfig | None = None,
) -> tuple[MissionEvaluation, ...]:
    """Return evaluated candidates with score components populated.

    This is a composition wrapper only: deterministic facts are produced by
    ``evaluate_candidates(...)`` and score fields are populated by the isolated
    scoring policy.
    """

    if not candidates:
        return ()
    from .scoring import score_evaluations

    evaluations = evaluate_candidates(
        state,
        candidates,
        config=evaluation_config,
    )
    return score_evaluations(evaluations, config=scoring_config)


def extract_candidate_facts(
    candidate: MissionCandidate,
    state: GameState | None = None,
    *,
    baseline_state: GameState | None = None,
    baseline_horizon_ticks: int = 0,
    mission_state: GameState | None = None,
    mission_horizon_ticks: int = 0,
    mission_simulation_error: str | None = None,
    player_id: int | None = None,
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
    future_delta = mission_future_delta_facts(
        target_planet_id=candidate.target_planet_id,
        source_planet_ids=candidate.source_planet_ids,
        target_before=before_lookup.target,
        target_baseline=baseline_lookup.target,
        target_mission=mission_lookup.target,
        sources_before=before_lookup.sources,
        sources_baseline=baseline_lookup.sources,
        sources_mission=mission_lookup.sources,
    )
    value_facts = mission_value_facts(
        player_id=player_id,
        target_before=before_lookup.target,
        target_baseline=baseline_lookup.target,
        target_mission=mission_lookup.target,
        future_delta=future_delta,
        ships_spent=sum(launch.ships for launch in candidate.launches),
        mission_simulation_error=mission_simulation_error,
    )

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
        future_delta=future_delta,
        value_facts=value_facts,
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


def planet_future_delta_facts(
    before: PlanetEvaluationFacts | None,
    baseline: PlanetEvaluationFacts | None,
    mission: PlanetEvaluationFacts | None,
    planet_id: int | None = None,
) -> PlanetFutureDeltaFacts:
    """Return deterministic deltas for one planet snapshot triple."""

    resolved_planet_id = _first_non_none(
        planet_id,
        None if before is None else before.planet_id,
        None if baseline is None else baseline.planet_id,
        None if mission is None else mission.planet_id,
    )
    return PlanetFutureDeltaFacts(
        planet_id=resolved_planet_id,
        before_owner=None if before is None else before.owner,
        baseline_owner=None if baseline is None else baseline.owner,
        mission_owner=None if mission is None else mission.owner,
        before_ships=None if before is None else before.ships,
        baseline_ships=None if baseline is None else baseline.ships,
        mission_ships=None if mission is None else mission.ships,
        mission_ship_delta_vs_baseline=_ship_delta(mission, baseline),
        mission_ship_delta_vs_before=_ship_delta(mission, before),
        mission_owner_changed_vs_baseline=_owner_changed(mission, baseline),
        mission_owner_changed_vs_before=_owner_changed(mission, before),
    )


def mission_future_delta_facts(
    *,
    target_planet_id: int | None,
    source_planet_ids: tuple[int, ...],
    target_before: PlanetEvaluationFacts | None,
    target_baseline: PlanetEvaluationFacts | None,
    target_mission: PlanetEvaluationFacts | None,
    sources_before: tuple[PlanetEvaluationFacts, ...],
    sources_baseline: tuple[PlanetEvaluationFacts, ...],
    sources_mission: tuple[PlanetEvaluationFacts, ...],
) -> MissionFutureDeltaFacts:
    """Return deterministic mission-vs-baseline delta facts."""

    target = None
    if target_planet_id is not None:
        target = planet_future_delta_facts(
            target_before,
            target_baseline,
            target_mission,
            target_planet_id,
        )

    aligned_before = _align_planet_facts(source_planet_ids, sources_before)
    aligned_baseline = _align_planet_facts(source_planet_ids, sources_baseline)
    aligned_mission = _align_planet_facts(source_planet_ids, sources_mission)
    sources = tuple(
        planet_future_delta_facts(
            before,
            baseline,
            mission,
            source_planet_id,
        )
        for source_planet_id, before, baseline, mission in zip(
            source_planet_ids,
            aligned_before,
            aligned_baseline,
            aligned_mission,
        )
    )

    return MissionFutureDeltaFacts(
        target=target,
        sources=sources,
        total_source_ship_delta_vs_baseline=_sum_known_deltas(
            source.mission_ship_delta_vs_baseline
            for source in sources
        ),
        total_source_ship_delta_vs_before=_sum_known_deltas(
            source.mission_ship_delta_vs_before
            for source in sources
        ),
    )


def mission_value_facts(
    *,
    player_id: int | None,
    target_before: PlanetEvaluationFacts | None,
    target_baseline: PlanetEvaluationFacts | None,
    target_mission: PlanetEvaluationFacts | None,
    future_delta: MissionFutureDeltaFacts,
    ships_spent: int,
    mission_simulation_error: str | None = None,
) -> MissionValueFacts:
    """Return deterministic value features derived from evaluation facts."""

    baseline_controlled_production = _controlled_production(
        target_baseline,
        player_id,
    )
    mission_controlled_production = _controlled_production(
        target_mission,
        player_id,
    )
    return MissionValueFacts(
        target_owner_before=None if target_before is None else target_before.owner,
        target_owner_baseline=None if target_baseline is None else target_baseline.owner,
        target_owner_mission=None if target_mission is None else target_mission.owner,
        target_captured_by_player=_target_captured_by_player(
            target_baseline,
            target_mission,
            player_id,
        ),
        target_retained_by_player=_target_retained_by_player(
            target_baseline,
            target_mission,
            player_id,
        ),
        target_lost_by_player=_target_lost_by_player(
            target_baseline,
            target_mission,
            player_id,
        ),
        target_production_before=(
            None if target_before is None else target_before.production
        ),
        target_production_baseline_controlled_by_player=baseline_controlled_production,
        target_production_mission_controlled_by_player=mission_controlled_production,
        production_delta_vs_baseline=_int_delta(
            mission_controlled_production,
            baseline_controlled_production,
        ),
        target_ship_delta_vs_baseline=(
            None
            if future_delta.target is None
            else future_delta.target.mission_ship_delta_vs_baseline
        ),
        total_source_ship_delta_vs_baseline=(
            future_delta.total_source_ship_delta_vs_baseline
        ),
        total_source_ship_delta_vs_before=future_delta.total_source_ship_delta_vs_before,
        ships_spent=ships_spent,
        mission_valid_for_value=(
            mission_simulation_error is None
            and player_id is not None
            and target_before is not None
            and target_baseline is not None
            and target_mission is not None
            and future_delta.target is not None
            and future_delta.target.mission_ship_delta_vs_baseline is not None
            and future_delta.total_source_ship_delta_vs_baseline is not None
            and future_delta.total_source_ship_delta_vs_before is not None
        ),
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


def _align_planet_facts(
    planet_ids: tuple[int, ...],
    facts: tuple[PlanetEvaluationFacts, ...],
) -> tuple[PlanetEvaluationFacts | None, ...]:
    aligned: list[PlanetEvaluationFacts | None] = []
    cursor = 0
    for planet_id in planet_ids:
        if cursor < len(facts) and facts[cursor].planet_id == planet_id:
            aligned.append(facts[cursor])
            cursor += 1
        else:
            aligned.append(None)
    return tuple(aligned)


def _ship_delta(
    mission: PlanetEvaluationFacts | None,
    comparison: PlanetEvaluationFacts | None,
) -> int | None:
    if mission is None or comparison is None:
        return None
    return mission.ships - comparison.ships


def _owner_changed(
    mission: PlanetEvaluationFacts | None,
    comparison: PlanetEvaluationFacts | None,
) -> bool | None:
    if mission is None or comparison is None:
        return None
    return mission.owner != comparison.owner


def _sum_known_deltas(deltas: Sequence[int | None]) -> int | None:
    values = tuple(deltas)
    if any(value is None for value in values):
        return None
    return sum(value for value in values if value is not None)


def _first_non_none(*values: int | None) -> int | None:
    for value in values:
        if value is not None:
            return value
    return None


def _controlled_production(
    target: PlanetEvaluationFacts | None,
    player_id: int | None,
) -> int | None:
    if target is None or player_id is None:
        return None
    if target.owner == player_id:
        return target.production
    return 0


def _int_delta(
    mission_value: int | None,
    baseline_value: int | None,
) -> int | None:
    if mission_value is None or baseline_value is None:
        return None
    return mission_value - baseline_value


def _target_captured_by_player(
    baseline: PlanetEvaluationFacts | None,
    mission: PlanetEvaluationFacts | None,
    player_id: int | None,
) -> bool | None:
    if baseline is None or mission is None or player_id is None:
        return None
    return baseline.owner != player_id and mission.owner == player_id


def _target_retained_by_player(
    baseline: PlanetEvaluationFacts | None,
    mission: PlanetEvaluationFacts | None,
    player_id: int | None,
) -> bool | None:
    if baseline is None or mission is None or player_id is None:
        return None
    return baseline.owner == player_id and mission.owner == player_id


def _target_lost_by_player(
    baseline: PlanetEvaluationFacts | None,
    mission: PlanetEvaluationFacts | None,
    player_id: int | None,
) -> bool | None:
    if baseline is None or mission is None or player_id is None:
        return None
    return baseline.owner == player_id and mission.owner != player_id


__all__ = (
    "EvaluationConfig",
    "MissionEvaluation",
    "MissionEvaluationFacts",
    "MissionEvaluationStatus",
    "MissionFutureDeltaFacts",
    "MissionValueFacts",
    "PlanetEvaluationFacts",
    "PlanetFutureDeltaFacts",
    "ScoreComponent",
    "baseline_state_after_horizon",
    "candidate_state_after_horizon",
    "evaluate_and_score_candidates",
    "evaluate_candidates",
    "extract_candidate_facts",
    "mission_future_delta_facts",
    "mission_value_facts",
    "planet_evaluation_facts",
    "planet_future_delta_facts",
)
