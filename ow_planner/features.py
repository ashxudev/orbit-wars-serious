"""Planner board feature extraction.

Mission Generation Cycle 2 turns parsed simulator state into deterministic
facts for later mission generation. It does not generate missions, estimate
ships, score targets, simulate outcomes, or choose actions.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Iterable, Mapping, TypeVar

from ow_sim.geometry import distance
from ow_sim.state import Fleet, GameState, Planet, Point2D


NEUTRAL_OWNER = -1
"""Official neutral planet owner id."""


K = TypeVar("K")
V = TypeVar("V")


@dataclass(frozen=True, slots=True)
class OwnerTotals:
    """Ship and production totals for one owner id."""

    owner: int
    planet_ships: int = 0
    fleet_ships: int = 0
    production: int = 0

    @property
    def total_ships(self) -> int:
        """Return planet and fleet ships combined."""

        return self.planet_ships + self.fleet_ships


@dataclass(frozen=True, slots=True)
class PlanetFacts:
    """Factual metadata for a planet."""

    planet_id: int
    owner: int
    position: Point2D
    radius: float
    ships: int
    production: int
    is_comet: bool = False
    initial_position: Point2D | None = None


@dataclass(frozen=True, slots=True)
class PlanetDistance:
    """Distance from an owned source planet to a possible target planet."""

    source_planet_id: int
    target_planet_id: int
    distance: float
    target_owner: int
    target_ships: int
    target_production: int
    target_is_comet: bool = False


@dataclass(frozen=True, slots=True)
class NearestTarget:
    """Nearest factual target for a source planet."""

    source_planet_id: int
    target_planet_id: int
    distance: float
    target_owner: int
    target_ships: int
    target_production: int
    target_is_comet: bool = False


@dataclass(frozen=True, slots=True)
class BoardFeatures:
    """Immutable board facts extracted from a parsed game state."""

    player_id: int
    own_planets: tuple[Planet, ...]
    neutral_planets: tuple[Planet, ...]
    enemy_planets: tuple[Planet, ...]
    own_fleets: tuple[Fleet, ...]
    enemy_fleets: tuple[Fleet, ...]
    planet_by_id: Mapping[int, Planet]
    fleet_by_id: Mapping[int, Fleet]
    planet_facts_by_id: Mapping[int, PlanetFacts]
    own_planet_ship_total: int
    own_fleet_ship_total: int
    enemy_planet_ship_total: int
    enemy_fleet_ship_total: int
    neutral_planet_ship_total: int
    own_production_total: int
    enemy_production_total: int
    neutral_production_total: int
    owner_totals: tuple[OwnerTotals, ...]
    owner_totals_by_owner: Mapping[int, OwnerTotals]
    source_target_distances: tuple[PlanetDistance, ...]
    target_distances_by_source: Mapping[int, tuple[PlanetDistance, ...]]
    nearest_neutral_by_source: Mapping[int, NearestTarget]
    nearest_enemy_by_source: Mapping[int, NearestTarget]
    frontline_by_source: Mapping[int, NearestTarget]


def extract_board_features(
    state: GameState,
    player_id: int | None = None,
) -> BoardFeatures:
    """Extract deterministic planner facts from ``state``.

    The effective player id is resolved from explicit ``player_id`` first and
    then from ``state.player_id``. Returned collections are sorted by stable
    ids and use read-only mappings where lookup dictionaries are exposed.
    """

    effective_player_id = _effective_player_id(state, player_id)
    planets = tuple(sorted(state.planets, key=lambda planet: planet.planet_id))
    fleets = tuple(sorted(state.fleets, key=lambda fleet: fleet.fleet_id))

    own_planets = tuple(
        planet for planet in planets if planet.owner == effective_player_id
    )
    neutral_planets = tuple(
        planet for planet in planets if planet.owner == NEUTRAL_OWNER
    )
    enemy_planets = tuple(
        planet
        for planet in planets
        if planet.owner not in (effective_player_id, NEUTRAL_OWNER)
    )
    own_fleets = tuple(fleet for fleet in fleets if fleet.owner == effective_player_id)
    enemy_fleets = tuple(fleet for fleet in fleets if fleet.owner != effective_player_id)

    planet_by_id = _readonly_mapping(
        (planet.planet_id, planet)
        for planet in planets
    )
    fleet_by_id = _readonly_mapping(
        (fleet.fleet_id, fleet)
        for fleet in fleets
    )
    planet_facts_by_id = _readonly_mapping(
        (planet.planet_id, _planet_facts(planet))
        for planet in planets
    )

    owner_totals = _owner_totals(planets, fleets)
    owner_totals_by_owner = _readonly_mapping(
        (totals.owner, totals)
        for totals in owner_totals
    )
    candidate_targets = tuple(
        sorted(neutral_planets + enemy_planets, key=lambda planet: planet.planet_id)
    )
    source_target_distances = _source_target_distances(
        sources=own_planets,
        targets=candidate_targets,
    )
    target_distances_by_source = _distances_by_source(
        source_target_distances,
        sources=own_planets,
    )
    nearest_neutral_by_source = _nearest_targets(
        sources=own_planets,
        targets=neutral_planets,
    )
    nearest_enemy_by_source = _nearest_targets(
        sources=own_planets,
        targets=enemy_planets,
    )

    return BoardFeatures(
        player_id=effective_player_id,
        own_planets=own_planets,
        neutral_planets=neutral_planets,
        enemy_planets=enemy_planets,
        own_fleets=own_fleets,
        enemy_fleets=enemy_fleets,
        planet_by_id=planet_by_id,
        fleet_by_id=fleet_by_id,
        planet_facts_by_id=planet_facts_by_id,
        own_planet_ship_total=sum(planet.ships for planet in own_planets),
        own_fleet_ship_total=sum(fleet.ships for fleet in own_fleets),
        enemy_planet_ship_total=sum(planet.ships for planet in enemy_planets),
        enemy_fleet_ship_total=sum(fleet.ships for fleet in enemy_fleets),
        neutral_planet_ship_total=sum(planet.ships for planet in neutral_planets),
        own_production_total=sum(planet.production for planet in own_planets),
        enemy_production_total=sum(planet.production for planet in enemy_planets),
        neutral_production_total=sum(planet.production for planet in neutral_planets),
        owner_totals=owner_totals,
        owner_totals_by_owner=owner_totals_by_owner,
        source_target_distances=source_target_distances,
        target_distances_by_source=target_distances_by_source,
        nearest_neutral_by_source=nearest_neutral_by_source,
        nearest_enemy_by_source=nearest_enemy_by_source,
        frontline_by_source=nearest_enemy_by_source,
    )


def _effective_player_id(state: GameState, player_id: int | None) -> int:
    if player_id is not None:
        return _validate_player_id(player_id)
    if state.player_id is not None:
        return _validate_player_id(state.player_id)
    raise ValueError("player_id is required for board feature extraction")


def _validate_player_id(player_id: int) -> int:
    if isinstance(player_id, bool) or not isinstance(player_id, int):
        raise ValueError("player_id must be an integer")
    return player_id


def _planet_facts(planet: Planet) -> PlanetFacts:
    return PlanetFacts(
        planet_id=planet.planet_id,
        owner=planet.owner,
        position=planet.position,
        radius=planet.radius,
        ships=planet.ships,
        production=planet.production,
        is_comet=planet.is_comet,
        initial_position=planet.initial_position,
    )


def _owner_totals(
    planets: tuple[Planet, ...],
    fleets: tuple[Fleet, ...],
) -> tuple[OwnerTotals, ...]:
    owners = sorted({planet.owner for planet in planets} | {fleet.owner for fleet in fleets})
    totals = []
    for owner in owners:
        totals.append(
            OwnerTotals(
                owner=owner,
                planet_ships=sum(planet.ships for planet in planets if planet.owner == owner),
                fleet_ships=sum(fleet.ships for fleet in fleets if fleet.owner == owner),
                production=sum(
                    planet.production for planet in planets if planet.owner == owner
                ),
            )
        )
    return tuple(totals)


def _source_target_distances(
    *,
    sources: tuple[Planet, ...],
    targets: tuple[Planet, ...],
) -> tuple[PlanetDistance, ...]:
    return tuple(
        PlanetDistance(
            source_planet_id=source.planet_id,
            target_planet_id=target.planet_id,
            distance=distance(source.position, target.position),
            target_owner=target.owner,
            target_ships=target.ships,
            target_production=target.production,
            target_is_comet=target.is_comet,
        )
        for source in sources
        for target in targets
    )


def _distances_by_source(
    distances: tuple[PlanetDistance, ...],
    *,
    sources: tuple[Planet, ...],
) -> Mapping[int, tuple[PlanetDistance, ...]]:
    return _readonly_mapping(
        (
            source.planet_id,
            tuple(
                distance_fact
                for distance_fact in distances
                if distance_fact.source_planet_id == source.planet_id
            ),
        )
        for source in sources
    )


def _nearest_targets(
    *,
    sources: tuple[Planet, ...],
    targets: tuple[Planet, ...],
) -> Mapping[int, NearestTarget]:
    nearest = {}
    for source in sources:
        if not targets:
            continue
        target = min(
            targets,
            key=lambda candidate: (
                distance(source.position, candidate.position),
                candidate.planet_id,
            ),
        )
        nearest[source.planet_id] = NearestTarget(
            source_planet_id=source.planet_id,
            target_planet_id=target.planet_id,
            distance=distance(source.position, target.position),
            target_owner=target.owner,
            target_ships=target.ships,
            target_production=target.production,
            target_is_comet=target.is_comet,
        )
    return MappingProxyType(nearest)


def _readonly_mapping(items: Iterable[tuple[K, V]]) -> Mapping[K, V]:
    return MappingProxyType(dict(items))


__all__ = (
    "BoardFeatures",
    "NEUTRAL_OWNER",
    "NearestTarget",
    "OwnerTotals",
    "PlanetDistance",
    "PlanetFacts",
    "extract_board_features",
)
