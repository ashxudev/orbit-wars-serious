"""Position forecasting.

Cycle 6 covers planet/comet position projection, existing-fleet straight-line
movement, pure launch spawning, point aiming, and distance-based ETA queries.
Collision handling, production, combat, timelines, and what-if behavior are
intentionally deferred.
"""

from __future__ import annotations

import math

from .constants import DEFAULT_MAX_FLEET_SPEED, SUN_CENTER
from .geometry import distance, is_orbiting_position
from .state import CometGroup, Fleet, GameState, Planet, Point2D


PlanetPath = tuple[Point2D, Point2D]
CometPath = tuple[Point2D, Point2D, bool]
FleetPath = tuple[Point2D, Point2D]


def is_orbiting_planet(planet: Planet) -> bool:
    """Return whether ``planet`` is classified as orbiting.

    The official engine classifies non-comet planet motion from the initial
    position: ``orbital_radius + planet_radius < ROTATION_RADIUS_LIMIT``. When
    the parsed planet lacks initial-position metadata, its current position is
    used only for classification.
    """

    position = planet.initial_position or planet.position
    return is_orbiting_position(position, planet.radius)


def planet_orbit_radius(initial_planet: Planet) -> float:
    """Return the orbital radius for an initial planet position."""

    return distance(initial_planet.position, SUN_CENTER)


def planet_initial_angle(initial_planet: Planet) -> float:
    """Return the initial angle around the sun for an initial planet."""

    return math.atan2(
        initial_planet.y - SUN_CENTER[1],
        initial_planet.x - SUN_CENTER[0],
    )


def planet_position_at_step(
    state: GameState,
    planet_id: int,
    step: int,
) -> Point2D | None:
    """Return a planet position at an observation step.

    Non-comet generated observations show step 0 at the initial position and
    step ``N`` for ``N > 0`` at the position computed by the official
    interpreter with angle offset ``angular_velocity * (N - 1)``. Comets are
    projected by advancing their current path index by ``step - state.step``.
    """

    if step < 0:
        raise ValueError("step must be >= 0")

    planet = _planet_by_id(state, planet_id)
    if planet is None:
        return None
    if planet.is_comet:
        if state.step is None:
            return None
        group_slot = comet_group_for_planet(state, planet_id)
        if group_slot is None:
            return None
        group, _ = group_slot
        if group.path_index is None:
            return None
        return comet_position_at_path_index(
            state,
            planet_id,
            group.path_index + (step - state.step),
        )

    initial_planet = _initial_planet_by_id(state, planet_id)
    if initial_planet is None:
        if is_orbiting_planet(planet):
            return None
        return planet.position

    if not is_orbiting_planet(initial_planet):
        return planet.position

    if state.angular_velocity is None:
        return None

    orbit_radius = planet_orbit_radius(initial_planet)
    initial_angle = planet_initial_angle(initial_planet)
    official_step_index = max(0, step - 1)
    current_angle = initial_angle + state.angular_velocity * official_step_index
    return (
        SUN_CENTER[0] + orbit_radius * math.cos(current_angle),
        SUN_CENTER[1] + orbit_radius * math.sin(current_angle),
    )


def planet_position_after_ticks(
    state: GameState,
    planet_id: int,
    dt: int,
) -> Point2D | None:
    """Return a planet position at ``state.step + dt``."""

    if state.step is None:
        return None
    return planet_position_at_step(state, planet_id, state.step + dt)


def planet_path_for_tick(
    state: GameState,
    planet_id: int,
    dt: int = 1,
) -> PlanetPath | CometPath | None:
    """Return old/new planet positions for one tick interval.

    ``dt=1`` returns the interval from ``state.step`` to ``state.step + 1``.
    More generally, the interval is ``state.step + dt - 1`` to
    ``state.step + dt``. Comet paths include a third boolean indicating whether
    the official interpreter would check swept collisions for that interval.
    """

    if dt < 1:
        raise ValueError("dt must be >= 1")
    if state.step is None:
        return None

    planet = _planet_by_id(state, planet_id)
    if planet is not None and planet.is_comet:
        return comet_path_for_tick(state, planet_id, dt)

    old_position = planet_position_at_step(state, planet_id, state.step + dt - 1)
    new_position = planet_position_at_step(state, planet_id, state.step + dt)
    if old_position is None or new_position is None:
        return None
    return (old_position, new_position)


def comet_group_for_planet(
    state: GameState,
    planet_id: int,
) -> tuple[CometGroup, int] | None:
    """Return the comet group and path slot for ``planet_id`` if available."""

    for group in state.comets:
        for slot, candidate_id in enumerate(group.planet_ids):
            if candidate_id == planet_id:
                if slot >= len(group.paths):
                    return None
                return (group, slot)
    return None


def comet_position_at_path_index(
    state: GameState,
    planet_id: int,
    path_index: int,
) -> Point2D | None:
    """Return comet position for an explicit path index.

    Out-of-range path indices represent pre-placement or expiry and return
    ``None`` rather than inventing a position.
    """

    group_slot = comet_group_for_planet(state, planet_id)
    if group_slot is None:
        return None

    group, slot = group_slot
    path = group.paths[slot]
    if path_index < 0 or path_index >= len(path):
        return None
    return path[path_index]


def comet_position_after_ticks(
    state: GameState,
    planet_id: int,
    dt: int,
) -> Point2D | None:
    """Return comet position after advancing the current path index by ``dt``."""

    group_slot = comet_group_for_planet(state, planet_id)
    if group_slot is None:
        return None

    group, _ = group_slot
    if group.path_index is None:
        return None
    return comet_position_at_path_index(state, planet_id, group.path_index + dt)


def comet_path_for_tick(
    state: GameState,
    planet_id: int,
    dt: int = 1,
) -> CometPath | None:
    """Return old/new comet positions and official collision-check flag.

    The official interpreter increments ``path_index`` once per tick. First
    placement moves from the off-board planet placeholder to ``path[0]`` and
    sets ``check_collision`` to false. Expiry keeps the comet at its last valid
    point for that tick and returns ``check_collision`` from the old position.
    """

    if dt < 1:
        raise ValueError("dt must be >= 1")

    planet = _planet_by_id(state, planet_id)
    if planet is None or not planet.is_comet:
        return None

    group_slot = comet_group_for_planet(state, planet_id)
    if group_slot is None:
        return None

    group, slot = group_slot
    if group.path_index is None:
        return None

    path = group.paths[slot]
    old_index = group.path_index + dt - 1
    new_index = group.path_index + dt

    if old_index == group.path_index:
        old_position = planet.position
    elif 0 <= old_index < len(path):
        old_position = path[old_index]
    else:
        return None

    check_collision = old_position[0] >= 0.0

    if 0 <= new_index < len(path):
        return (old_position, path[new_index], check_collision)
    if new_index >= len(path) and 0 <= old_index < len(path):
        return (old_position, old_position, check_collision)
    return None


def fleet_speed(
    ships: int,
    max_speed: float = DEFAULT_MAX_FLEET_SPEED,
) -> float:
    """Return the official fleet speed for a positive ship count."""

    _validate_positive_ship_count(ships)
    speed = 1.0 + (max_speed - 1.0) * (
        math.log(ships) / math.log(1000)
    ) ** 1.5
    return min(speed, max_speed)


def fleet_step_delta(
    angle: float,
    ships: int,
    max_speed: float = DEFAULT_MAX_FLEET_SPEED,
) -> Point2D:
    """Return the official one-tick x/y delta for a fleet heading."""

    speed = fleet_speed(ships, max_speed)
    return (math.cos(angle) * speed, math.sin(angle) * speed)


def fleet_position_after_ticks(
    fleet: Fleet,
    dt: int,
    max_speed: float = DEFAULT_MAX_FLEET_SPEED,
) -> Point2D:
    """Return straight-line fleet position after ``dt`` movement ticks."""

    _validate_tick_count(dt, minimum=0, field_name="dt")
    dx, dy = fleet_step_delta(fleet.angle, fleet.ships, max_speed)
    return (fleet.x + dx * dt, fleet.y + dy * dt)


def fleet_path_for_tick(
    fleet: Fleet,
    dt: int = 1,
    max_speed: float = DEFAULT_MAX_FLEET_SPEED,
) -> FleetPath:
    """Return old/new fleet positions for the tick interval ``dt - 1`` to ``dt``."""

    _validate_tick_count(dt, minimum=1, field_name="dt")
    return (
        fleet_position_after_ticks(fleet, dt - 1, max_speed),
        fleet_position_after_ticks(fleet, dt, max_speed),
    )


def can_launch_from_planet(source: Planet, player_id: int, ships: int) -> bool:
    """Return whether a launch satisfies the official core legality checks."""

    if isinstance(ships, bool) or not isinstance(ships, int):
        raise ValueError("ships must be an integer")
    return source.owner == player_id and ships > 0 and source.ships >= ships


def launch_spawn_position(source: Planet, angle: float) -> Point2D:
    """Return the official fleet spawn position just outside ``source``."""

    offset = source.radius + 0.1
    return (
        source.x + math.cos(angle) * offset,
        source.y + math.sin(angle) * offset,
    )


def launch_fleet(
    next_fleet_id: int,
    player_id: int,
    source: Planet,
    angle: float,
    ships: int,
) -> Fleet:
    """Return a spawned fleet row without mutating source or game state."""

    _validate_positive_ship_count(ships)
    if not can_launch_from_planet(source, player_id, ships):
        raise ValueError("launch must be from an owned planet with enough ships")

    x, y = launch_spawn_position(source, angle)
    raw = (
        next_fleet_id,
        player_id,
        x,
        y,
        angle,
        source.planet_id,
        ships,
    )
    return Fleet(
        fleet_id=next_fleet_id,
        owner=player_id,
        x=x,
        y=y,
        angle=angle,
        from_planet_id=source.planet_id,
        ships=ships,
        raw=raw,
    )


def angle_to_point(origin: Point2D, target: Point2D) -> float:
    """Return the heading angle from ``origin`` to ``target``."""

    dx = target[0] - origin[0]
    dy = target[1] - origin[1]
    if dx == 0.0 and dy == 0.0:
        raise ValueError("origin and target must be different points")
    return math.atan2(dy, dx)


def angle_from_planet_to_point(source: Planet, target: Point2D) -> float:
    """Return the heading angle from a planet center to ``target``."""

    return angle_to_point(source.position, target)


def fleet_ticks_to_reach_distance(
    distance_value: float,
    ships: int,
    max_speed: float = DEFAULT_MAX_FLEET_SPEED,
) -> int:
    """Return whole movement ticks needed to cover a straight-line distance."""

    _validate_nonnegative_number(distance_value, "distance_value")
    return math.ceil(distance_value / fleet_speed(ships, max_speed))


def fleet_ticks_to_reach_point(
    start: Point2D,
    target: Point2D,
    ships: int,
    max_speed: float = DEFAULT_MAX_FLEET_SPEED,
) -> int:
    """Return distance-based ticks needed to reach ``target`` from ``start``."""

    return fleet_ticks_to_reach_distance(distance(start, target), ships, max_speed)


def fleet_ticks_to_reach_circle(
    start: Point2D,
    center: Point2D,
    radius: float,
    ships: int,
    max_speed: float = DEFAULT_MAX_FLEET_SPEED,
) -> int:
    """Return distance-based ticks needed to reach a circle boundary."""

    _validate_nonnegative_number(radius, "radius")
    distance_to_boundary = max(0.0, distance(start, center) - radius)
    return fleet_ticks_to_reach_distance(distance_to_boundary, ships, max_speed)


def _planet_by_id(state: GameState, planet_id: int) -> Planet | None:
    for planet in state.planets:
        if planet.planet_id == planet_id:
            return planet
    return None


def _initial_planet_by_id(state: GameState, planet_id: int) -> Planet | None:
    for planet in state.initial_planets:
        if planet.planet_id == planet_id:
            return planet
    return None


def _validate_positive_ship_count(ships: int) -> None:
    if isinstance(ships, bool) or not isinstance(ships, int) or ships <= 0:
        raise ValueError("ships must be a positive integer")


def _validate_tick_count(dt: int, *, minimum: int, field_name: str) -> None:
    if isinstance(dt, bool) or not isinstance(dt, int) or dt < minimum:
        raise ValueError(f"{field_name} must be an integer >= {minimum}")


def _validate_nonnegative_number(value: float, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0.0:
        raise ValueError(f"{field_name} must be a nonnegative number")


__all__ = (
    "angle_from_planet_to_point",
    "angle_to_point",
    "can_launch_from_planet",
    "comet_group_for_planet",
    "comet_path_for_tick",
    "comet_position_after_ticks",
    "comet_position_at_path_index",
    "fleet_path_for_tick",
    "fleet_position_after_ticks",
    "fleet_speed",
    "fleet_step_delta",
    "fleet_ticks_to_reach_circle",
    "fleet_ticks_to_reach_distance",
    "fleet_ticks_to_reach_point",
    "is_orbiting_planet",
    "launch_fleet",
    "launch_spawn_position",
    "planet_initial_angle",
    "planet_orbit_radius",
    "planet_path_for_tick",
    "planet_position_after_ticks",
    "planet_position_at_step",
)
