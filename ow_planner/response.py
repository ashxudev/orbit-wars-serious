"""Planner opponent-response model contracts.

Opponent Response Model Cycle 0 defines immutable response-evaluation
containers and a structural public API. Cycle 1 adds deterministic opponent
reinforcement feasibility facts. Cycle 2 adds deterministic target race-risk
facts. Cycle 3 adds deterministic source counterattack-risk facts. Cycle 4 adds
deterministic FFA third-party benefit facts. Cycle 5 adds deterministic response
summary labels. It does not model scoring, ranking, pruning, or selection.
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
class ThirdPartyOwnerFacts:
    """Current-state summary for one non-player owner outside the target owner."""

    owner: int
    current_planet_count: int
    current_production: int
    current_ships: int
    unaffected_by_target_ownership_change: bool


@dataclass(frozen=True, slots=True)
class ThirdPartyBenefitFacts:
    """Deterministic FFA third-party benefit facts for one mission target."""

    player_id: int | None = None
    target_planet_id: int | None = None
    target_owner_before: int | None = None
    target_owner_baseline: int | None = None
    target_owner_mission: int | None = None
    target_production_before: int | None = None
    target_owner_is_non_player: bool | None = None
    target_owner_damaged_by_mission: bool | None = None
    target_owner_loses_control_by_mission: bool | None = None
    third_party_owner_facts: tuple[ThirdPartyOwnerFacts, ...] = ()
    unaffected_non_player_owner_count: int = 0
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ResponseSummaryFacts:
    """Deterministic summary labels and counts for response facts."""

    labels: tuple[str, ...] = ()
    target_reinforcement_feasible: bool = False
    target_race_risk: bool = False
    source_counterattack_risk: bool = False
    third_party_benefit_possible: bool = False
    reinforcement_feasible_source_count: int = 0
    race_by_earliest_source_count: int = 0
    counterattack_arrives_by_window_count: int = 0
    third_party_owner_count: int = 0
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
    third_party_benefit: ThirdPartyBenefitFacts = field(
        default_factory=ThirdPartyBenefitFacts
    )
    response_summary: ResponseSummaryFacts = field(default_factory=ResponseSummaryFacts)
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
        third_party_benefit = third_party_benefit_facts(
            state,
            evaluation,
            effective_config,
        )
        facts = MissionResponseFacts(
            target_reinforcement=target_reinforcement,
            target_race=target_race,
            source_counterattacks=source_counterattacks,
            third_party_benefit=third_party_benefit,
        )
        response_summary = response_summary_facts(facts)
        response_evaluations.append(
            MissionResponseEvaluation(
                evaluation=evaluation,
                status=ResponseEvaluationStatus.EVALUATED,
                facts=MissionResponseFacts(
                    response_labels=response_summary.labels,
                    target_reinforcement=target_reinforcement,
                    target_race=target_race,
                    source_counterattacks=source_counterattacks,
                    third_party_benefit=third_party_benefit,
                    response_summary=response_summary,
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


def third_party_benefit_facts(
    state: GameState,
    evaluation: MissionEvaluation,
    config: ResponseConfig | None = None,
) -> ThirdPartyBenefitFacts:
    """Return deterministic FFA third-party benefit facts."""

    ResponseConfig() if config is None else config
    facts = evaluation.facts
    if facts is None:
        return ThirdPartyBenefitFacts(notes=("mission facts are missing",))

    notes: list[str] = []
    player_id = state.player_id
    if player_id is None:
        notes.append("player id is missing")

    target_before = facts.target_before
    target_baseline = facts.target_baseline
    target_mission = facts.target_mission
    if target_before is None:
        notes.append("target before facts are missing")
    if target_baseline is None:
        notes.append("target baseline facts are missing")
    if target_mission is None:
        notes.append("target mission facts are missing")

    target_owner_before = None if target_before is None else target_before.owner
    target_owner_baseline = None if target_baseline is None else target_baseline.owner
    target_owner_mission = None if target_mission is None else target_mission.owner
    target_production_before = None if target_before is None else target_before.production

    target_owner_is_non_player = _target_owner_is_non_player(
        target_owner_before,
        player_id,
    )
    target_owner_loses_control = _target_owner_loses_control_by_mission(
        target_owner_before,
        target_owner_mission,
        player_id,
    )
    target_owner_damaged = _target_owner_damaged_by_mission(
        target_owner_before,
        target_owner_baseline,
        target_owner_mission,
        player_id,
    )

    third_party_owner_facts = _third_party_owner_facts(
        state,
        player_id,
        target_owner_before,
    )
    if player_id is not None and target_owner_before is not None and not third_party_owner_facts:
        notes.append("no third-party owners")

    return ThirdPartyBenefitFacts(
        player_id=player_id,
        target_planet_id=facts.target_planet_id,
        target_owner_before=target_owner_before,
        target_owner_baseline=target_owner_baseline,
        target_owner_mission=target_owner_mission,
        target_production_before=target_production_before,
        target_owner_is_non_player=target_owner_is_non_player,
        target_owner_damaged_by_mission=target_owner_damaged,
        target_owner_loses_control_by_mission=target_owner_loses_control,
        third_party_owner_facts=third_party_owner_facts,
        unaffected_non_player_owner_count=sum(
            1
            for owner_facts in third_party_owner_facts
            if owner_facts.unaffected_by_target_ownership_change
        ),
        notes=tuple(notes),
    )


def response_summary_facts(
    response_facts: MissionResponseFacts,
) -> ResponseSummaryFacts:
    """Return deterministic labels and counts from response facts."""

    reinforcement_count = response_facts.target_reinforcement.feasible_source_count
    race_by_earliest_count = sum(
        1
        for source in response_facts.target_race.source_facts
        if source.can_arrive_by_earliest
    )
    counterattack_by_window_count = sum(
        1
        for source_facts in response_facts.source_counterattacks
        for source in source_facts.counterattack_sources
        if source.arrives_by_response_window
    )
    third_party_owner_count = (
        response_facts.third_party_benefit.unaffected_non_player_owner_count
    )

    target_reinforcement_feasible = reinforcement_count > 0
    target_race_risk = race_by_earliest_count > 0
    source_counterattack_risk = counterattack_by_window_count > 0
    third_party_benefit_possible = (
        response_facts.third_party_benefit.target_owner_damaged_by_mission is True
        and third_party_owner_count > 0
    )

    labels: list[str] = []
    if target_reinforcement_feasible:
        labels.append("target_reinforcement_feasible")
    if target_race_risk:
        labels.append("target_race_risk")
    if source_counterattack_risk:
        labels.append("source_counterattack_risk")
    if third_party_benefit_possible:
        labels.append("third_party_benefit_possible")

    return ResponseSummaryFacts(
        labels=tuple(labels),
        target_reinforcement_feasible=target_reinforcement_feasible,
        target_race_risk=target_race_risk,
        source_counterattack_risk=source_counterattack_risk,
        third_party_benefit_possible=third_party_benefit_possible,
        reinforcement_feasible_source_count=reinforcement_count,
        race_by_earliest_source_count=race_by_earliest_count,
        counterattack_arrives_by_window_count=counterattack_by_window_count,
        third_party_owner_count=third_party_owner_count,
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


def _third_party_owner_facts(
    state: GameState,
    player_id: int | None,
    target_owner_before: int | None,
) -> tuple[ThirdPartyOwnerFacts, ...]:
    if player_id is None or target_owner_before is None:
        return ()

    owner_totals: dict[int, tuple[int, int, int]] = {}
    for planet in state.planets:
        if (
            planet.owner < 0
            or planet.owner == player_id
            or planet.owner == target_owner_before
            or planet.is_comet
        ):
            continue
        planet_count, production, ships = owner_totals.get(planet.owner, (0, 0, 0))
        owner_totals[planet.owner] = (
            planet_count + 1,
            production + planet.production,
            ships + planet.ships,
        )

    return tuple(
        ThirdPartyOwnerFacts(
            owner=owner,
            current_planet_count=planet_count,
            current_production=production,
            current_ships=ships,
            unaffected_by_target_ownership_change=True,
        )
        for owner, (planet_count, production, ships) in sorted(owner_totals.items())
    )


def _target_owner_is_non_player(
    target_owner_before: int | None,
    player_id: int | None,
) -> bool | None:
    if target_owner_before is None or player_id is None:
        return None
    return target_owner_before >= 0 and target_owner_before != player_id


def _target_owner_loses_control_by_mission(
    target_owner_before: int | None,
    target_owner_mission: int | None,
    player_id: int | None,
) -> bool | None:
    target_owner_is_non_player = _target_owner_is_non_player(
        target_owner_before,
        player_id,
    )
    if target_owner_is_non_player is None or target_owner_mission is None:
        return None
    return target_owner_is_non_player and target_owner_mission != target_owner_before


def _target_owner_damaged_by_mission(
    target_owner_before: int | None,
    target_owner_baseline: int | None,
    target_owner_mission: int | None,
    player_id: int | None,
) -> bool | None:
    target_owner_loses_control = _target_owner_loses_control_by_mission(
        target_owner_before,
        target_owner_mission,
        player_id,
    )
    if target_owner_loses_control is None or target_owner_baseline is None:
        return None
    return target_owner_loses_control and target_owner_baseline == target_owner_before


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
    "ResponseSummaryFacts",
    "SourceCounterattackFacts",
    "TargetRaceFacts",
    "TargetReinforcementFacts",
    "ThirdPartyBenefitFacts",
    "ThirdPartyOwnerFacts",
    "evaluate_responses",
    "response_summary_facts",
    "source_counterattack_facts",
    "target_race_facts",
    "target_reinforcement_facts",
    "third_party_benefit_facts",
)
