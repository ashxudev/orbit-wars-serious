"""Four-player plateau opportunity fact extraction.

V1 Deterministic Leak Fix Cycle 7 exposes deterministic observability facts for
stalled four-player replay windows. It does not generate missions, evaluate
candidates, score, commit, select, convert actions, run rollouts, or mutate
game state.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping

from ow_sim.forecast import fleet_speed
from ow_sim.geometry import distance
from ow_sim.state import GameState, Planet


UNDEREXPANDED_PRODUCTION_THRESHOLD = 12
UNDEREXPANDED_PLANET_COUNT_THRESHOLD = 6


@dataclass(frozen=True, slots=True)
class FourPlayerPlateauTargetFacts:
    """Nearest-source opportunity facts for one neutral or enemy target."""

    target_planet_id: int
    target_owner: int
    target_category: str
    target_ships: int
    target_production: int
    production_bearing: bool
    nearest_owned_source_id: int | None
    nearest_owned_source_ships: int | None
    distance_to_nearest_source: float | None
    eta_ticks_from_nearest_source: int | None
    plausible_with_nearest_source: bool
    labels: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "distance_to_nearest_source": self.distance_to_nearest_source,
            "eta_ticks_from_nearest_source": self.eta_ticks_from_nearest_source,
            "labels": list(self.labels),
            "nearest_owned_source_id": self.nearest_owned_source_id,
            "nearest_owned_source_ships": self.nearest_owned_source_ships,
            "plausible_with_nearest_source": self.plausible_with_nearest_source,
            "production_bearing": self.production_bearing,
            "target_category": self.target_category,
            "target_owner": self.target_owner,
            "target_planet_id": self.target_planet_id,
            "target_production": self.target_production,
            "target_ships": self.target_ships,
        }


@dataclass(frozen=True, slots=True)
class FourPlayerPlateauReport:
    """Aggregate four-player plateau and opportunity facts."""

    player_id: int | None
    active_opponent_ids: tuple[int, ...] = ()
    declared_player_count: int | None = None
    active_player_count: int = 0
    is_four_player_context: bool = False
    owned_planet_count: int = 0
    owned_production: int = 0
    owned_ships: int = 0
    neutral_production_target_count: int = 0
    enemy_production_target_count: int = 0
    plausible_neutral_target_count: int = 0
    plausible_enemy_target_count: int = 0
    nearest_expansion_target_id: int | None = None
    nearest_expansion_distance: float | None = None
    nearest_denial_target_id: int | None = None
    nearest_denial_distance: float | None = None
    nearest_plausible_target_id: int | None = None
    candidate_count: int | None = None
    action_count: int | None = None
    runtime_status: str | None = None
    no_action_reason: str | None = None
    plateaued: bool = False
    underexpanded: bool = False
    candidate_backlog_no_action: bool = False
    action_emitting_plateau: bool = False
    target_facts: tuple[FourPlayerPlateauTargetFacts, ...] = ()
    labels: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "action_count": self.action_count,
            "action_emitting_plateau": self.action_emitting_plateau,
            "active_opponent_ids": list(self.active_opponent_ids),
            "active_player_count": self.active_player_count,
            "candidate_backlog_no_action": self.candidate_backlog_no_action,
            "candidate_count": self.candidate_count,
            "declared_player_count": self.declared_player_count,
            "enemy_production_target_count": self.enemy_production_target_count,
            "is_four_player_context": self.is_four_player_context,
            "labels": list(self.labels),
            "nearest_denial_distance": self.nearest_denial_distance,
            "nearest_denial_target_id": self.nearest_denial_target_id,
            "nearest_expansion_distance": self.nearest_expansion_distance,
            "nearest_expansion_target_id": self.nearest_expansion_target_id,
            "nearest_plausible_target_id": self.nearest_plausible_target_id,
            "neutral_production_target_count": self.neutral_production_target_count,
            "no_action_reason": self.no_action_reason,
            "owned_planet_count": self.owned_planet_count,
            "owned_production": self.owned_production,
            "owned_ships": self.owned_ships,
            "plausible_enemy_target_count": self.plausible_enemy_target_count,
            "plausible_neutral_target_count": self.plausible_neutral_target_count,
            "plateaued": self.plateaued,
            "player_id": self.player_id,
            "runtime_status": self.runtime_status,
            "target_facts": [facts.to_dict() for facts in self.target_facts],
            "underexpanded": self.underexpanded,
        }


def four_player_plateau_facts(
    state: GameState,
    *,
    runtime_metadata: Mapping[str, str] | None = None,
    declared_player_count: int | None = None,
) -> FourPlayerPlateauReport:
    """Return deterministic four-player plateau opportunity facts."""

    if not isinstance(state, GameState):
        raise ValueError("state must be a GameState")
    if runtime_metadata is not None and not isinstance(runtime_metadata, Mapping):
        raise ValueError("runtime_metadata must be None or a mapping")
    if declared_player_count is not None and (
        isinstance(declared_player_count, bool)
        or not isinstance(declared_player_count, int)
        or declared_player_count <= 0
    ):
        raise ValueError("declared_player_count must be None or a positive integer")

    metadata = runtime_metadata or {}
    active_player_ids = tuple(
        sorted(
            {
                owner
                for owner in (
                    *(planet.owner for planet in state.planets),
                    *(fleet.owner for fleet in state.fleets),
                )
                if owner >= 0
            }
        )
    )
    player_id = state.player_id
    active_opponent_ids = tuple(
        player
        for player in active_player_ids
        if player_id is not None and player != player_id
    )
    is_four_player_context = declared_player_count == 4 or len(active_player_ids) == 4
    owned_sources = tuple(
        planet
        for planet in state.planets
        if player_id is not None and planet.owner == player_id
    )
    owned_planet_count = len(owned_sources)
    owned_production = sum(planet.production for planet in owned_sources)
    owned_ships = sum(planet.ships for planet in owned_sources)
    target_facts = tuple(
        _target_facts(target, owned_sources, player_id)
        for target in sorted(
            (
                planet
                for planet in state.planets
                if _is_opportunity_target(planet, player_id)
            ),
            key=lambda planet: (
                0 if planet.owner == -1 else 1,
                -planet.production,
                planet.ships,
                planet.planet_id,
            ),
        )
    )
    neutral_targets = tuple(
        facts for facts in target_facts if facts.target_category == "neutral"
    )
    enemy_targets = tuple(
        facts for facts in target_facts if facts.target_category == "enemy"
    )
    nearest_expansion = _nearest_target(neutral_targets)
    nearest_denial = _nearest_target(enemy_targets)
    nearest_plausible = _nearest_target(
        tuple(facts for facts in target_facts if facts.plausible_with_nearest_source)
    )
    candidate_count = _metadata_int(metadata, "runtime_diagnostic_candidate_count")
    action_count = _metadata_int(metadata, "runtime_diagnostic_action_count")
    runtime_status = metadata.get("runtime_diagnostic_status")
    no_action_reason = metadata.get("runtime_diagnostic_no_action_reason")
    underexpanded = is_four_player_context and (
        owned_production < UNDEREXPANDED_PRODUCTION_THRESHOLD
        or owned_planet_count <= UNDEREXPANDED_PLANET_COUNT_THRESHOLD
    )
    candidate_backlog_no_action = (
        is_four_player_context
        and underexpanded
        and (candidate_count or 0) > 0
        and action_count == 0
        and no_action_reason == "strategy_selection_no_action"
    )
    action_emitting_plateau = (
        is_four_player_context
        and underexpanded
        and action_count is not None
        and action_count > 0
    )
    plateaued = underexpanded and (
        candidate_backlog_no_action
        or action_emitting_plateau
        or bool(target_facts)
    )
    labels: list[str] = []
    if is_four_player_context:
        labels.append("four_player_context")
    if underexpanded:
        labels.append("underexpanded_four_player")
    if plateaued:
        labels.append("four_player_plateau")
    if candidate_backlog_no_action:
        labels.append("candidate_backlog_no_action")
    if action_emitting_plateau:
        labels.append("action_emitting_plateau")
    if neutral_targets:
        labels.append("neutral_production_opportunities")
    if enemy_targets:
        labels.append("enemy_production_denial_opportunities")

    return FourPlayerPlateauReport(
        player_id=player_id,
        active_opponent_ids=active_opponent_ids,
        declared_player_count=declared_player_count,
        active_player_count=len(active_player_ids),
        is_four_player_context=is_four_player_context,
        owned_planet_count=owned_planet_count,
        owned_production=owned_production,
        owned_ships=owned_ships,
        neutral_production_target_count=len(neutral_targets),
        enemy_production_target_count=len(enemy_targets),
        plausible_neutral_target_count=sum(
            1 for facts in neutral_targets if facts.plausible_with_nearest_source
        ),
        plausible_enemy_target_count=sum(
            1 for facts in enemy_targets if facts.plausible_with_nearest_source
        ),
        nearest_expansion_target_id=(
            None if nearest_expansion is None else nearest_expansion.target_planet_id
        ),
        nearest_expansion_distance=(
            None
            if nearest_expansion is None
            else nearest_expansion.distance_to_nearest_source
        ),
        nearest_denial_target_id=(
            None if nearest_denial is None else nearest_denial.target_planet_id
        ),
        nearest_denial_distance=(
            None if nearest_denial is None else nearest_denial.distance_to_nearest_source
        ),
        nearest_plausible_target_id=(
            None if nearest_plausible is None else nearest_plausible.target_planet_id
        ),
        candidate_count=candidate_count,
        action_count=action_count,
        runtime_status=runtime_status,
        no_action_reason=no_action_reason,
        plateaued=plateaued,
        underexpanded=underexpanded,
        candidate_backlog_no_action=candidate_backlog_no_action,
        action_emitting_plateau=action_emitting_plateau,
        target_facts=target_facts,
        labels=tuple(labels),
    )


def _is_opportunity_target(planet: Planet, player_id: int | None) -> bool:
    if planet.production <= 0:
        return False
    if planet.owner == -1:
        return True
    return player_id is not None and planet.owner >= 0 and planet.owner != player_id


def _target_facts(
    target: Planet,
    owned_sources: tuple[Planet, ...],
    player_id: int | None,
) -> FourPlayerPlateauTargetFacts:
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
    category = "neutral" if target.owner == -1 else "enemy"
    labels = [f"{category}_production_target"]
    if plausible:
        labels.append("plausible_with_nearest_source")
    if player_id is not None and target.owner != player_id:
        labels.append("conversion_opportunity")
    return FourPlayerPlateauTargetFacts(
        target_planet_id=target.planet_id,
        target_owner=target.owner,
        target_category=category,
        target_ships=target.ships,
        target_production=target.production,
        production_bearing=True,
        nearest_owned_source_id=(
            None if nearest_source is None else nearest_source.planet_id
        ),
        nearest_owned_source_ships=nearest_source_ships,
        distance_to_nearest_source=distance_to_nearest_source,
        eta_ticks_from_nearest_source=eta_ticks,
        plausible_with_nearest_source=plausible,
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


def _nearest_target(
    targets: tuple[FourPlayerPlateauTargetFacts, ...],
) -> FourPlayerPlateauTargetFacts | None:
    if not targets:
        return None
    return min(
        targets,
        key=lambda facts: (
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


def _metadata_int(metadata: Mapping[str, str], key: str) -> int | None:
    value = metadata.get(key)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


__all__ = (
    "FourPlayerPlateauReport",
    "FourPlayerPlateauTargetFacts",
    "UNDEREXPANDED_PLANET_COUNT_THRESHOLD",
    "UNDEREXPANDED_PRODUCTION_THRESHOLD",
    "four_player_plateau_facts",
)
