"""Pure combat resolution query helpers for Orbit Wars planet arrivals.

Cycle 8 resolves the combat result for fleets that have already hit a planet.
It does not mutate game state, remove fleets, move planets, apply production,
or integrate with timeline simulation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .state import Fleet, Planet


@dataclass(frozen=True, slots=True)
class FleetCombatWinner:
    """Surviving incoming fleet force after owner-vs-owner fleet combat."""

    owner: int | None
    ships: int


@dataclass(frozen=True, slots=True)
class PlanetCombatResult:
    """Pure planet owner/ship result after applying surviving incoming force."""

    owner: int
    ships: int
    winner_owner: int | None = None
    winner_ships: int = 0


def fleet_ships_by_owner(fleets: Sequence[Fleet]) -> dict[int, int]:
    """Return incoming fleet ships summed by owner."""

    ships_by_owner: dict[int, int] = {}
    for fleet in fleets:
        ships_by_owner[fleet.owner] = ships_by_owner.get(fleet.owner, 0) + fleet.ships
    return ships_by_owner


def resolve_fleet_combat(fleets: Sequence[Fleet]) -> FleetCombatWinner:
    """Resolve combat between arriving fleet owners using official semantics."""

    ships_by_owner = fleet_ships_by_owner(fleets)
    if not ships_by_owner:
        return FleetCombatWinner(owner=None, ships=0)

    sorted_players = sorted(
        ships_by_owner.items(),
        key=lambda item: item[1],
        reverse=True,
    )
    top_owner, top_ships = sorted_players[0]

    if len(sorted_players) == 1:
        return FleetCombatWinner(owner=top_owner, ships=top_ships)

    second_ships = sorted_players[1][1]
    if top_ships == second_ships:
        return FleetCombatWinner(owner=None, ships=0)

    return FleetCombatWinner(owner=top_owner, ships=top_ships - second_ships)


def resolve_planet_combat(
    planet: Planet,
    fleets: Sequence[Fleet],
) -> PlanetCombatResult:
    """Resolve incoming fleet combat against ``planet`` without mutation."""

    winner = resolve_fleet_combat(fleets)
    if winner.owner is None or winner.ships <= 0:
        return PlanetCombatResult(
            owner=planet.owner,
            ships=planet.ships,
            winner_owner=winner.owner,
            winner_ships=winner.ships,
        )

    if planet.owner == winner.owner:
        return PlanetCombatResult(
            owner=planet.owner,
            ships=planet.ships + winner.ships,
            winner_owner=winner.owner,
            winner_ships=winner.ships,
        )

    remaining_ships = planet.ships - winner.ships
    if remaining_ships < 0:
        return PlanetCombatResult(
            owner=winner.owner,
            ships=abs(remaining_ships),
            winner_owner=winner.owner,
            winner_ships=winner.ships,
        )

    return PlanetCombatResult(
        owner=planet.owner,
        ships=remaining_ships,
        winner_owner=winner.owner,
        winner_ships=winner.ships,
    )


__all__ = (
    "FleetCombatWinner",
    "PlanetCombatResult",
    "fleet_ships_by_owner",
    "resolve_fleet_combat",
    "resolve_planet_combat",
)
