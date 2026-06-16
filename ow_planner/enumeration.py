"""Planner source-target pair enumeration.

Mission Generation Cycle 3 turns board features into deterministic factual
source-target opportunities. It does not create launch candidates, estimate
required ships, score targets, simulate outcomes, or choose actions.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ow_sim.forecast import fleet_ticks_to_reach_distance
from ow_sim.state import GameState, Point2D

from .candidates import CandidateGenerationConfig
from .features import BoardFeatures, NEUTRAL_OWNER, PlanetDistance, extract_board_features


ROUGH_TRAVEL_SHIPS = 1
"""Placeholder ship count used only for factual rough travel tick estimates."""


class TargetCategory(str, Enum):
    """Factual target ownership categories considered by this enumerator."""

    NEUTRAL = "neutral"
    ENEMY = "enemy"


@dataclass(frozen=True, slots=True)
class SourceTargetPair:
    """Factual single-source opportunity from an owned planet to a target."""

    source_planet_id: int
    target_planet_id: int
    target_owner: int
    target_category: TargetCategory
    source_ships: int
    target_ships: int
    target_production: int
    source_position: Point2D
    target_position: Point2D
    distance: float
    rough_travel_ticks: int
    source_affordable_ships: int
    target_is_comet: bool = False


def enumerate_source_target_pairs(
    state_or_features: GameState | BoardFeatures,
    player_id: int | None = None,
    config: CandidateGenerationConfig | None = None,
) -> tuple[SourceTargetPair, ...]:
    """Enumerate factual owned-source to neutral/enemy target pairs.

    ``rough_travel_ticks`` is computed with a one-ship placeholder via the
    simulator fleet ETA helper. This makes the value deterministic and useful
    for coarse ordering/debugging without estimating mission ship requirements.
    Owned sources with no positive ships are omitted.
    """

    _ = config
    if isinstance(state_or_features, BoardFeatures):
        features = state_or_features
    else:
        features = extract_board_features(state_or_features, player_id=player_id)
    return enumerate_source_target_pairs_from_features(features, config=config)


def enumerate_source_target_pairs_from_features(
    features: BoardFeatures,
    config: CandidateGenerationConfig | None = None,
) -> tuple[SourceTargetPair, ...]:
    """Enumerate factual pairs from precomputed board features."""

    _ = config
    source_ships_by_id = {
        planet.planet_id: planet.ships
        for planet in features.own_planets
        if planet.ships > 0
    }
    if not source_ships_by_id:
        return ()

    pairs = [
        _pair_from_distance(distance_fact, features, source_ships_by_id)
        for distance_fact in features.source_target_distances
        if distance_fact.source_planet_id in source_ships_by_id
    ]
    return tuple(
        sorted(
            pairs,
            key=lambda pair: (
                pair.source_planet_id,
                _target_category_rank(pair.target_category),
                pair.target_planet_id,
            ),
        )
    )


def _pair_from_distance(
    distance_fact: PlanetDistance,
    features: BoardFeatures,
    source_ships_by_id: dict[int, int],
) -> SourceTargetPair:
    source_ships = source_ships_by_id[distance_fact.source_planet_id]
    source_facts = features.planet_facts_by_id[distance_fact.source_planet_id]
    target_facts = features.planet_facts_by_id[distance_fact.target_planet_id]
    return SourceTargetPair(
        source_planet_id=distance_fact.source_planet_id,
        target_planet_id=distance_fact.target_planet_id,
        target_owner=distance_fact.target_owner,
        target_category=_target_category(distance_fact.target_owner),
        source_ships=source_ships,
        target_ships=distance_fact.target_ships,
        target_production=distance_fact.target_production,
        source_position=source_facts.position,
        target_position=target_facts.position,
        distance=distance_fact.distance,
        rough_travel_ticks=fleet_ticks_to_reach_distance(
            distance_fact.distance,
            ROUGH_TRAVEL_SHIPS,
        ),
        source_affordable_ships=source_ships,
        target_is_comet=distance_fact.target_is_comet,
    )


def _target_category(owner: int) -> TargetCategory:
    if owner == NEUTRAL_OWNER:
        return TargetCategory.NEUTRAL
    return TargetCategory.ENEMY


def _target_category_rank(category: TargetCategory) -> int:
    if category is TargetCategory.NEUTRAL:
        return 0
    return 1


__all__ = (
    "ROUGH_TRAVEL_SHIPS",
    "SourceTargetPair",
    "TargetCategory",
    "enumerate_source_target_pairs",
    "enumerate_source_target_pairs_from_features",
)
