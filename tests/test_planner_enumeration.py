"""Tests for Mission Generation Cycle 3 source-target enumeration."""

from __future__ import annotations

import copy
import importlib
import unittest
from dataclasses import FrozenInstanceError

from ow_planner import (
    ROUGH_TRAVEL_SHIPS,
    BoardFeatures,
    SourceTargetPair,
    TargetCategory,
    enumerate_source_target_pairs,
    enumerate_source_target_pairs_from_features,
    extract_board_features,
    generate_candidates,
)
from ow_sim.forecast import fleet_ticks_to_reach_distance
from ow_sim.state import CometGroup, Fleet, GameState, Planet


def planet_at(
    planet_id: int,
    owner: int,
    x: float,
    y: float,
    ships: int,
    production: int,
    *,
    is_comet: bool = False,
) -> Planet:
    initial_position = (x - 1.0, y - 1.0) if is_comet else None
    return Planet(
        planet_id=planet_id,
        owner=owner,
        x=x,
        y=y,
        radius=2.0,
        ships=ships,
        production=production,
        is_comet=is_comet,
        initial_position=initial_position,
        raw=(planet_id, owner, x, y, 2.0, ships, production),
    )


def fleet_at(fleet_id: int, owner: int, ships: int) -> Fleet:
    return Fleet(
        fleet_id=fleet_id,
        owner=owner,
        x=0.0,
        y=0.0,
        angle=0.0,
        from_planet_id=10,
        ships=ships,
        raw=(fleet_id, owner, 0.0, 0.0, 0.0, 10, ships),
    )


def enumeration_state(
    *,
    player_id: int | None = 0,
    planets: tuple[Planet, ...] | None = None,
    fleets: tuple[Fleet, ...] | None = None,
) -> GameState:
    if planets is None:
        planets = (
            planet_at(20, 0, 10.0, 0.0, 0, 5),
            planet_at(4, -1, 6.0, 8.0, 1, 4, is_comet=True),
            planet_at(5, 2, 8.0, 0.0, 9, 1),
            planet_at(10, 0, 0.0, 0.0, 5, 2),
            planet_at(3, -1, 3.0, 4.0, 2, 3),
            planet_at(2, 1, 0.0, 6.0, 6, 1),
        )
    if fleets is None:
        fleets = (
            fleet_at(2, 0, 3),
            fleet_at(1, 1, 4),
        )

    comet = CometGroup(
        planet_ids=(4,),
        paths=(((6.0, 8.0), (7.0, 8.0)),),
        path_index=0,
        raw={
            "planet_ids": [4],
            "paths": [[[6.0, 8.0], [7.0, 8.0]]],
            "path_index": 0,
        },
    )
    return GameState(
        tick=11,
        player_id=player_id,
        planets=planets,
        fleets=fleets,
        angular_velocity=0.02,
        initial_planets=planets,
        next_fleet_id=30,
        comet_planet_ids=frozenset({4}),
        comets=(comet,),
        remaining_overage_time=30.0,
        raw_observation={
            "step": 11,
            "player": player_id,
            "planets": [list(planet.raw) for planet in planets],
            "fleets": [list(fleet.raw) for fleet in fleets],
            "comets": [copy.deepcopy(comet.raw)],
        },
    )


class PlannerEnumerationTests(unittest.TestCase):
    def test_enumeration_module_imports_and_exports_are_available(self) -> None:
        importlib.import_module("ow_planner.enumeration")

        self.assertIsNotNone(enumerate_source_target_pairs)
        self.assertIsNotNone(enumerate_source_target_pairs_from_features)
        self.assertEqual(TargetCategory.NEUTRAL.value, "neutral")
        self.assertEqual(TargetCategory.ENEMY.value, "enemy")
        self.assertEqual(ROUGH_TRAVEL_SHIPS, 1)

    def test_source_target_pair_type_is_frozen(self) -> None:
        pair = SourceTargetPair(
            source_planet_id=1,
            target_planet_id=2,
            target_owner=-1,
            target_category=TargetCategory.NEUTRAL,
            source_ships=5,
            target_ships=2,
            target_production=3,
            source_position=(0.0, 0.0),
            target_position=(3.0, 4.0),
            distance=5.0,
            rough_travel_ticks=5,
            source_affordable_ships=5,
        )

        with self.assertRaises(FrozenInstanceError):
            pair.source_ships = 4

    def test_enumerates_from_game_state(self) -> None:
        pairs = enumerate_source_target_pairs(enumeration_state())

        self.assertEqual(len(pairs), 4)
        self.assertTrue(all(isinstance(pair, SourceTargetPair) for pair in pairs))

    def test_enumerates_from_precomputed_features(self) -> None:
        state = enumeration_state()
        features = extract_board_features(state)

        self.assertEqual(
            enumerate_source_target_pairs_from_features(features),
            enumerate_source_target_pairs(features),
        )

    def test_owned_sources_only_and_zero_ship_source_is_omitted(self) -> None:
        pairs = enumerate_source_target_pairs(enumeration_state())

        self.assertEqual({pair.source_planet_id for pair in pairs}, {10})
        self.assertNotIn(20, {pair.source_planet_id for pair in pairs})

    def test_neutral_and_enemy_targets_only_with_own_planets_excluded(self) -> None:
        pairs = enumerate_source_target_pairs(enumeration_state())

        self.assertEqual({pair.target_planet_id for pair in pairs}, {2, 3, 4, 5})
        self.assertNotIn(20, {pair.target_planet_id for pair in pairs})
        self.assertNotIn(10, {pair.target_planet_id for pair in pairs})

    def test_deterministic_order_is_source_category_then_target_id(self) -> None:
        pairs = enumerate_source_target_pairs(enumeration_state())

        self.assertEqual(
            tuple(
                (
                    pair.source_planet_id,
                    pair.target_category,
                    pair.target_planet_id,
                )
                for pair in pairs
            ),
            (
                (10, TargetCategory.NEUTRAL, 3),
                (10, TargetCategory.NEUTRAL, 4),
                (10, TargetCategory.ENEMY, 2),
                (10, TargetCategory.ENEMY, 5),
            ),
        )

    def test_target_category_classification_and_metadata(self) -> None:
        pairs = enumerate_source_target_pairs(enumeration_state())
        by_target = {pair.target_planet_id: pair for pair in pairs}

        self.assertEqual(by_target[3].target_category, TargetCategory.NEUTRAL)
        self.assertEqual(by_target[3].target_owner, -1)
        self.assertEqual(by_target[2].target_category, TargetCategory.ENEMY)
        self.assertEqual(by_target[2].target_owner, 1)
        self.assertEqual(by_target[5].target_owner, 2)
        self.assertEqual(by_target[4].target_ships, 1)
        self.assertEqual(by_target[4].target_production, 4)
        self.assertTrue(by_target[4].target_is_comet)
        self.assertEqual(by_target[4].source_position, (0.0, 0.0))
        self.assertEqual(by_target[4].target_position, (6.0, 8.0))

    def test_distance_values_are_inherited_from_features(self) -> None:
        state = enumeration_state()
        features = extract_board_features(state)
        pairs = enumerate_source_target_pairs_from_features(features)
        feature_distances = {
            (fact.source_planet_id, fact.target_planet_id): fact.distance
            for fact in features.source_target_distances
        }

        for pair in pairs:
            with self.subTest(pair=pair):
                self.assertEqual(
                    pair.distance,
                    feature_distances[(pair.source_planet_id, pair.target_planet_id)],
                )

    def test_rough_travel_ticks_use_one_ship_placeholder(self) -> None:
        pairs = enumerate_source_target_pairs(enumeration_state())
        by_target = {pair.target_planet_id: pair for pair in pairs}

        self.assertEqual(
            by_target[3].rough_travel_ticks,
            fleet_ticks_to_reach_distance(5.0, ROUGH_TRAVEL_SHIPS),
        )
        self.assertEqual(by_target[3].rough_travel_ticks, 5)
        self.assertEqual(
            by_target[4].rough_travel_ticks,
            fleet_ticks_to_reach_distance(10.0, ROUGH_TRAVEL_SHIPS),
        )

    def test_source_affordability_fields_are_factual(self) -> None:
        pairs = enumerate_source_target_pairs(enumeration_state())

        self.assertTrue(all(pair.source_ships == 5 for pair in pairs))
        self.assertTrue(all(pair.source_affordable_ships == 5 for pair in pairs))

    def test_no_owned_planets_returns_empty_tuple(self) -> None:
        state = enumeration_state(
            planets=(
                planet_at(3, -1, 3.0, 4.0, 2, 3),
                planet_at(2, 1, 0.0, 6.0, 6, 1),
            ),
            fleets=(),
        )

        self.assertEqual(enumerate_source_target_pairs(state), ())

    def test_no_neutral_or_enemy_targets_returns_empty_tuple(self) -> None:
        state = enumeration_state(
            planets=(
                planet_at(10, 0, 0.0, 0.0, 5, 2),
                planet_at(20, 0, 10.0, 0.0, 4, 5),
            ),
            fleets=(),
        )

        self.assertEqual(enumerate_source_target_pairs(state), ())

    def test_zero_ship_owned_source_behavior_returns_empty_when_only_source(self) -> None:
        state = enumeration_state(
            planets=(
                planet_at(20, 0, 10.0, 0.0, 0, 5),
                planet_at(3, -1, 3.0, 4.0, 2, 3),
            ),
            fleets=(),
        )

        self.assertEqual(enumerate_source_target_pairs(state), ())

    def test_explicit_player_id_override_flows_through_feature_extraction(self) -> None:
        state = enumeration_state(player_id=0)

        pairs = enumerate_source_target_pairs(state, player_id=1)

        self.assertEqual({pair.source_planet_id for pair in pairs}, {2})
        self.assertEqual({pair.target_planet_id for pair in pairs}, {3, 4, 5, 10, 20})
        self.assertTrue(all(pair.target_owner != 1 for pair in pairs))

    def test_enumeration_does_not_mutate_input_state_or_features(self) -> None:
        state = enumeration_state()
        features = extract_board_features(state)
        state_before = copy.deepcopy(state)
        feature_snapshot = (
            features.own_planets,
            features.neutral_planets,
            features.enemy_planets,
            dict(features.planet_by_id),
            features.source_target_distances,
            dict(features.target_distances_by_source),
        )

        enumerate_source_target_pairs(state)
        enumerate_source_target_pairs_from_features(features)

        self.assertEqual(state, state_before)
        self.assertEqual(
            feature_snapshot,
            (
                features.own_planets,
                features.neutral_planets,
                features.enemy_planets,
                dict(features.planet_by_id),
                features.source_target_distances,
                dict(features.target_distances_by_source),
            ),
        )

    def test_generate_candidates_returns_empty_when_enumeration_state_has_no_targets(self) -> None:
        state = enumeration_state(
            planets=(planet_at(10, 0, 0.0, 0.0, 5, 2),),
            fleets=(),
        )

        self.assertEqual(generate_candidates(state), ())
        self.assertEqual(generate_candidates(state), generate_candidates(state))


if __name__ == "__main__":
    unittest.main()
