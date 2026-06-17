"""Planner opponent-response model contracts.

Opponent Response Model Cycle 0 defines immutable response-evaluation
containers and a structural public API. Cycle 1 adds deterministic opponent
reinforcement feasibility facts. Cycle 2 adds deterministic target race-risk
facts. Cycle 3 adds deterministic source counterattack-risk facts. It does not
model third-party effects, scoring, ranking, pruning, or selection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence

from ow_sim.forecast import fleet_ticks_to_reach_distance
from ow_sim.geometry import distance
from ow_sim.state import GameState, Planet

from .evaluation import (
    MissionEvaluation,
    PlanetEvaluationFacts,
    PlanetFutureDeltaFacts,
)


class ResponseEvaluationStatus(str, Enum):
    """Status for opponent-response evaluation lifecycle."""

    UNEVALUATED = "unevaluated"
    EVALUATED = "evaluated"
    INCOMPLETE = "incomplete"


@dataclass(frozen=True, slots=True)
class ResponseConfig:
    """Configuration boundary for future opponent-response modeling."""

    response_window_ticks: int = 0

    def __post_init__(self) -> None:
        if (
            isinstance(self.response_window_ticks, bool)
            or not isinstance(self.response_window_ticks, int)
            or self.response_window_ticks < 0
        ):
            raise ValueError("response_window_ticks must be an integer >= 0")


@dataclass(frozen=True, slots=True)
class ReinforcementSourceFacts:
    """Deterministic feasibility facts for one potential reinforcing planet."""

    planet_id: int
    owner: int
    ships: int
    distance_to_target: float
    travel_ticks: int | None
    arrives_by_window: bool | None


@dataclass(frozen=True, slots=True)
class TargetReinforcementFacts:
    """Deterministic reinforcement facts for one mission target."""

    target_planet_id: int | None = None
    arrival_window_ticks: int | None = None
    timing_complete: bool = False
    source_facts: tuple[ReinforcementSourceFacts, ...] = ()
    feasible_source_count: int = 0
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RaceSourceFacts:
    """Deterministic race timing facts for one potential opponent source."""

    planet_id: int
    owner: int
    ships: int
    distance_to_target: float
    travel_ticks: int
    can_arrive_before_earliest: bool
    can_arrive_by_earliest: bool
    can_arrive_by_latest: bool
    target_ships_before: int | None
    source_has_more_ships_than_target_before: bool | None


@dataclass(frozen=True, slots=True)
class TargetRaceFacts:
    """Deterministic target race-risk facts for one mission target."""

    target_planet_id: int | None = None
    min_arrival_ticks: int | None = None
    max_arrival_ticks: int | None = None
    timing_complete: bool = False
    target_ships_before: int | None = None
    source_facts: tuple[RaceSourceFacts, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CounterattackSourceFacts:
    """Deterministic counterattack timing facts for one non-player source."""

    planet_id: int
    owner: int
    ships: int
    distance_to_source: float
    travel_ticks: int
    arrives_by_response_window: bool
    source_ships_after_mission: int | None
    source_has_more_ships_than_source_after_mission: bool | None


@dataclass(frozen=True, slots=True)
class SourceCounterattackFacts:
    """Deterministic counterattack facts for one mission source planet."""

    source_planet_id: int
    source_owner_before: int | None = None
    source_ships_before: int | None = None
    source_ships_after_mission: int | None = None
    source_ship_delta_vs_before: int | None = None
    ships_drained: int | None = None
    source_after_mission_is_depleted: bool | None = None
    response_window_ticks: int = 0
    counterattack_sources: tuple[CounterattackSourceFacts, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MissionResponseFacts:
    """Deterministic response facts for one mission evaluation."""

    response_labels: tuple[str, ...] = ()
    target_reinforcement: TargetReinforcementFacts = field(
        default_factory=TargetReinforcementFacts
    )
    target_race: TargetRaceFacts = field(default_factory=TargetRaceFacts)
    source_counterattacks: tuple[SourceCounterattackFacts, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MissionResponseEvaluation:
    """Structural opponent-response wrapper for one mission evaluation."""

    evaluation: MissionEvaluation
    status: ResponseEvaluationStatus = ResponseEvaluationStatus.UNEVALUATED
    facts: MissionResponseFacts = field(default_factory=MissionResponseFacts)
    note: str | None = None


def evaluate_responses(
    state: GameState,
    evaluations: Sequence[MissionEvaluation],
    config: ResponseConfig | None = None,
) -> tuple[MissionResponseEvaluation, ...]:
    """Return structural opponent-response evaluations in input order."""

    effective_config = ResponseConfig() if config is None else config
    if not evaluations:
        return ()

    response_evaluations: list[MissionResponseEvaluation] = []
    for evaluation in evaluations:
        if evaluation.facts is None:
            response_evaluations.append(
                MissionResponseEvaluation(
                    evaluation=evaluation,
                    status=ResponseEvaluationStatus.INCOMPLETE,
                    facts=MissionResponseFacts(
                        notes=("mission facts are missing",),
                    ),
                    note="mission facts are missing",
                )
            )
            continue
        target_reinforcement = target_reinforcement_facts(
            state,
            evaluation,
            effective_config,
        )
        target_race = target_race_facts(
            state,
            evaluation,
            effective_config,
        )
        source_counterattacks = source_counterattack_facts(
            state,
            evaluation,
            effective_config,
        )
        response_evaluations.append(
            MissionResponseEvaluation(
                evaluation=evaluation,
                status=ResponseEvaluationStatus.EVALUATED,
                facts=MissionResponseFacts(
                    target_reinforcement=target_reinforcement,
                    target_race=target_race,
                    source_counterattacks=source_counterattacks,
                ),
            )
        )
    return tuple(response_evaluations)


def target_reinforcement_facts(
    state: GameState,
    evaluation: MissionEvaluation,
    config: ResponseConfig | None = None,
) -> TargetReinforcementFacts:
    """Return deterministic opponent reinforcement feasibility facts."""

    effective_config = ResponseConfig() if config is None else config
    facts = evaluation.facts
    if facts is None:
        return TargetReinforcementFacts(notes=("mission facts are missing",))
    if state.player_id is None:
        return TargetReinforcementFacts(
            target_planet_id=facts.target_planet_id,
            notes=("player id is missing",),
        )
    if facts.target_planet_id is None:
        return TargetReinforcementFacts(notes=("target planet id is missing",))

    timing_facts = facts.timing_facts
    if (
        not timing_facts.timing_complete
        or timing_facts.max_arrival_ticks is None
    ):
        return TargetReinforcementFacts(
            target_planet_id=facts.target_planet_id,
            notes=("mission arrival timing is incomplete",),
        )

    target = _planet_by_id(state, facts.target_planet_id)
    if target is None:
        return TargetReinforcementFacts(
            target_planet_id=facts.target_planet_id,
            arrival_window_ticks=(
                timing_facts.max_arrival_ticks + effective_config.response_window_ticks
            ),
            timing_complete=True,
            notes=("target planet is missing",),
        )

    arrival_window_ticks = (
        timing_facts.max_arrival_ticks + effective_config.response_window_ticks
    )
    source_facts = tuple(
        _reinforcement_source_facts(source, target, arrival_window_ticks)
        for source in state.planets
        if _is_candidate_reinforcement_source(source, target, state.player_id)
    )
    feasible_source_count = sum(
        1 for source in source_facts if source.arrives_by_window is True
    )
    notes = (
        ("no candidate reinforcing planets",)
        if not source_facts
        else ()
    )
    return TargetReinforcementFacts(
        target_planet_id=target.planet_id,
        arrival_window_ticks=arrival_window_ticks,
        timing_complete=True,
        source_facts=source_facts,
        feasible_source_count=feasible_source_count,
        notes=notes,
    )


def target_race_facts(
    state: GameState,
    evaluation: MissionEvaluation,
    config: ResponseConfig | None = None,
) -> TargetRaceFacts:
    """Return deterministic target race-risk facts."""

    ResponseConfig() if config is None else config
    facts = evaluation.facts
    if facts is None:
        return TargetRaceFacts(notes=("mission facts are missing",))
    if state.player_id is None:
        return TargetRaceFacts(
            target_planet_id=facts.target_planet_id,
            notes=("player id is missing",),
        )
    if facts.target_planet_id is None:
        return TargetRaceFacts(notes=("target planet id is missing",))

    timing_facts = facts.timing_facts
    if (
        not timing_facts.timing_complete
        or timing_facts.min_arrival_ticks is None
        or timing_facts.max_arrival_ticks is None
    ):
        return TargetRaceFacts(
            target_planet_id=facts.target_planet_id,
            notes=("mission arrival timing is incomplete",),
        )

    target = _planet_by_id(state, facts.target_planet_id)
    if target is None:
        return TargetRaceFacts(
            target_planet_id=facts.target_planet_id,
            min_arrival_ticks=timing_facts.min_arrival_ticks,
            max_arrival_ticks=timing_facts.max_arrival_ticks,
            timing_complete=True,
            notes=("target planet is missing",),
        )

    source_facts = tuple(
        _race_source_facts(
            source,
            target,
            timing_facts.min_arrival_ticks,
            timing_facts.max_arrival_ticks,
        )
        for source in state.planets
        if _is_candidate_response_source(source, target, state.player_id)
    )
    notes = ("no candidate race sources",) if not source_facts else ()
    return TargetRaceFacts(
        target_planet_id=target.planet_id,
        min_arrival_ticks=timing_facts.min_arrival_ticks,
        max_arrival_ticks=timing_facts.max_arrival_ticks,
        timing_complete=True,
        target_ships_before=target.ships,
        source_facts=source_facts,
        notes=notes,
    )


def source_counterattack_facts(
    state: GameState,
    evaluation: MissionEvaluation,
    config: ResponseConfig | None = None,
) -> tuple[SourceCounterattackFacts, ...]:
    """Return deterministic counterattack facts for mission source planets."""

    effective_config = ResponseConfig() if config is None else config
    facts = evaluation.facts
    if facts is None:
        return ()

    before_by_id = _planet_evaluation_facts_by_id(facts.sources_before)
    mission_by_id = _planet_evaluation_facts_by_id(facts.sources_mission)
    delta_by_id = _planet_future_delta_facts_by_id(facts.future_delta.sources)
    return tuple(
        _source_counterattack_facts_for_source(
            state,
            source_planet_id,
            before_by_id.get(source_planet_id),
            mission_by_id.get(source_planet_id),
            delta_by_id.get(source_planet_id),
            effective_config.response_window_ticks,
        )
        for source_planet_id in facts.source_planet_ids
    )


def _reinforcement_source_facts(
    source: Planet,
    target: Planet,
    arrival_window_ticks: int,
) -> ReinforcementSourceFacts:
    distance_to_target = distance(source.position, target.position)
    travel_ticks = None
    arrives_by_window = None
    if source.ships > 0:
        travel_ticks = fleet_ticks_to_reach_distance(
            distance_to_target,
            source.ships,
        )
        arrives_by_window = travel_ticks <= arrival_window_ticks
    return ReinforcementSourceFacts(
        planet_id=source.planet_id,
        owner=source.owner,
        ships=source.ships,
        distance_to_target=distance_to_target,
        travel_ticks=travel_ticks,
        arrives_by_window=arrives_by_window,
    )


def _race_source_facts(
    source: Planet,
    target: Planet,
    min_arrival_ticks: int,
    max_arrival_ticks: int,
) -> RaceSourceFacts:
    distance_to_target = distance(source.position, target.position)
    travel_ticks = fleet_ticks_to_reach_distance(distance_to_target, source.ships)
    source_has_more_ships = source.ships > target.ships
    return RaceSourceFacts(
        planet_id=source.planet_id,
        owner=source.owner,
        ships=source.ships,
        distance_to_target=distance_to_target,
        travel_ticks=travel_ticks,
        can_arrive_before_earliest=travel_ticks < min_arrival_ticks,
        can_arrive_by_earliest=travel_ticks <= min_arrival_ticks,
        can_arrive_by_latest=travel_ticks <= max_arrival_ticks,
        target_ships_before=target.ships,
        source_has_more_ships_than_target_before=source_has_more_ships,
    )


def _source_counterattack_facts_for_source(
    state: GameState,
    source_planet_id: int,
    before: PlanetEvaluationFacts | None,
    mission: PlanetEvaluationFacts | None,
    delta: PlanetFutureDeltaFacts | None,
    response_window_ticks: int,
) -> SourceCounterattackFacts:
    notes: list[str] = []
    if before is None:
        notes.append("source before facts are missing")
    if mission is None:
        notes.append("source mission facts are missing")
    if delta is None:
        notes.append("source delta facts are missing")

    source_planet = _planet_by_id(state, source_planet_id)
    if source_planet is None:
        notes.append("source planet is missing")
    if state.player_id is None:
        notes.append("player id is missing")

    source_ships_after_mission = None if mission is None else mission.ships
    source_ship_delta_vs_before = (
        None if delta is None else delta.mission_ship_delta_vs_before
    )
    ships_drained = (
        None
        if source_ship_delta_vs_before is None
        else max(0, -source_ship_delta_vs_before)
    )
    source_after_mission_is_depleted = (
        None if source_ships_after_mission is None else source_ships_after_mission <= 0
    )

    counterattack_sources: tuple[CounterattackSourceFacts, ...] = ()
    if source_planet is not None and state.player_id is not None:
        counterattack_sources = tuple(
            _counterattack_source_facts(
                candidate,
                source_planet,
                response_window_ticks,
                source_ships_after_mission,
            )
            for candidate in state.planets
            if _is_candidate_response_source(candidate, source_planet, state.player_id)
        )
        if not counterattack_sources:
            notes.append("no candidate counterattack sources")

    return SourceCounterattackFacts(
        source_planet_id=source_planet_id,
        source_owner_before=None if before is None else before.owner,
        source_ships_before=None if before is None else before.ships,
        source_ships_after_mission=source_ships_after_mission,
        source_ship_delta_vs_before=source_ship_delta_vs_before,
        ships_drained=ships_drained,
        source_after_mission_is_depleted=source_after_mission_is_depleted,
        response_window_ticks=response_window_ticks,
        counterattack_sources=counterattack_sources,
        notes=tuple(notes),
    )


def _counterattack_source_facts(
    counterattack_source: Planet,
    mission_source: Planet,
    response_window_ticks: int,
    source_ships_after_mission: int | None,
) -> CounterattackSourceFacts:
    distance_to_source = distance(counterattack_source.position, mission_source.position)
    travel_ticks = fleet_ticks_to_reach_distance(
        distance_to_source,
        counterattack_source.ships,
    )
    source_has_more_ships = (
        None
        if source_ships_after_mission is None
        else counterattack_source.ships > source_ships_after_mission
    )
    return CounterattackSourceFacts(
        planet_id=counterattack_source.planet_id,
        owner=counterattack_source.owner,
        ships=counterattack_source.ships,
        distance_to_source=distance_to_source,
        travel_ticks=travel_ticks,
        arrives_by_response_window=travel_ticks <= response_window_ticks,
        source_ships_after_mission=source_ships_after_mission,
        source_has_more_ships_than_source_after_mission=source_has_more_ships,
    )


def _is_candidate_reinforcement_source(
    source: Planet,
    target: Planet,
    player_id: int,
) -> bool:
    return _is_candidate_response_source(source, target, player_id)


def _is_candidate_response_source(
    source: Planet,
    target: Planet,
    player_id: int,
) -> bool:
    return (
        source.planet_id != target.planet_id
        and source.owner >= 0
        and source.owner != player_id
        and not source.is_comet
        and source.ships > 0
    )


def _planet_by_id(state: GameState, planet_id: int) -> Planet | None:
    for planet in state.planets:
        if planet.planet_id == planet_id:
            return planet
    return None


def _planet_evaluation_facts_by_id(
    planet_facts: tuple[PlanetEvaluationFacts, ...],
) -> dict[int, PlanetEvaluationFacts]:
    return {planet.planet_id: planet for planet in planet_facts}


def _planet_future_delta_facts_by_id(
    planet_facts: tuple[PlanetFutureDeltaFacts, ...],
) -> dict[int, PlanetFutureDeltaFacts]:
    return {
        planet.planet_id: planet
        for planet in planet_facts
        if planet.planet_id is not None
    }


__all__ = (
    "CounterattackSourceFacts",
    "MissionResponseEvaluation",
    "MissionResponseFacts",
    "RaceSourceFacts",
    "ReinforcementSourceFacts",
    "ResponseConfig",
    "ResponseEvaluationStatus",
    "SourceCounterattackFacts",
    "TargetRaceFacts",
    "TargetReinforcementFacts",
    "evaluate_responses",
    "source_counterattack_facts",
    "target_race_facts",
    "target_reinforcement_facts",
)
