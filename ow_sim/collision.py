"""Pure fleet collision and removal query helpers for Orbit Wars.

These helpers answer one-tick collision/removal questions only. They do not
mutate fleets, planets, game state, raw observations, or resolve combat.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .constants import BOARD_MAX, BOARD_MIN
from .forecast import fleet_path_for_tick, planet_path_for_tick
from .geometry import segment_hits_sun, swept_circle_intersects
from .state import Fleet, GameState, Planet, Point2D


class FleetRemovalReason(str, Enum):
    """Official one-tick fleet removal reason."""

    PLANET = "planet"
    BOUNDS = "bounds"
    SUN = "sun"


@dataclass(frozen=True, slots=True)
class FleetRemovalEvent:
    """Pure description of why a fleet would be removed during one tick."""

    reason: FleetRemovalReason
    fleet_id: int
    planet_id: int | None
    old_position: Point2D
    new_position: Point2D


def fleet_hits_planet_path(
    fleet_old: Point2D,
    fleet_new: Point2D,
    planet_old: Point2D,
    planet_new: Point2D,
    planet_radius: float,
) -> bool:
    """Return whether a fleet segment hits a moving planet circle."""

    return swept_circle_intersects(
        fleet_old,
        fleet_new,
        planet_old,
        planet_new,
        planet_radius,
    )


def fleet_hits_planet_on_tick(
    state: GameState,
    fleet: Fleet,
    planet: Planet,
    dt: int = 1,
) -> bool:
    """Return whether ``fleet`` hits ``planet`` during a tick interval."""

    fleet_old, fleet_new = fleet_path_for_tick(fleet, dt)
    planet_path = planet_path_for_tick(state, planet.planet_id, dt)
    if planet_path is None:
        return False

    if len(planet_path) == 3:
        planet_old, planet_new, check_collision = planet_path
        if not check_collision:
            return False
    else:
        planet_old, planet_new = planet_path

    return fleet_hits_planet_path(
        fleet_old,
        fleet_new,
        planet_old,
        planet_new,
        planet.radius,
    )


def first_planet_hit_for_fleet_tick(
    state: GameState,
    fleet: Fleet,
    dt: int = 1,
) -> int | None:
    """Return the first hit planet id in official ``state.planets`` order."""

    for planet in state.planets:
        if fleet_hits_planet_on_tick(state, fleet, planet, dt):
            return planet.planet_id
    return None


def fleet_is_out_of_bounds_after_tick(fleet: Fleet, dt: int = 1) -> bool:
    """Return whether a fleet's new position after movement is out of bounds."""

    _, (x, y) = fleet_path_for_tick(fleet, dt)
    return not (BOARD_MIN <= x <= BOARD_MAX and BOARD_MIN <= y <= BOARD_MAX)


def fleet_hits_sun_on_tick(fleet: Fleet, dt: int = 1) -> bool:
    """Return whether a fleet segment enters the sun radius on this tick."""

    old_position, new_position = fleet_path_for_tick(fleet, dt)
    return segment_hits_sun(old_position, new_position)


def fleet_removal_event_for_tick(
    state: GameState,
    fleet: Fleet,
    dt: int = 1,
) -> FleetRemovalEvent | None:
    """Return the official-priority one-tick removal event for ``fleet``."""

    old_position, new_position = fleet_path_for_tick(fleet, dt)

    planet_id = first_planet_hit_for_fleet_tick(state, fleet, dt)
    if planet_id is not None:
        return FleetRemovalEvent(
            reason=FleetRemovalReason.PLANET,
            fleet_id=fleet.fleet_id,
            planet_id=planet_id,
            old_position=old_position,
            new_position=new_position,
        )

    if not (
        BOARD_MIN <= new_position[0] <= BOARD_MAX
        and BOARD_MIN <= new_position[1] <= BOARD_MAX
    ):
        return FleetRemovalEvent(
            reason=FleetRemovalReason.BOUNDS,
            fleet_id=fleet.fleet_id,
            planet_id=None,
            old_position=old_position,
            new_position=new_position,
        )

    if segment_hits_sun(old_position, new_position):
        return FleetRemovalEvent(
            reason=FleetRemovalReason.SUN,
            fleet_id=fleet.fleet_id,
            planet_id=None,
            old_position=old_position,
            new_position=new_position,
        )

    return None


__all__ = (
    "FleetRemovalEvent",
    "FleetRemovalReason",
    "first_planet_hit_for_fleet_tick",
    "fleet_hits_planet_on_tick",
    "fleet_hits_planet_path",
    "fleet_hits_sun_on_tick",
    "fleet_is_out_of_bounds_after_tick",
    "fleet_removal_event_for_tick",
)
