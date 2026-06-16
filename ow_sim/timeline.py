"""Pure one-tick event summaries for Orbit Wars.

Cycle 9 integrates collision/removal queries with combat resolution facts for
existing fleets only. It does not mutate game state, remove fleets, update
planet rows, apply production, expire comets, or insert hypothetical launches.
"""

from __future__ import annotations

from dataclasses import dataclass

from .combat import PlanetCombatResult, resolve_planet_combat
from .collision import (
    FleetRemovalEvent,
    FleetRemovalReason,
    fleet_removal_event_for_tick,
)
from .state import Fleet, GameState


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


def _validate_tick_count(dt: int) -> None:
    if isinstance(dt, bool) or not isinstance(dt, int) or dt < 1:
        raise ValueError("dt must be an integer >= 1")


__all__ = (
    "OneTickEventSummary",
    "PlanetArrivalCombatEvent",
    "fleet_removal_events_for_tick",
    "one_tick_event_summary",
    "planet_arrival_combat_events_for_tick",
    "planet_arrival_fleets_for_tick",
)
