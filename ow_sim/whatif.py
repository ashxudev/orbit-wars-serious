"""Hypothetical launch insertion boundary.

Cycle 13 adds typed hypothetical launch insertion. It does not advance time,
process Kaggle action payloads, choose targets, score missions, branch
timelines, or add planner logic.

Cycle 14 adds a mechanical composition helper for launch insertion plus idle
rollout. It still does not rank, compare, or branch scenarios.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .forecast import launch_fleet
from .state import Fleet, GameState, Planet
from .timeline import simulate_ticks


@dataclass(frozen=True, slots=True)
class LaunchOrder:
    """Typed hypothetical launch from one source planet."""

    source_planet_id: int
    angle: float
    ships: int
    player_id: int | None = None


def apply_launch_orders(
    state: GameState,
    orders: Sequence[LaunchOrder],
    player_id: int | None = None,
) -> GameState:
    """Return a new state with hypothetical launch orders inserted.

    Launches are applied sequentially and do not advance time. Callers can
    compose the returned state with ``next_game_state_after_tick(...)`` or
    ``simulate_ticks(...)`` when they want production and movement.
    """

    order_tuple = tuple(orders)
    if not order_tuple:
        return state
    if state.next_fleet_id is None:
        raise ValueError("state.next_fleet_id is required to insert launches")

    planets = list(state.planets)
    fleets = list(state.fleets)
    next_fleet_id = state.next_fleet_id

    for order in order_tuple:
        effective_player_id = _effective_player_id(state, order, player_id)
        source_index = _source_planet_index(planets, order.source_planet_id)
        source = planets[source_index]

        new_fleet = launch_fleet(
            next_fleet_id=next_fleet_id,
            player_id=effective_player_id,
            source=source,
            angle=order.angle,
            ships=order.ships,
        )
        planets[source_index] = _planet_with_ships(source, source.ships - order.ships)
        fleets.append(new_fleet)
        next_fleet_id += 1

    return GameState(
        tick=state.tick,
        player_id=state.player_id,
        planets=tuple(planets),
        fleets=tuple(fleets),
        angular_velocity=state.angular_velocity,
        initial_planets=state.initial_planets,
        next_fleet_id=next_fleet_id,
        comet_planet_ids=state.comet_planet_ids,
        comets=state.comets,
        remaining_overage_time=state.remaining_overage_time,
        raw_observation=None,
    )


def simulate_launch_orders(
    state: GameState,
    orders: Sequence[LaunchOrder],
    ticks: int,
    player_id: int | None = None,
) -> GameState:
    """Return the state after inserting launches and rolling out idle ticks."""

    _validate_rollout_ticks(ticks)
    launched_state = apply_launch_orders(state, orders, player_id=player_id)
    return simulate_ticks(launched_state, ticks)


def _effective_player_id(
    state: GameState,
    order: LaunchOrder,
    default_player_id: int | None,
) -> int:
    if order.player_id is not None:
        return order.player_id
    if default_player_id is not None:
        return default_player_id
    if state.player_id is not None:
        return state.player_id
    raise ValueError("player_id is required for launch orders")


def _source_planet_index(planets: list[Planet], source_planet_id: int) -> int:
    for index, planet in enumerate(planets):
        if planet.planet_id == source_planet_id:
            return index
    raise ValueError(f"source planet {source_planet_id} was not found")


def _planet_with_ships(planet: Planet, ships: int) -> Planet:
    return Planet(
        planet_id=planet.planet_id,
        owner=planet.owner,
        x=planet.x,
        y=planet.y,
        radius=planet.radius,
        ships=ships,
        production=planet.production,
        is_comet=planet.is_comet,
        initial_position=planet.initial_position,
        raw=(
            planet.planet_id,
            planet.owner,
            planet.x,
            planet.y,
            planet.radius,
            ships,
            planet.production,
        ),
    )


def _validate_rollout_ticks(ticks: int) -> None:
    if isinstance(ticks, bool) or not isinstance(ticks, int) or ticks < 0:
        raise ValueError("ticks must be an integer >= 0")


__all__ = (
    "LaunchOrder",
    "apply_launch_orders",
    "simulate_launch_orders",
)
