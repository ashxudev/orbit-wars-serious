"""Deterministic four-player board and standing facts.

Strategy Modes Cycle 5 extracts 4-player board/rank/survival facts from the
current parsed game state. It does not generate missions, evaluate candidates,
score, model responses, build commitments, select, convert actions, or run
simulator rollouts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ow_sim.state import GameState

from .strategy_modes import (
    StrategyMode,
    StrategyModeFacts,
    strategy_mode_facts as detect_strategy_mode_facts,
)


@dataclass(frozen=True, slots=True)
class FourPlayerStandingFacts:
    """Current board standing facts for one active non-neutral player."""

    player_id: int
    planet_count: int = 0
    fleet_count: int = 0
    planet_ships: int = 0
    fleet_ships: int = 0
    total_ships: int = 0
    production: int = 0
    production_rank: int | None = None
    total_ship_rank: int | None = None
    planet_count_rank: int | None = None
    is_current_player: bool = False
    is_production_leader: bool = False
    is_total_ship_leader: bool = False


@dataclass(frozen=True, slots=True)
class FourPlayerBoardFacts:
    """Deterministic 4-player board/rank/survival context."""

    strategy_mode_facts: StrategyModeFacts | None = None
    is_four_player_mode: bool = False
    player_id: int | None = None
    active_player_ids: tuple[int, ...] = ()
    standings: tuple[FourPlayerStandingFacts, ...] = ()
    current_player_standing: FourPlayerStandingFacts | None = None
    production_leader_player_id: int | None = None
    total_ship_leader_player_id: int | None = None
    current_player_production_rank: int | None = None
    current_player_total_ship_rank: int | None = None
    current_player_is_production_leader: bool | None = None
    current_player_is_total_ship_leader: bool | None = None
    current_player_is_last_by_production: bool | None = None
    current_player_is_last_by_total_ships: bool | None = None
    production_deficit_to_leader: int | None = None
    total_ship_deficit_to_leader: int | None = None
    survival_pressure: bool | None = None
    notes: tuple[str, ...] = ()


def four_player_board_facts(
    state: GameState,
    strategy_mode_facts: StrategyModeFacts | None = None,
) -> FourPlayerBoardFacts:
    """Return deterministic 4-player board facts for ``state``."""

    mode_facts = strategy_mode_facts or detect_strategy_mode_facts(state)
    active_player_ids = tuple(
        sorted(player_id for player_id in mode_facts.active_player_ids if player_id >= 0)
    )
    notes: list[str] = []
    is_four_player_mode = mode_facts.mode is StrategyMode.FOUR_PLAYER
    if not is_four_player_mode:
        notes.append("not four-player mode")
    if mode_facts.player_id is None:
        notes.append("missing player id")
    if not active_player_ids:
        notes.append("missing active players")

    standing_base = tuple(
        _standing_base_for_player(state, player_id, mode_facts.player_id)
        for player_id in active_player_ids
    )
    production_ranks = _rank_by_value(
        (standing.player_id, standing.production) for standing in standing_base
    )
    total_ship_ranks = _rank_by_value(
        (standing.player_id, standing.total_ships) for standing in standing_base
    )
    planet_count_ranks = _rank_by_value(
        (standing.player_id, standing.planet_count) for standing in standing_base
    )
    standings = tuple(
        FourPlayerStandingFacts(
            player_id=standing.player_id,
            planet_count=standing.planet_count,
            fleet_count=standing.fleet_count,
            planet_ships=standing.planet_ships,
            fleet_ships=standing.fleet_ships,
            total_ships=standing.total_ships,
            production=standing.production,
            production_rank=production_ranks.get(standing.player_id),
            total_ship_rank=total_ship_ranks.get(standing.player_id),
            planet_count_rank=planet_count_ranks.get(standing.player_id),
            is_current_player=standing.is_current_player,
            is_production_leader=production_ranks.get(standing.player_id) == 1,
            is_total_ship_leader=total_ship_ranks.get(standing.player_id) == 1,
        )
        for standing in standing_base
    )

    production_leader = _leader_standing(standings, "production_rank")
    total_ship_leader = _leader_standing(standings, "total_ship_rank")
    current_player_standing = _current_player_standing(standings)
    if mode_facts.player_id is not None and current_player_standing is None:
        notes.append("current player not active")

    current_player_production_rank = (
        None
        if current_player_standing is None
        else current_player_standing.production_rank
    )
    current_player_total_ship_rank = (
        None
        if current_player_standing is None
        else current_player_standing.total_ship_rank
    )
    current_player_is_production_leader = (
        None
        if current_player_standing is None
        else current_player_standing.is_production_leader
    )
    current_player_is_total_ship_leader = (
        None
        if current_player_standing is None
        else current_player_standing.is_total_ship_leader
    )
    current_player_is_last_by_production = _is_last_rank(
        current_player_production_rank,
        standings,
    )
    current_player_is_last_by_total_ships = _is_last_rank(
        current_player_total_ship_rank,
        standings,
    )
    survival_pressure = (
        None
        if (
            current_player_is_last_by_production is None
            or current_player_is_last_by_total_ships is None
        )
        else (
            current_player_is_last_by_production
            or current_player_is_last_by_total_ships
        )
    )

    return FourPlayerBoardFacts(
        strategy_mode_facts=mode_facts,
        is_four_player_mode=is_four_player_mode,
        player_id=mode_facts.player_id,
        active_player_ids=active_player_ids,
        standings=standings,
        current_player_standing=current_player_standing,
        production_leader_player_id=(
            None if production_leader is None else production_leader.player_id
        ),
        total_ship_leader_player_id=(
            None if total_ship_leader is None else total_ship_leader.player_id
        ),
        current_player_production_rank=current_player_production_rank,
        current_player_total_ship_rank=current_player_total_ship_rank,
        current_player_is_production_leader=current_player_is_production_leader,
        current_player_is_total_ship_leader=current_player_is_total_ship_leader,
        current_player_is_last_by_production=current_player_is_last_by_production,
        current_player_is_last_by_total_ships=current_player_is_last_by_total_ships,
        production_deficit_to_leader=_deficit_to_leader(
            current_player_standing,
            production_leader,
            "production",
        ),
        total_ship_deficit_to_leader=_deficit_to_leader(
            current_player_standing,
            total_ship_leader,
            "total_ships",
        ),
        survival_pressure=survival_pressure,
        notes=tuple(notes),
    )


def _standing_base_for_player(
    state: GameState,
    player_id: int,
    current_player_id: int | None,
) -> FourPlayerStandingFacts:
    planets = tuple(planet for planet in state.planets if planet.owner == player_id)
    fleets = tuple(fleet for fleet in state.fleets if fleet.owner == player_id)
    planet_ships = sum(planet.ships for planet in planets)
    fleet_ships = sum(fleet.ships for fleet in fleets)
    return FourPlayerStandingFacts(
        player_id=player_id,
        planet_count=len(planets),
        fleet_count=len(fleets),
        planet_ships=planet_ships,
        fleet_ships=fleet_ships,
        total_ships=planet_ships + fleet_ships,
        production=sum(planet.production for planet in planets),
        is_current_player=player_id == current_player_id,
    )


def _rank_by_value(player_values: Iterable[tuple[int, int]]) -> dict[int, int]:
    sorted_values = sorted(player_values, key=lambda item: (-item[1], item[0]))
    return {player_id: index + 1 for index, (player_id, _value) in enumerate(sorted_values)}


def _leader_standing(
    standings: tuple[FourPlayerStandingFacts, ...],
    rank_field: str,
) -> FourPlayerStandingFacts | None:
    for standing in standings:
        if getattr(standing, rank_field) == 1:
            return standing
    return None


def _current_player_standing(
    standings: tuple[FourPlayerStandingFacts, ...],
) -> FourPlayerStandingFacts | None:
    for standing in standings:
        if standing.is_current_player:
            return standing
    return None


def _is_last_rank(
    rank: int | None,
    standings: tuple[FourPlayerStandingFacts, ...],
) -> bool | None:
    if rank is None or not standings:
        return None
    return rank == len(standings)


def _deficit_to_leader(
    current: FourPlayerStandingFacts | None,
    leader: FourPlayerStandingFacts | None,
    field_name: str,
) -> int | None:
    if current is None or leader is None:
        return None
    return max(0, getattr(leader, field_name) - getattr(current, field_name))


__all__ = (
    "FourPlayerBoardFacts",
    "FourPlayerStandingFacts",
    "four_player_board_facts",
)
