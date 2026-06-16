"""Planner action conversion helpers.

Mission Generation Cycle 1 converts typed planner launch candidates into
simulator launch orders and official Kaggle action payload rows. It does not
generate, score, rank, or simulate missions.
"""

from __future__ import annotations

import math
from typing import TypeAlias

from ow_sim.state import GameState, Planet
from ow_sim.whatif import LaunchOrder

from .candidates import LaunchCandidate, MissionCandidate


KaggleActionRow: TypeAlias = list[int | float]
"""Official Orbit Wars action row: ``[from_planet_id, angle, ships]``."""


def launch_candidate_to_order(
    state: GameState,
    launch: LaunchCandidate,
    player_id: int | None = None,
) -> LaunchOrder:
    """Convert one launch candidate to a validated simulator launch order."""

    remaining_ships = _source_ship_counts(state)
    return _launch_candidate_to_order_with_remaining(
        state=state,
        launch=launch,
        remaining_ships=remaining_ships,
        player_id=player_id,
    )


def launch_candidate_to_action(
    state: GameState,
    launch: LaunchCandidate,
    player_id: int | None = None,
) -> KaggleActionRow:
    """Convert one launch candidate to a Kaggle-compatible action row."""

    return _order_to_action_row(launch_candidate_to_order(state, launch, player_id))


def mission_candidate_to_orders(
    state: GameState,
    mission: MissionCandidate,
    player_id: int | None = None,
) -> tuple[LaunchOrder, ...]:
    """Convert mission launches to validated simulator launch orders."""

    remaining_ships = _source_ship_counts(state)
    orders: list[LaunchOrder] = []

    for launch in mission.launches:
        order = _launch_candidate_to_order_with_remaining(
            state=state,
            launch=launch,
            remaining_ships=remaining_ships,
            player_id=player_id,
        )
        remaining_ships[order.source_planet_id] -= order.ships
        orders.append(order)

    return tuple(orders)


def mission_candidate_to_actions(
    state: GameState,
    mission: MissionCandidate,
    player_id: int | None = None,
) -> list[KaggleActionRow]:
    """Convert mission launches to official Kaggle action payload rows."""

    return [
        _order_to_action_row(order)
        for order in mission_candidate_to_orders(state, mission, player_id)
    ]


def _launch_candidate_to_order_with_remaining(
    *,
    state: GameState,
    launch: LaunchCandidate,
    remaining_ships: dict[int, int],
    player_id: int | None,
) -> LaunchOrder:
    source_planet_id = _validate_int(launch.source_planet_id, "source_planet_id")
    angle = _validate_angle(launch.angle)
    ships = _validate_positive_ships(launch.ships)
    effective_player_id = _effective_player_id(state, launch, player_id)
    source = _source_planet_by_id(state, source_planet_id)

    if source.owner != effective_player_id:
        raise ValueError("source planet is not owned by player_id")
    if remaining_ships[source_planet_id] < ships:
        raise ValueError("source planet does not have enough ships")

    return LaunchOrder(
        source_planet_id=source_planet_id,
        angle=angle,
        ships=ships,
        player_id=effective_player_id,
    )


def _source_ship_counts(state: GameState) -> dict[int, int]:
    return {
        planet.planet_id: planet.ships
        for planet in state.planets
    }


def _source_planet_by_id(state: GameState, source_planet_id: int) -> Planet:
    for planet in state.planets:
        if planet.planet_id == source_planet_id:
            return planet
    raise ValueError(f"source planet {source_planet_id} was not found")


def _effective_player_id(
    state: GameState,
    launch: LaunchCandidate,
    explicit_player_id: int | None,
) -> int:
    if launch.player_id is not None:
        return _validate_int(launch.player_id, "player_id")
    if explicit_player_id is not None:
        return _validate_int(explicit_player_id, "player_id")
    if state.player_id is not None:
        return _validate_int(state.player_id, "player_id")
    raise ValueError("player_id is required for launch conversion")


def _validate_int(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer")
    return value


def _validate_positive_ships(value: object) -> int:
    ships = _validate_int(value, "ships")
    if ships <= 0:
        raise ValueError("ships must be > 0")
    return ships


def _validate_angle(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("angle must be a finite real number")
    angle = float(value)
    if not math.isfinite(angle):
        raise ValueError("angle must be a finite real number")
    return angle


def _order_to_action_row(order: LaunchOrder) -> KaggleActionRow:
    return [order.source_planet_id, order.angle, order.ships]


__all__ = (
    "KaggleActionRow",
    "launch_candidate_to_action",
    "launch_candidate_to_order",
    "mission_candidate_to_actions",
    "mission_candidate_to_orders",
)
