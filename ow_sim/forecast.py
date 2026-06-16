"""Non-comet planet position forecasting.

Cycle 3 is limited to pure planet-motion helpers for non-comet planets. Comet
motion, fleet movement, production, combat, timelines, and what-if behavior are
intentionally deferred.
"""

from __future__ import annotations

import math

from .constants import SUN_CENTER
from .geometry import distance, is_orbiting_position
from .state import GameState, Planet, Point2D


PlanetPath = tuple[Point2D, Point2D]


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
    """Return a non-comet planet position at an observation step.

    Generated observations show step 0 at the initial position and step ``N``
    for ``N > 0`` at the position computed by the official interpreter with
    angle offset ``angular_velocity * (N - 1)``. Comets return ``None`` because
    their path-index motion is deferred to Cycle 4.
    """

    if step < 0:
        raise ValueError("step must be >= 0")

    planet = _planet_by_id(state, planet_id)
    if planet is None or planet.is_comet:
        return None

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
    """Return a non-comet planet position at ``state.step + dt``."""

    if state.step is None:
        return None
    return planet_position_at_step(state, planet_id, state.step + dt)


def planet_path_for_tick(
    state: GameState,
    planet_id: int,
    dt: int = 1,
) -> PlanetPath | None:
    """Return old/new non-comet planet positions for one tick interval.

    ``dt=1`` returns the interval from ``state.step`` to ``state.step + 1``.
    More generally, the interval is ``state.step + dt - 1`` to
    ``state.step + dt``. Comets and unprojectable planets return ``None``.
    """

    if dt < 1:
        raise ValueError("dt must be >= 1")
    if state.step is None:
        return None

    old_position = planet_position_at_step(state, planet_id, state.step + dt - 1)
    new_position = planet_position_at_step(state, planet_id, state.step + dt)
    if old_position is None or new_position is None:
        return None
    return (old_position, new_position)


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


__all__ = (
    "is_orbiting_planet",
    "planet_initial_angle",
    "planet_orbit_radius",
    "planet_path_for_tick",
    "planet_position_after_ticks",
    "planet_position_at_step",
)
