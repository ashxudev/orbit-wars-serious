"""Pure one-tick timeline facts for Orbit Wars.

Cycle 9 integrates collision/removal queries with combat resolution facts for
existing fleets only. It does not mutate game state, remove fleets, update
planet rows, apply production, expire comets, or insert hypothetical launches.

Cycle 10 adds immutable one-tick delta facts built from the same event summary
and existing movement helpers. These deltas still do not apply a next state.
"""

from __future__ import annotations

from dataclasses import dataclass

from .combat import PlanetCombatResult, resolve_planet_combat
from .collision import (
    FleetRemovalEvent,
    FleetRemovalReason,
    fleet_removal_event_for_tick,
)
from .forecast import fleet_path_for_tick, planet_path_for_tick
from .state import Fleet, GameState, Point2D


@dataclass(frozen=True, slots=True)
class PlanetArrivalCombatEvent:
    """Pure combat summary for fleets arriving at one planet this tick."""

    planet_id: int
    fleet_ids: tuple[int, ...]
    fleets: tuple[Fleet, ...]
    combat_result: PlanetCombatResult


@dataclass(frozen=True, slots=True)
class OneTickEventSummary:
    """Pure removal and planet-arrival summary for one movement tick."""

    removal_events: tuple[FleetRemovalEvent, ...]
    planet_arrivals: tuple[PlanetArrivalCombatEvent, ...]
    bounds_fleet_ids: tuple[int, ...]
    sun_fleet_ids: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class FleetTickDelta:
    """Pure one-tick movement/removal facts for one existing fleet."""

    fleet_id: int
    old_position: Point2D
    new_position: Point2D
    removed: bool
    removal_event: FleetRemovalEvent | None


@dataclass(frozen=True, slots=True)
class PlanetTickDelta:
    """Pure one-tick movement/combat facts for one existing planet."""

    planet_id: int
    old_position: Point2D
    new_position: Point2D | None
    combat_result: PlanetCombatResult | None
    has_arrivals: bool


@dataclass(frozen=True, slots=True)
class OneTickStateDelta:
    """Pure one-tick state-delta facts without applying a next state."""

    fleet_deltas: tuple[FleetTickDelta, ...]
    planet_deltas: tuple[PlanetTickDelta, ...]
    event_summary: OneTickEventSummary


def fleet_removal_events_for_tick(
    state: GameState,
    dt: int = 1,
) -> tuple[FleetRemovalEvent, ...]:
    """Return removal events for existing fleets, preserving fleet order."""

    events, _ = _removal_events_and_arrivals(state, dt)
    return events


def planet_arrival_fleets_for_tick(
    state: GameState,
    dt: int = 1,
) -> dict[int, tuple[Fleet, ...]]:
    """Return planet-hit fleets grouped by planet id in fleet iteration order."""

    _, arrivals = _removal_events_and_arrivals(state, dt)
    return {
        planet_id: tuple(fleets)
        for planet_id, fleets in arrivals.items()
    }


def planet_arrival_combat_events_for_tick(
    state: GameState,
    dt: int = 1,
) -> tuple[PlanetArrivalCombatEvent, ...]:
    """Return combat summaries for planet arrivals in ``state.planets`` order."""

    _, arrivals = _removal_events_and_arrivals(state, dt)
    return _planet_arrival_combat_events_from_arrivals(state, arrivals)


def one_tick_event_summary(
    state: GameState,
    dt: int = 1,
) -> OneTickEventSummary:
    """Return a pure one-tick removal and planet-arrival event summary."""

    removal_events, arrivals = _removal_events_and_arrivals(state, dt)
    return OneTickEventSummary(
        removal_events=removal_events,
        planet_arrivals=_planet_arrival_combat_events_from_arrivals(state, arrivals),
        bounds_fleet_ids=tuple(
            event.fleet_id
            for event in removal_events
            if event.reason == FleetRemovalReason.BOUNDS
        ),
        sun_fleet_ids=tuple(
            event.fleet_id
            for event in removal_events
            if event.reason == FleetRemovalReason.SUN
        ),
    )


def fleet_tick_deltas(
    state: GameState,
    dt: int = 1,
) -> tuple[FleetTickDelta, ...]:
    """Return movement/removal deltas for existing fleets in fleet order."""

    summary = one_tick_event_summary(state, dt)
    return _fleet_tick_deltas_from_summary(state, dt, summary)


def planet_tick_deltas(
    state: GameState,
    dt: int = 1,
) -> tuple[PlanetTickDelta, ...]:
    """Return movement/combat deltas for existing planets in planet order."""

    summary = one_tick_event_summary(state, dt)
    return _planet_tick_deltas_from_summary(state, dt, summary)


def one_tick_state_delta(
    state: GameState,
    dt: int = 1,
) -> OneTickStateDelta:
    """Return pure one-tick fleet, planet, and event-summary facts."""

    summary = one_tick_event_summary(state, dt)
    return OneTickStateDelta(
        fleet_deltas=_fleet_tick_deltas_from_summary(state, dt, summary),
        planet_deltas=_planet_tick_deltas_from_summary(state, dt, summary),
        event_summary=summary,
    )


def _removal_events_and_arrivals(
    state: GameState,
    dt: int,
) -> tuple[tuple[FleetRemovalEvent, ...], dict[int, list[Fleet]]]:
    _validate_tick_count(dt)

    removal_events: list[FleetRemovalEvent] = []
    arrivals: dict[int, list[Fleet]] = {}

    for fleet in state.fleets:
        event = fleet_removal_event_for_tick(state, fleet, dt)
        if event is None:
            continue

        removal_events.append(event)
        if event.reason == FleetRemovalReason.PLANET and event.planet_id is not None:
            arrivals.setdefault(event.planet_id, []).append(fleet)

    return (tuple(removal_events), arrivals)


def _planet_arrival_combat_events_from_arrivals(
    state: GameState,
    arrivals: dict[int, list[Fleet]],
) -> tuple[PlanetArrivalCombatEvent, ...]:
    events: list[PlanetArrivalCombatEvent] = []

    for planet in state.planets:
        fleets = arrivals.get(planet.planet_id)
        if not fleets:
            continue

        fleet_tuple = tuple(fleets)
        events.append(
            PlanetArrivalCombatEvent(
                planet_id=planet.planet_id,
                fleet_ids=tuple(fleet.fleet_id for fleet in fleet_tuple),
                fleets=fleet_tuple,
                combat_result=resolve_planet_combat(planet, fleet_tuple),
            )
        )

    return tuple(events)


def _fleet_tick_deltas_from_summary(
    state: GameState,
    dt: int,
    summary: OneTickEventSummary,
) -> tuple[FleetTickDelta, ...]:
    removal_by_fleet_id = {
        event.fleet_id: event
        for event in summary.removal_events
    }

    deltas: list[FleetTickDelta] = []
    for fleet in state.fleets:
        old_position, new_position = fleet_path_for_tick(fleet, dt)
        removal_event = removal_by_fleet_id.get(fleet.fleet_id)
        deltas.append(
            FleetTickDelta(
                fleet_id=fleet.fleet_id,
                old_position=old_position,
                new_position=new_position,
                removed=removal_event is not None,
                removal_event=removal_event,
            )
        )

    return tuple(deltas)


def _planet_tick_deltas_from_summary(
    state: GameState,
    dt: int,
    summary: OneTickEventSummary,
) -> tuple[PlanetTickDelta, ...]:
    combat_by_planet_id = {
        event.planet_id: event.combat_result
        for event in summary.planet_arrivals
    }

    deltas: list[PlanetTickDelta] = []
    for planet in state.planets:
        path = planet_path_for_tick(state, planet.planet_id, dt)
        if path is None:
            old_position = planet.position
            new_position = None
        else:
            old_position = path[0]
            new_position = path[1]

        combat_result = combat_by_planet_id.get(planet.planet_id)
        deltas.append(
            PlanetTickDelta(
                planet_id=planet.planet_id,
                old_position=old_position,
                new_position=new_position,
                combat_result=combat_result,
                has_arrivals=combat_result is not None,
            )
        )

    return tuple(deltas)


def _validate_tick_count(dt: int) -> None:
    if isinstance(dt, bool) or not isinstance(dt, int) or dt < 1:
        raise ValueError("dt must be an integer >= 1")


__all__ = (
    "FleetTickDelta",
    "OneTickEventSummary",
    "OneTickStateDelta",
    "PlanetTickDelta",
    "PlanetArrivalCombatEvent",
    "fleet_tick_deltas",
    "fleet_removal_events_for_tick",
    "one_tick_event_summary",
    "one_tick_state_delta",
    "planet_tick_deltas",
    "planet_arrival_combat_events_for_tick",
    "planet_arrival_fleets_for_tick",
)
