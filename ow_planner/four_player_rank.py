"""Four-player rank, leader-pressure, and swing-risk fact extraction.

V1 Deterministic Leak Fix Cycle 9 exposes deterministic observability facts for
four-player rank context. It does not generate missions, evaluate candidates,
score, build commitments, select actions, convert actions, run rollouts, or
mutate game state.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from ow_sim.forecast import fleet_speed
from ow_sim.geometry import distance
from ow_sim.state import GameState, Planet


HIGH_SWING_PRODUCTION_THRESHOLD = 3
RANK_PRESERVATION_PRODUCTION_MARGIN = 3
UNDEREXPANDED_PRODUCTION_RANK_THRESHOLD = 3
UNDEREXPANDED_PLANET_RANK_THRESHOLD = 3


@dataclass(frozen=True, slots=True)
class FourPlayerRankStandingFacts:
    """Current rank facts for one active non-neutral player."""

    player_id: int
    planet_count: int = 0
    production: int = 0
    planet_ships: int = 0
    fleet_count: int = 0
    fleet_ships: int = 0
    total_ships: int = 0
    planet_count_rank: int | None = None
    production_rank: int | None = None
    total_ship_rank: int | None = None
    is_current_player: bool = False
    is_planet_count_leader: bool = False
    is_production_leader: bool = False
    is_total_ship_leader: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "fleet_count": self.fleet_count,
            "fleet_ships": self.fleet_ships,
            "is_current_player": self.is_current_player,
            "is_planet_count_leader": self.is_planet_count_leader,
            "is_production_leader": self.is_production_leader,
            "is_total_ship_leader": self.is_total_ship_leader,
            "planet_count": self.planet_count,
            "planet_count_rank": self.planet_count_rank,
            "planet_ships": self.planet_ships,
            "player_id": self.player_id,
            "production": self.production,
            "production_rank": self.production_rank,
            "total_ship_rank": self.total_ship_rank,
            "total_ships": self.total_ships,
        }


@dataclass(frozen=True, slots=True)
class FourPlayerSwingTargetFacts:
    """Nearest-source facts for one non-owned production swing target."""

    target_planet_id: int
    target_owner: int
    target_ships: int
    target_production: int
    production_bearing: bool
    target_owner_is_leader: bool
    nearest_owned_source_id: int | None
    nearest_owned_source_ships: int | None
    distance_to_nearest_source: float | None
    eta_ticks_from_nearest_source: int | None
    plausible_with_nearest_source: bool
    high_value_swing_target: bool
    labels: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "distance_to_nearest_source": self.distance_to_nearest_source,
            "eta_ticks_from_nearest_source": self.eta_ticks_from_nearest_source,
            "high_value_swing_target": self.high_value_swing_target,
            "labels": list(self.labels),
            "nearest_owned_source_id": self.nearest_owned_source_id,
            "nearest_owned_source_ships": self.nearest_owned_source_ships,
            "plausible_with_nearest_source": self.plausible_with_nearest_source,
            "production_bearing": self.production_bearing,
            "target_owner": self.target_owner,
            "target_owner_is_leader": self.target_owner_is_leader,
            "target_planet_id": self.target_planet_id,
            "target_production": self.target_production,
            "target_ships": self.target_ships,
        }


@dataclass(frozen=True, slots=True)
class FourPlayerRankReport:
    """Aggregate four-player rank, leader-pressure, and swing facts."""

    player_id: int | None
    declared_player_count: int | None = None
    active_player_ids: tuple[int, ...] = ()
    active_opponent_ids: tuple[int, ...] = ()
    active_player_count: int = 0
    is_declared_four_player_context: bool = False
    is_active_four_player_context: bool = False
    is_four_player_context: bool = False
    standings: tuple[FourPlayerRankStandingFacts, ...] = ()
    current_player_standing: FourPlayerRankStandingFacts | None = None
    planet_count_leader_ids: tuple[int, ...] = ()
    production_leader_ids: tuple[int, ...] = ()
    total_ship_leader_ids: tuple[int, ...] = ()
    current_player_planet_count_rank: int | None = None
    current_player_production_rank: int | None = None
    current_player_total_ship_rank: int | None = None
    planet_count_delta_to_leader: int | None = None
    production_delta_to_leader: int | None = None
    total_ship_delta_to_leader: int | None = None
    production_rival_id: int | None = None
    production_delta_to_next_higher_rival: int | None = None
    production_delta_to_next_lower_rival: int | None = None
    total_ship_rival_id: int | None = None
    total_ship_delta_to_next_higher_rival: int | None = None
    total_ship_delta_to_next_lower_rival: int | None = None
    swing_target_facts: tuple[FourPlayerSwingTargetFacts, ...] = ()
    swing_target_count: int = 0
    plausible_swing_target_count: int = 0
    high_value_swing_target_count: int = 0
    leader_owned_swing_target_count: int = 0
    nearest_swing_target_id: int | None = None
    leader_pressure: bool = False
    rank_preservation_pressure: bool = False
    underexpanded_trailing: bool = False
    swing_opportunity: bool = False
    labels: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "active_opponent_ids": list(self.active_opponent_ids),
            "active_player_count": self.active_player_count,
            "active_player_ids": list(self.active_player_ids),
            "current_player_planet_count_rank": self.current_player_planet_count_rank,
            "current_player_production_rank": self.current_player_production_rank,
            "current_player_standing": (
                None
                if self.current_player_standing is None
                else self.current_player_standing.to_dict()
            ),
            "current_player_total_ship_rank": self.current_player_total_ship_rank,
            "declared_player_count": self.declared_player_count,
            "high_value_swing_target_count": self.high_value_swing_target_count,
            "is_active_four_player_context": self.is_active_four_player_context,
            "is_declared_four_player_context": self.is_declared_four_player_context,
            "is_four_player_context": self.is_four_player_context,
            "labels": list(self.labels),
            "leader_owned_swing_target_count": self.leader_owned_swing_target_count,
            "leader_pressure": self.leader_pressure,
            "nearest_swing_target_id": self.nearest_swing_target_id,
            "planet_count_delta_to_leader": self.planet_count_delta_to_leader,
            "planet_count_leader_ids": list(self.planet_count_leader_ids),
            "player_id": self.player_id,
            "plausible_swing_target_count": self.plausible_swing_target_count,
            "production_delta_to_leader": self.production_delta_to_leader,
            "production_delta_to_next_higher_rival": (
                self.production_delta_to_next_higher_rival
            ),
            "production_delta_to_next_lower_rival": (
                self.production_delta_to_next_lower_rival
            ),
            "production_leader_ids": list(self.production_leader_ids),
            "production_rival_id": self.production_rival_id,
            "rank_preservation_pressure": self.rank_preservation_pressure,
            "standings": [standing.to_dict() for standing in self.standings],
            "swing_opportunity": self.swing_opportunity,
            "swing_target_count": self.swing_target_count,
            "swing_target_facts": [
                target_facts.to_dict() for target_facts in self.swing_target_facts
            ],
            "total_ship_delta_to_leader": self.total_ship_delta_to_leader,
            "total_ship_delta_to_next_higher_rival": (
                self.total_ship_delta_to_next_higher_rival
            ),
            "total_ship_delta_to_next_lower_rival": (
                self.total_ship_delta_to_next_lower_rival
            ),
            "total_ship_leader_ids": list(self.total_ship_leader_ids),
            "total_ship_rival_id": self.total_ship_rival_id,
            "underexpanded_trailing": self.underexpanded_trailing,
        }


def four_player_rank_facts(
    state: GameState,
    *,
    declared_player_count: int | None = None,
) -> FourPlayerRankReport:
    """Return deterministic four-player rank, leader-pressure, and swing facts."""

    if not isinstance(state, GameState):
        raise ValueError("state must be a GameState")
    if declared_player_count is not None and (
        isinstance(declared_player_count, bool)
        or not isinstance(declared_player_count, int)
        or declared_player_count <= 0
    ):
        raise ValueError("declared_player_count must be None or a positive integer")

    active_player_ids = _active_player_ids(state)
    active_opponent_ids = tuple(
        player
        for player in active_player_ids
        if state.player_id is not None and player != state.player_id
    )
    is_declared_four_player_context = declared_player_count == 4
    is_active_four_player_context = len(active_player_ids) == 4
    is_four_player_context = (
        is_declared_four_player_context or is_active_four_player_context
    )

    standing_base = tuple(
        _standing_base_for_player(state, player_id)
        for player_id in active_player_ids
    )
    planet_count_ranks = _rank_by_value(
        (standing.player_id, standing.planet_count) for standing in standing_base
    )
    production_ranks = _rank_by_value(
        (standing.player_id, standing.production) for standing in standing_base
    )
    total_ship_ranks = _rank_by_value(
        (standing.player_id, standing.total_ships) for standing in standing_base
    )
    planet_count_leader_ids = _leader_ids(standing_base, "planet_count")
    production_leader_ids = _leader_ids(standing_base, "production")
    total_ship_leader_ids = _leader_ids(standing_base, "total_ships")
    standings = tuple(
        FourPlayerRankStandingFacts(
            player_id=standing.player_id,
            planet_count=standing.planet_count,
            production=standing.production,
            planet_ships=standing.planet_ships,
            fleet_count=standing.fleet_count,
            fleet_ships=standing.fleet_ships,
            total_ships=standing.total_ships,
            planet_count_rank=planet_count_ranks.get(standing.player_id),
            production_rank=production_ranks.get(standing.player_id),
            total_ship_rank=total_ship_ranks.get(standing.player_id),
            is_current_player=standing.player_id == state.player_id,
            is_planet_count_leader=standing.player_id in planet_count_leader_ids,
            is_production_leader=standing.player_id in production_leader_ids,
            is_total_ship_leader=standing.player_id in total_ship_leader_ids,
        )
        for standing in standing_base
    )
    current = _current_player_standing(standings)
    swing_target_facts = tuple(
        _swing_target_facts(
            target=target,
            owned_sources=tuple(
                planet for planet in state.planets if planet.owner == state.player_id
            ),
            production_leader_ids=production_leader_ids,
        )
        for target in sorted(
            (
                planet
                for planet in state.planets
                if _is_swing_target(planet, state.player_id)
            ),
            key=lambda planet: (
                0 if planet.owner in production_leader_ids else 1,
                -planet.production,
                planet.ships,
                planet.planet_id,
            ),
        )
    )
    nearest_swing_target = _nearest_swing_target(swing_target_facts)
    production_delta_to_leader = _delta_to_leader(
        current,
        standings,
        "production",
    )
    total_ship_delta_to_leader = _delta_to_leader(
        current,
        standings,
        "total_ships",
    )
    planet_count_delta_to_leader = _delta_to_leader(
        current,
        standings,
        "planet_count",
    )
    production_rival = _next_higher_rival(current, standings, "production")
    total_ship_rival = _next_higher_rival(current, standings, "total_ships")
    production_trailing = _next_lower_delta(current, standings, "production")
    total_ship_trailing = _next_lower_delta(current, standings, "total_ships")
    leader_pressure = (
        is_four_player_context
        and current is not None
        and production_delta_to_leader is not None
        and production_delta_to_leader > 0
    )
    rank_preservation_pressure = (
        is_four_player_context
        and current is not None
        and current.production_rank is not None
        and current.production_rank <= 2
        and production_trailing is not None
        and production_trailing <= RANK_PRESERVATION_PRODUCTION_MARGIN
    )
    underexpanded_trailing = (
        is_four_player_context
        and current is not None
        and (
            (
                current.production_rank is not None
                and current.production_rank >= UNDEREXPANDED_PRODUCTION_RANK_THRESHOLD
            )
            or (
                current.planet_count_rank is not None
                and current.planet_count_rank >= UNDEREXPANDED_PLANET_RANK_THRESHOLD
            )
            or (
                production_delta_to_leader is not None
                and production_delta_to_leader >= max(6, current.production)
            )
        )
    )
    swing_opportunity = is_four_player_context and any(
        facts.high_value_swing_target for facts in swing_target_facts
    )
    labels = _labels(
        is_declared_four_player_context=is_declared_four_player_context,
        is_active_four_player_context=is_active_four_player_context,
        active_player_count=len(active_player_ids),
        leader_pressure=leader_pressure,
        rank_preservation_pressure=rank_preservation_pressure,
        underexpanded_trailing=underexpanded_trailing,
        swing_opportunity=swing_opportunity,
        swing_target_facts=swing_target_facts,
    )

    return FourPlayerRankReport(
        player_id=state.player_id,
        declared_player_count=declared_player_count,
        active_player_ids=active_player_ids,
        active_opponent_ids=active_opponent_ids,
        active_player_count=len(active_player_ids),
        is_declared_four_player_context=is_declared_four_player_context,
        is_active_four_player_context=is_active_four_player_context,
        is_four_player_context=is_four_player_context,
        standings=standings,
        current_player_standing=current,
        planet_count_leader_ids=planet_count_leader_ids,
        production_leader_ids=production_leader_ids,
        total_ship_leader_ids=total_ship_leader_ids,
        current_player_planet_count_rank=(
            None if current is None else current.planet_count_rank
        ),
        current_player_production_rank=(
            None if current is None else current.production_rank
        ),
        current_player_total_ship_rank=(
            None if current is None else current.total_ship_rank
        ),
        planet_count_delta_to_leader=planet_count_delta_to_leader,
        production_delta_to_leader=production_delta_to_leader,
        total_ship_delta_to_leader=total_ship_delta_to_leader,
        production_rival_id=None if production_rival is None else production_rival.player_id,
        production_delta_to_next_higher_rival=(
            None if production_rival is None or current is None else production_rival.production - current.production
        ),
        production_delta_to_next_lower_rival=production_trailing,
        total_ship_rival_id=None if total_ship_rival is None else total_ship_rival.player_id,
        total_ship_delta_to_next_higher_rival=(
            None if total_ship_rival is None or current is None else total_ship_rival.total_ships - current.total_ships
        ),
        total_ship_delta_to_next_lower_rival=total_ship_trailing,
        swing_target_facts=swing_target_facts,
        swing_target_count=len(swing_target_facts),
        plausible_swing_target_count=sum(
            1 for facts in swing_target_facts if facts.plausible_with_nearest_source
        ),
        high_value_swing_target_count=sum(
            1 for facts in swing_target_facts if facts.high_value_swing_target
        ),
        leader_owned_swing_target_count=sum(
            1 for facts in swing_target_facts if facts.target_owner_is_leader
        ),
        nearest_swing_target_id=(
            None if nearest_swing_target is None else nearest_swing_target.target_planet_id
        ),
        leader_pressure=leader_pressure,
        rank_preservation_pressure=rank_preservation_pressure,
        underexpanded_trailing=underexpanded_trailing,
        swing_opportunity=swing_opportunity,
        labels=labels,
    )


def _active_player_ids(state: GameState) -> tuple[int, ...]:
    return tuple(
        sorted(
            {
                owner
                for owner in (
                    *(planet.owner for planet in state.planets),
                    *(fleet.owner for fleet in state.fleets),
                )
                if owner >= 0
            },
        ),
    )


def _standing_base_for_player(
    state: GameState,
    player_id: int,
) -> FourPlayerRankStandingFacts:
    planets = tuple(planet for planet in state.planets if planet.owner == player_id)
    fleets = tuple(fleet for fleet in state.fleets if fleet.owner == player_id)
    planet_ships = sum(planet.ships for planet in planets)
    fleet_ships = sum(fleet.ships for fleet in fleets)
    return FourPlayerRankStandingFacts(
        player_id=player_id,
        planet_count=len(planets),
        production=sum(planet.production for planet in planets),
        planet_ships=planet_ships,
        fleet_count=len(fleets),
        fleet_ships=fleet_ships,
        total_ships=planet_ships + fleet_ships,
    )


def _rank_by_value(player_values: Iterable[tuple[int, int]]) -> dict[int, int]:
    sorted_values = sorted(player_values, key=lambda item: (-item[1], item[0]))
    return {player_id: index + 1 for index, (player_id, _value) in enumerate(sorted_values)}


def _leader_ids(
    standings: tuple[FourPlayerRankStandingFacts, ...],
    field_name: str,
) -> tuple[int, ...]:
    if not standings:
        return ()
    max_value = max(getattr(standing, field_name) for standing in standings)
    return tuple(
        standing.player_id
        for standing in standings
        if getattr(standing, field_name) == max_value
    )


def _current_player_standing(
    standings: tuple[FourPlayerRankStandingFacts, ...],
) -> FourPlayerRankStandingFacts | None:
    for standing in standings:
        if standing.is_current_player:
            return standing
    return None


def _delta_to_leader(
    current: FourPlayerRankStandingFacts | None,
    standings: tuple[FourPlayerRankStandingFacts, ...],
    field_name: str,
) -> int | None:
    if current is None or not standings:
        return None
    return max(0, max(getattr(standing, field_name) for standing in standings) - getattr(current, field_name))


def _next_higher_rival(
    current: FourPlayerRankStandingFacts | None,
    standings: tuple[FourPlayerRankStandingFacts, ...],
    field_name: str,
) -> FourPlayerRankStandingFacts | None:
    if current is None:
        return None
    higher = tuple(
        standing
        for standing in standings
        if standing.player_id != current.player_id
        and getattr(standing, field_name) > getattr(current, field_name)
    )
    if not higher:
        return None
    return min(
        higher,
        key=lambda standing: (
            getattr(standing, field_name) - getattr(current, field_name),
            standing.player_id,
        ),
    )


def _next_lower_delta(
    current: FourPlayerRankStandingFacts | None,
    standings: tuple[FourPlayerRankStandingFacts, ...],
    field_name: str,
) -> int | None:
    if current is None:
        return None
    lower = tuple(
        standing
        for standing in standings
        if standing.player_id != current.player_id
        and getattr(standing, field_name) < getattr(current, field_name)
    )
    if not lower:
        return None
    closest = max(
        lower,
        key=lambda standing: (
            getattr(standing, field_name),
            -standing.player_id,
        ),
    )
    return getattr(current, field_name) - getattr(closest, field_name)


def _is_swing_target(planet: Planet, player_id: int | None) -> bool:
    return (
        player_id is not None
        and planet.owner != player_id
        and planet.production > 0
    )


def _swing_target_facts(
    *,
    target: Planet,
    owned_sources: tuple[Planet, ...],
    production_leader_ids: tuple[int, ...],
) -> FourPlayerSwingTargetFacts:
    nearest_source = _nearest_source(owned_sources, target)
    distance_to_nearest_source = None
    eta_ticks = None
    nearest_source_ships = None
    plausible = False
    if nearest_source is not None:
        distance_to_nearest_source = round(
            distance(nearest_source.position, target.position),
            6,
        )
        eta_ticks = _eta_ticks_from_source(nearest_source, target)
        nearest_source_ships = nearest_source.ships
        plausible = max(0, nearest_source.ships - 1) > target.ships
    high_value = target.production >= HIGH_SWING_PRODUCTION_THRESHOLD
    target_owner_is_leader = target.owner in production_leader_ids
    labels: list[str] = ["production_swing_target"]
    if high_value:
        labels.append("high_value_swing_target")
    if plausible:
        labels.append("plausible_with_nearest_source")
    if target_owner_is_leader:
        labels.append("leader_owned_swing_target")
    if high_value and not plausible:
        labels.append("thin_capture_risk_context")
    return FourPlayerSwingTargetFacts(
        target_planet_id=target.planet_id,
        target_owner=target.owner,
        target_ships=target.ships,
        target_production=target.production,
        production_bearing=True,
        target_owner_is_leader=target_owner_is_leader,
        nearest_owned_source_id=(
            None if nearest_source is None else nearest_source.planet_id
        ),
        nearest_owned_source_ships=nearest_source_ships,
        distance_to_nearest_source=distance_to_nearest_source,
        eta_ticks_from_nearest_source=eta_ticks,
        plausible_with_nearest_source=plausible,
        high_value_swing_target=high_value,
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


def _nearest_swing_target(
    targets: tuple[FourPlayerSwingTargetFacts, ...],
) -> FourPlayerSwingTargetFacts | None:
    if not targets:
        return None
    return min(
        targets,
        key=lambda facts: (
            0 if facts.plausible_with_nearest_source else 1,
            float("inf")
            if facts.distance_to_nearest_source is None
            else facts.distance_to_nearest_source,
            -facts.target_production,
            facts.target_ships,
            facts.target_planet_id,
        ),
    )


def _eta_ticks_from_source(source: Planet, target: Planet) -> int:
    ships_to_send = max(1, target.ships + 1)
    travel_distance = max(
        0.0,
        distance(source.position, target.position) - target.radius,
    )
    return int(math.ceil(travel_distance / fleet_speed(ships_to_send)))


def _labels(
    *,
    is_declared_four_player_context: bool,
    is_active_four_player_context: bool,
    active_player_count: int,
    leader_pressure: bool,
    rank_preservation_pressure: bool,
    underexpanded_trailing: bool,
    swing_opportunity: bool,
    swing_target_facts: tuple[FourPlayerSwingTargetFacts, ...],
) -> tuple[str, ...]:
    labels: list[str] = []
    if is_declared_four_player_context:
        labels.append("declared_four_player_context")
    if is_active_four_player_context:
        labels.append("active_four_player_context")
    if is_declared_four_player_context and active_player_count < 4:
        labels.append("declared_four_player_reduced_active_owners")
    if leader_pressure:
        labels.append("leader_pressure")
    if rank_preservation_pressure:
        labels.append("rank_preservation_pressure")
    if underexpanded_trailing:
        labels.append("underexpanded_trailing")
    if swing_opportunity:
        labels.append("swing_opportunity")
    if any("leader_owned_swing_target" in facts.labels for facts in swing_target_facts):
        labels.append("leader_owned_swing_target")
    if any("thin_capture_risk_context" in facts.labels for facts in swing_target_facts):
        labels.append("thin_capture_risk_context")
    return tuple(labels)


__all__ = (
    "FourPlayerRankReport",
    "FourPlayerRankStandingFacts",
    "FourPlayerSwingTargetFacts",
    "HIGH_SWING_PRODUCTION_THRESHOLD",
    "RANK_PRESERVATION_PRODUCTION_MARGIN",
    "UNDEREXPANDED_PLANET_RANK_THRESHOLD",
    "UNDEREXPANDED_PRODUCTION_RANK_THRESHOLD",
    "four_player_rank_facts",
)
