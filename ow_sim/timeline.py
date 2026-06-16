"""Pure one-tick timeline facts for Orbit Wars.

Cycle 9 integrates collision/removal queries with combat resolution facts for
existing fleets only. It does not mutate game state, remove fleets, update
planet rows, apply production, expire comets, or insert hypothetical launches.

Cycle 10 adds immutable one-tick delta facts built from the same event summary
and existing movement helpers. These deltas still do not apply a next state.

Cycle 11 adds a pure one-tick next-state constructor for existing parsed state.
It applies production, movement, removals, comet expiry, and combat, but still
does not process actions, insert launches, or simulate multiple ticks.

Cycle 12 adds a narrow idle rollout wrapper that repeatedly applies the Cycle
11 one-tick constructor without adding what-if branching or actions.
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
from .state import CometGroup, Fleet, GameState, Planet, Point2D


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


def produce_planet(planet: Planet) -> Planet:
    """Return ``planet`` after official owned-planet production."""

    if planet.owner == -1:
        return planet
    return _planet_with(planet, ships=planet.ships + planet.production)


def apply_planet_position(planet: Planet, position: Point2D) -> Planet:
    """Return ``planet`` with an updated x/y position."""

    return _planet_with(planet, x=position[0], y=position[1])


def apply_planet_combat_result(
    planet: Planet,
    result: PlanetCombatResult,
) -> Planet:
    """Return ``planet`` with owner and ships from a combat result."""

    return _planet_with(planet, owner=result.owner, ships=result.ships)


def advance_comet_groups(
    state: GameState,
    expired_planet_ids: frozenset[int],
) -> tuple[CometGroup, ...]:
    """Return comet groups after one path-index advance and expiry filtering."""

    advanced_groups: list[CometGroup] = []

    for group in state.comets:
        next_path_index = (
            None
            if group.path_index is None
            else group.path_index + 1
        )
        planet_ids: list[int] = []
        paths: list[tuple[Point2D, ...]] = []

        for slot, planet_id in enumerate(group.planet_ids):
            if planet_id in expired_planet_ids:
                continue
            planet_ids.append(planet_id)
            if slot < len(group.paths):
                paths.append(group.paths[slot])

        if not planet_ids:
            continue

        advanced_groups.append(
            CometGroup(
                planet_ids=tuple(planet_ids),
                paths=tuple(paths),
                path_index=next_path_index,
                raw={
                    "planet_ids": tuple(planet_ids),
                    "paths": tuple(paths),
                    "path_index": next_path_index,
                },
            )
        )

    return tuple(advanced_groups)


def next_game_state_after_tick(
    state: GameState,
    dt: int = 1,
) -> GameState:
    """Return a new ``GameState`` after applying one official movement tick.

    This helper applies only existing parsed state. It does not process actions,
    insert launched fleets, spawn new comets, or support multi-tick mutation.
    """

    _validate_single_tick(dt)

    removal_events, arrivals = _removal_events_and_arrivals(state, dt)
    expired_planet_ids = _expired_comet_planet_ids_after_tick(state)
    moved_planets = _produced_and_moved_planets(state)
    planets_after_expiry = tuple(
        planet
        for planet in moved_planets
        if planet.planet_id not in expired_planet_ids
    )
    planets_after_combat = _apply_arrival_combat_to_planets(
        planets_after_expiry,
        arrivals,
    )

    removed_fleet_ids = frozenset(event.fleet_id for event in removal_events)
    moved_remaining_fleets = tuple(
        _move_fleet_one_tick(fleet)
        for fleet in state.fleets
        if fleet.fleet_id not in removed_fleet_ids
    )

    return GameState(
        tick=None if state.tick is None else state.tick + 1,
        player_id=state.player_id,
        planets=planets_after_combat,
        fleets=moved_remaining_fleets,
        angular_velocity=state.angular_velocity,
        initial_planets=tuple(
            planet
            for planet in state.initial_planets
            if planet.planet_id not in expired_planet_ids
        ),
        next_fleet_id=state.next_fleet_id,
        comet_planet_ids=frozenset(
            planet_id
            for planet_id in state.comet_planet_ids
            if planet_id not in expired_planet_ids
        ),
        comets=advance_comet_groups(state, expired_planet_ids),
        remaining_overage_time=state.remaining_overage_time,
        raw_observation=None,
    )


def simulate_ticks(state: GameState, ticks: int) -> GameState:
    """Return ``state`` advanced by ``ticks`` idle existing-state ticks."""

    _validate_rollout_ticks(ticks)
    current_state = state
    for _ in range(ticks):
        current_state = next_game_state_after_tick(current_state)
    return current_state


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


def _produced_and_moved_planets(state: GameState) -> tuple[Planet, ...]:
    planets: list[Planet] = []

    for planet in state.planets:
        moved_planet = produce_planet(planet)
        path = planet_path_for_tick(state, planet.planet_id)
        if path is not None:
            moved_planet = apply_planet_position(moved_planet, path[1])
        planets.append(moved_planet)

    return tuple(planets)


def _apply_arrival_combat_to_planets(
    planets: tuple[Planet, ...],
    arrivals: dict[int, list[Fleet]],
) -> tuple[Planet, ...]:
    resolved_planets: list[Planet] = []

    for planet in planets:
        arriving_fleets = arrivals.get(planet.planet_id)
        if not arriving_fleets:
            resolved_planets.append(planet)
            continue

        combat_result = resolve_planet_combat(planet, tuple(arriving_fleets))
        resolved_planets.append(apply_planet_combat_result(planet, combat_result))

    return tuple(resolved_planets)


def _expired_comet_planet_ids_after_tick(state: GameState) -> frozenset[int]:
    expired_planet_ids: set[int] = set()

    for group in state.comets:
        if group.path_index is None:
            continue
        next_path_index = group.path_index + 1
        for slot, planet_id in enumerate(group.planet_ids):
            if slot >= len(group.paths):
                continue
            if next_path_index >= len(group.paths[slot]):
                expired_planet_ids.add(planet_id)

    return frozenset(expired_planet_ids)


def _move_fleet_one_tick(fleet: Fleet) -> Fleet:
    new_x, new_y = fleet_path_for_tick(fleet)[1]
    return Fleet(
        fleet_id=fleet.fleet_id,
        owner=fleet.owner,
        x=new_x,
        y=new_y,
        angle=fleet.angle,
        from_planet_id=fleet.from_planet_id,
        ships=fleet.ships,
        raw=(
            fleet.fleet_id,
            fleet.owner,
            new_x,
            new_y,
            fleet.angle,
            fleet.from_planet_id,
            fleet.ships,
        ),
    )


def _planet_with(
    planet: Planet,
    *,
    owner: int | None = None,
    x: float | None = None,
    y: float | None = None,
    ships: int | None = None,
) -> Planet:
    next_owner = planet.owner if owner is None else owner
    next_x = planet.x if x is None else x
    next_y = planet.y if y is None else y
    next_ships = planet.ships if ships is None else ships
    return Planet(
        planet_id=planet.planet_id,
        owner=next_owner,
        x=next_x,
        y=next_y,
        radius=planet.radius,
        ships=next_ships,
        production=planet.production,
        is_comet=planet.is_comet,
        initial_position=planet.initial_position,
        raw=(
            planet.planet_id,
            next_owner,
            next_x,
            next_y,
            planet.radius,
            next_ships,
            planet.production,
        ),
    )


def _validate_tick_count(dt: int) -> None:
    if isinstance(dt, bool) or not isinstance(dt, int) or dt < 1:
        raise ValueError("dt must be an integer >= 1")


def _validate_single_tick(dt: int) -> None:
    if isinstance(dt, bool) or not isinstance(dt, int) or dt != 1:
        raise ValueError("next_game_state_after_tick supports only dt=1")


def _validate_rollout_ticks(ticks: int) -> None:
    if isinstance(ticks, bool) or not isinstance(ticks, int) or ticks < 0:
        raise ValueError("ticks must be an integer >= 0")


__all__ = (
    "FleetTickDelta",
    "OneTickEventSummary",
    "OneTickStateDelta",
    "PlanetTickDelta",
    "PlanetArrivalCombatEvent",
    "advance_comet_groups",
    "apply_planet_combat_result",
    "apply_planet_position",
    "fleet_tick_deltas",
    "fleet_removal_events_for_tick",
    "next_game_state_after_tick",
    "one_tick_event_summary",
    "one_tick_state_delta",
    "planet_tick_deltas",
    "planet_arrival_combat_events_for_tick",
    "planet_arrival_fleets_for_tick",
    "produce_planet",
    "simulate_ticks",
)
