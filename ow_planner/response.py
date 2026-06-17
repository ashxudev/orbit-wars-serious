"""Planner opponent-response model contracts.

Opponent Response Model Cycle 0 defines immutable response-evaluation
containers and a structural public API. Cycle 1 adds deterministic opponent
reinforcement feasibility facts. Cycle 2 adds deterministic target race-risk
facts. It does not model counterattacks, third-party effects, scoring, ranking,
pruning, or selection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence

from ow_sim.forecast import fleet_ticks_to_reach_distance
from ow_sim.geometry import distance
from ow_sim.state import GameState, Planet

from .evaluation import MissionEvaluation


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
class MissionResponseFacts:
    """Deterministic response facts for one mission evaluation."""

    response_labels: tuple[str, ...] = ()
    target_reinforcement: TargetReinforcementFacts = field(
        default_factory=TargetReinforcementFacts
    )
    target_race: TargetRaceFacts = field(default_factory=TargetRaceFacts)
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
        response_evaluations.append(
            MissionResponseEvaluation(
                evaluation=evaluation,
                status=ResponseEvaluationStatus.EVALUATED,
                facts=MissionResponseFacts(
                    target_reinforcement=target_reinforcement,
                    target_race=target_race,
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


__all__ = (
    "MissionResponseEvaluation",
    "MissionResponseFacts",
    "RaceSourceFacts",
    "ReinforcementSourceFacts",
    "ResponseConfig",
    "ResponseEvaluationStatus",
    "TargetRaceFacts",
    "TargetReinforcementFacts",
    "evaluate_responses",
    "target_race_facts",
    "target_reinforcement_facts",
)
