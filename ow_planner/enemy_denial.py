"""Enemy-production denial opportunity fact extraction.

V1 Deterministic Leak Fix Cycle 5 exposes two-player ahead-state denial facts.
It does not generate missions, score options, select actions, run rollouts, or
mutate game state.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ow_sim.forecast import fleet_speed
from ow_sim.geometry import distance
from ow_sim.state import GameState, Planet


HIGH_VALUE_PRODUCTION_THRESHOLD = 3


@dataclass(frozen=True, slots=True)
class EnemyDenialTargetFacts:
    """Denial opportunity facts for one opponent-owned production planet."""

    player_id: int
    opponent_id: int
    target_planet_id: int
    target_owner: int
    target_ships: int
    target_production: int
    production_bearing: bool
    owned_source_count: int
    owned_source_capacity: int
    sufficient_source_count: int
    nearest_owned_source_id: int | None
    nearest_owned_source_ships: int | None
    nearest_owned_source_production: int | None
    distance_to_nearest_source: float | None
    eta_ticks_from_nearest_source: int | None
    player_production: int
    opponent_production: int
    player_ships: int
    opponent_ships: int
    player_ahead_by_production: bool
    player_ahead_by_ships: bool
    plausible_denial: bool
    high_value_denial: bool
    labels: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "distance_to_nearest_source": self.distance_to_nearest_source,
            "eta_ticks_from_nearest_source": self.eta_ticks_from_nearest_source,
            "high_value_denial": self.high_value_denial,
            "labels": list(self.labels),
            "nearest_owned_source_id": self.nearest_owned_source_id,
            "nearest_owned_source_production": self.nearest_owned_source_production,
            "nearest_owned_source_ships": self.nearest_owned_source_ships,
            "opponent_id": self.opponent_id,
            "opponent_production": self.opponent_production,
            "opponent_ships": self.opponent_ships,
            "owned_source_capacity": self.owned_source_capacity,
            "owned_source_count": self.owned_source_count,
            "plausible_denial": self.plausible_denial,
            "player_ahead_by_production": self.player_ahead_by_production,
            "player_ahead_by_ships": self.player_ahead_by_ships,
            "player_id": self.player_id,
            "player_production": self.player_production,
            "player_ships": self.player_ships,
            "production_bearing": self.production_bearing,
            "sufficient_source_count": self.sufficient_source_count,
            "target_owner": self.target_owner,
            "target_planet_id": self.target_planet_id,
            "target_production": self.target_production,
            "target_ships": self.target_ships,
        }


@dataclass(frozen=True, slots=True)
class EnemyDenialOpportunityReport:
    """Aggregate enemy-production denial facts for a state."""

    player_id: int | None
    opponent_id: int | None = None
    target_facts: tuple[EnemyDenialTargetFacts, ...] = ()
    target_count: int = 0
    plausible_denial_count: int = 0
    high_value_denial_count: int = 0
    player_production: int = 0
    opponent_production: int = 0
    player_ships: int = 0
    opponent_ships: int = 0
    player_ahead_by_production: bool = False
    player_ahead_by_ships: bool = False
    labels: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "high_value_denial_count": self.high_value_denial_count,
            "labels": list(self.labels),
            "opponent_id": self.opponent_id,
            "opponent_production": self.opponent_production,
            "opponent_ships": self.opponent_ships,
            "plausible_denial_count": self.plausible_denial_count,
            "player_ahead_by_production": self.player_ahead_by_production,
            "player_ahead_by_ships": self.player_ahead_by_ships,
            "player_id": self.player_id,
            "player_production": self.player_production,
            "player_ships": self.player_ships,
            "target_count": self.target_count,
            "target_facts": [facts.to_dict() for facts in self.target_facts],
        }


def enemy_denial_opportunity_facts(state: GameState) -> EnemyDenialOpportunityReport:
    """Return deterministic enemy-production denial opportunity facts."""

    if not isinstance(state, GameState):
        raise ValueError("state must be a GameState")
    if state.player_id is None:
        return EnemyDenialOpportunityReport(
            player_id=None,
            labels=("missing_player_id",),
        )

    opponent_ids = tuple(
        sorted(
            {
                planet.owner
                for planet in state.planets
                if planet.owner not in (-1, state.player_id)
            }
        )
    )
    if not opponent_ids:
        return EnemyDenialOpportunityReport(
            player_id=state.player_id,
            labels=("missing_opponent_id",),
        )
    opponent_id = opponent_ids[0]
    player_planets = tuple(
        planet for planet in state.planets if planet.owner == state.player_id
    )
    opponent_planets = tuple(planet for planet in state.planets if planet.owner == opponent_id)
    player_production = sum(planet.production for planet in player_planets)
    opponent_production = sum(planet.production for planet in opponent_planets)
    player_ships = sum(planet.ships for planet in player_planets)
    opponent_ships = sum(planet.ships for planet in opponent_planets)
    player_ahead_by_production = player_production >= opponent_production
    player_ahead_by_ships = player_ships >= opponent_ships

    target_facts = tuple(
        _target_denial_facts(
            player_id=state.player_id,
            opponent_id=opponent_id,
            target=target,
            owned_sources=player_planets,
            player_production=player_production,
            opponent_production=opponent_production,
            player_ships=player_ships,
            opponent_ships=opponent_ships,
            player_ahead_by_production=player_ahead_by_production,
            player_ahead_by_ships=player_ahead_by_ships,
        )
        for target in sorted(
            (planet for planet in opponent_planets if planet.production > 0),
            key=lambda planet: (-planet.production, planet.ships, planet.planet_id),
        )
    )
    labels: list[str] = []
    if target_facts:
        labels.append("opponent_production_targets")
    if player_ahead_by_production or player_ahead_by_ships:
        labels.append("ahead_state")
    if any(facts.plausible_denial for facts in target_facts):
        labels.append("plausible_enemy_denial")
    if any(facts.high_value_denial for facts in target_facts):
        labels.append("high_value_enemy_denial")

    return EnemyDenialOpportunityReport(
        player_id=state.player_id,
        opponent_id=opponent_id,
        target_facts=target_facts,
        target_count=len(target_facts),
        plausible_denial_count=sum(
            1 for facts in target_facts if facts.plausible_denial
        ),
        high_value_denial_count=sum(
            1 for facts in target_facts if facts.high_value_denial
        ),
        player_production=player_production,
        opponent_production=opponent_production,
        player_ships=player_ships,
        opponent_ships=opponent_ships,
        player_ahead_by_production=player_ahead_by_production,
        player_ahead_by_ships=player_ahead_by_ships,
        labels=tuple(labels),
    )


def _target_denial_facts(
    *,
    player_id: int,
    opponent_id: int,
    target: Planet,
    owned_sources: tuple[Planet, ...],
    player_production: int,
    opponent_production: int,
    player_ships: int,
    opponent_ships: int,
    player_ahead_by_production: bool,
    player_ahead_by_ships: bool,
) -> EnemyDenialTargetFacts:
    owned_source_count = len(owned_sources)
    owned_source_capacity = sum(max(0, source.ships - 1) for source in owned_sources)
    sufficient_sources = tuple(
        source for source in owned_sources if max(0, source.ships - 1) > target.ships
    )
    nearest_source = _nearest_source(owned_sources, target)
    distance_to_nearest_source = None
    eta_ticks = None
    if nearest_source is not None:
        distance_to_nearest_source = round(
            distance(nearest_source.position, target.position),
            6,
        )
        eta_ticks = _eta_ticks_from_source(nearest_source, target)
    plausible_denial = target.production > 0 and bool(sufficient_sources)
    ahead_or_capacity = (
        player_ahead_by_production
        or player_ahead_by_ships
        or owned_source_capacity >= target.ships * 2
    )
    high_value_denial = (
        plausible_denial
        and target.production >= HIGH_VALUE_PRODUCTION_THRESHOLD
        and ahead_or_capacity
    )
    labels: list[str] = ["opponent_production_target"]
    if plausible_denial:
        labels.append("plausible_denial_target")
    if high_value_denial:
        labels.append("high_value_denial_opportunity")
    if player_ahead_by_production or player_ahead_by_ships:
        labels.append("ahead_state_denial")

    return EnemyDenialTargetFacts(
        player_id=player_id,
        opponent_id=opponent_id,
        target_planet_id=target.planet_id,
        target_owner=target.owner,
        target_ships=target.ships,
        target_production=target.production,
        production_bearing=target.production > 0,
        owned_source_count=owned_source_count,
        owned_source_capacity=owned_source_capacity,
        sufficient_source_count=len(sufficient_sources),
        nearest_owned_source_id=(
            None if nearest_source is None else nearest_source.planet_id
        ),
        nearest_owned_source_ships=None if nearest_source is None else nearest_source.ships,
        nearest_owned_source_production=(
            None if nearest_source is None else nearest_source.production
        ),
        distance_to_nearest_source=distance_to_nearest_source,
        eta_ticks_from_nearest_source=eta_ticks,
        player_production=player_production,
        opponent_production=opponent_production,
        player_ships=player_ships,
        opponent_ships=opponent_ships,
        player_ahead_by_production=player_ahead_by_production,
        player_ahead_by_ships=player_ahead_by_ships,
        plausible_denial=plausible_denial,
        high_value_denial=high_value_denial,
        labels=tuple(labels),
    )


def _nearest_source(
    owned_sources: tuple[Planet, ...],
    target: Planet,
) -> Planet | None:
    if not owned_sources:
        return None
    return min(
        owned_sources,
        key=lambda source: (
            distance(source.position, target.position),
            source.planet_id,
        ),
    )


def _eta_ticks_from_source(source: Planet, target: Planet) -> int:
    ships_to_send = max(1, target.ships + 1)
    travel_distance = max(0.0, distance(source.position, target.position) - target.radius)
    return int(math.ceil(travel_distance / fleet_speed(ships_to_send)))


__all__ = (
    "EnemyDenialOpportunityReport",
    "EnemyDenialTargetFacts",
    "HIGH_VALUE_PRODUCTION_THRESHOLD",
    "enemy_denial_opportunity_facts",
)
