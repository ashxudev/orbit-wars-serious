"""Tests for Mission Generation Cycle 2 board feature extraction."""

from __future__ import annotations

import copy
import importlib
import unittest
from dataclasses import FrozenInstanceError

from ow_planner import (
    BoardFeatures,
    NearestTarget,
    OwnerTotals,
    PlanetDistance,
    PlanetFacts,
    extract_board_features,
    generate_candidates,
)
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


def fleet_at(
    fleet_id: int,
    owner: int,
    ships: int,
    *,
    x: float = 1.0,
    y: float = 2.0,
) -> Fleet:
    return Fleet(
        fleet_id=fleet_id,
        owner=owner,
        x=x,
        y=y,
        angle=0.0,
        from_planet_id=1,
        ships=ships,
        raw=(fleet_id, owner, x, y, 0.0, 1, ships),
    )


def state_for_features(
    *,
    player_id: int | None = 0,
    planets: tuple[Planet, ...] | None = None,
    fleets: tuple[Fleet, ...] | None = None,
) -> GameState:
    if planets is None:
        planets = (
            planet_at(4, 0, 10.0, 0.0, 5, 1),
            planet_at(2, -1, 3.0, 4.0, 2, 3),
            planet_at(6, 2, 8.0, 0.0, 9, 1),
            planet_at(1, 0, 0.0, 0.0, 10, 2),
            planet_at(5, -1, 11.0, 0.0, 1, 1, is_comet=True),
            planet_at(3, 1, 0.0, 6.0, 6, 4),
        )
    if fleets is None:
        fleets = (
            fleet_at(3, 2, 5),
            fleet_at(2, 0, 3),
            fleet_at(1, 1, 4),
        )

    comet = CometGroup(
        planet_ids=(5,),
        paths=(((11.0, 0.0), (12.0, 0.0)),),
        path_index=0,
        raw={
            "planet_ids": [5],
            "paths": [[[11.0, 0.0], [12.0, 0.0]]],
            "path_index": 0,
        },
    )
    return GameState(
        tick=9,
        player_id=player_id,
        planets=planets,
        fleets=fleets,
        angular_velocity=0.02,
        initial_planets=planets,
        next_fleet_id=20,
        comet_planet_ids=frozenset({5}),
        comets=(comet,),
        remaining_overage_time=45.0,
        raw_observation={
            "step": 9,
            "player": player_id,
            "planets": [list(planet.raw) for planet in planets],
            "fleets": [list(fleet.raw) for fleet in fleets],
            "comets": [copy.deepcopy(comet.raw)],
        },
    )


class PlannerFeatureExtractionTests(unittest.TestCase):
    def test_feature_modules_import_and_exports_are_available(self) -> None:
        importlib.import_module("ow_planner.features")

        self.assertIs(BoardFeatures, BoardFeatures)
        self.assertIs(OwnerTotals, OwnerTotals)
        self.assertIs(PlanetFacts, PlanetFacts)
        self.assertIs(PlanetDistance, PlanetDistance)
        self.assertIs(NearestTarget, NearestTarget)
        self.assertIsNotNone(extract_board_features)

    def test_effective_player_id_fallback_and_explicit_override(self) -> None:
        state = state_for_features(player_id=0)

        default_features = extract_board_features(state)
        override_features = extract_board_features(state, player_id=1)

        self.assertEqual(default_features.player_id, 0)
        self.assertEqual(tuple(planet.planet_id for planet in default_features.own_planets), (1, 4))
        self.assertEqual(override_features.player_id, 1)
        self.assertEqual(tuple(planet.planet_id for planet in override_features.own_planets), (3,))

    def test_missing_player_id_rejects(self) -> None:
        with self.assertRaises(ValueError):
            extract_board_features(state_for_features(player_id=None))

    def test_planet_and_fleet_partitions_are_correct_and_sorted(self) -> None:
        features = extract_board_features(state_for_features())

        self.assertEqual(tuple(planet.planet_id for planet in features.own_planets), (1, 4))
        self.assertEqual(tuple(planet.planet_id for planet in features.neutral_planets), (2, 5))
        self.assertEqual(tuple(planet.planet_id for planet in features.enemy_planets), (3, 6))
        self.assertEqual(tuple(fleet.fleet_id for fleet in features.own_fleets), (2,))
        self.assertEqual(tuple(fleet.fleet_id for fleet in features.enemy_fleets), (1, 3))

    def test_ship_and_production_totals_are_correct(self) -> None:
        features = extract_board_features(state_for_features())

        self.assertEqual(features.own_planet_ship_total, 15)
        self.assertEqual(features.own_fleet_ship_total, 3)
        self.assertEqual(features.enemy_planet_ship_total, 15)
        self.assertEqual(features.enemy_fleet_ship_total, 9)
        self.assertEqual(features.neutral_planet_ship_total, 3)
        self.assertEqual(features.own_production_total, 3)
        self.assertEqual(features.enemy_production_total, 5)
        self.assertEqual(features.neutral_production_total, 4)

    def test_owner_totals_cover_planets_fleets_and_production(self) -> None:
        features = extract_board_features(state_for_features())

        self.assertEqual(
            features.owner_totals,
            (
                OwnerTotals(owner=-1, planet_ships=3, fleet_ships=0, production=4),
                OwnerTotals(owner=0, planet_ships=15, fleet_ships=3, production=3),
                OwnerTotals(owner=1, planet_ships=6, fleet_ships=4, production=4),
                OwnerTotals(owner=2, planet_ships=9, fleet_ships=5, production=1),
            ),
        )
        self.assertEqual(features.owner_totals_by_owner[0].total_ships, 18)
        self.assertEqual(features.owner_totals_by_owner[2].fleet_ships, 5)

    def test_lookups_expose_expected_planets_fleets_and_facts(self) -> None:
        features = extract_board_features(state_for_features())

        self.assertEqual(features.planet_by_id[5].owner, -1)
        self.assertEqual(features.fleet_by_id[1].owner, 1)
        self.assertEqual(
            features.planet_facts_by_id[5],
            PlanetFacts(
                planet_id=5,
                owner=-1,
                position=(11.0, 0.0),
                radius=2.0,
                ships=1,
                production=1,
                is_comet=True,
                initial_position=(10.0, -1.0),
            ),
        )

    def test_source_target_distances_are_deterministic_and_factual(self) -> None:
        features = extract_board_features(state_for_features())

        self.assertEqual(
            tuple(
                (fact.source_planet_id, fact.target_planet_id)
                for fact in features.source_target_distances
            ),
            ((1, 2), (1, 3), (1, 5), (1, 6), (4, 2), (4, 3), (4, 5), (4, 6)),
        )
        first = features.source_target_distances[0]
        self.assertEqual(first.target_owner, -1)
        self.assertEqual(first.target_ships, 2)
        self.assertEqual(first.target_production, 3)
        self.assertFalse(first.target_is_comet)
        self.assertAlmostEqual(first.distance, 5.0)
        self.assertAlmostEqual(features.target_distances_by_source[4][-1].distance, 2.0)

    def test_nearest_neutral_and_enemy_targets_per_owned_source(self) -> None:
        features = extract_board_features(state_for_features())

        self.assertEqual(
            features.nearest_neutral_by_source[1],
            NearestTarget(
                source_planet_id=1,
                target_planet_id=2,
                distance=5.0,
                target_owner=-1,
                target_ships=2,
                target_production=3,
                target_is_comet=False,
            ),
        )
        self.assertEqual(features.nearest_neutral_by_source[4].target_planet_id, 5)
        self.assertEqual(features.nearest_enemy_by_source[1].target_planet_id, 3)
        self.assertEqual(features.nearest_enemy_by_source[4].target_planet_id, 6)
        self.assertIs(features.frontline_by_source, features.nearest_enemy_by_source)

    def test_behavior_with_no_owned_planets(self) -> None:
        state = state_for_features(
            player_id=0,
            planets=(planet_at(2, -1, 3.0, 4.0, 2, 3), planet_at(3, 1, 0.0, 6.0, 6, 4)),
            fleets=(),
        )

        features = extract_board_features(state)

        self.assertEqual(features.own_planets, ())
        self.assertEqual(features.source_target_distances, ())
        self.assertEqual(dict(features.target_distances_by_source), {})
        self.assertEqual(dict(features.nearest_neutral_by_source), {})
        self.assertEqual(dict(features.nearest_enemy_by_source), {})

    def test_behavior_with_no_neutral_planets(self) -> None:
        state = state_for_features(
            planets=(planet_at(1, 0, 0.0, 0.0, 10, 2), planet_at(3, 1, 0.0, 6.0, 6, 4)),
            fleets=(),
        )

        features = extract_board_features(state)

        self.assertEqual(features.neutral_planets, ())
        self.assertEqual(dict(features.nearest_neutral_by_source), {})
        self.assertEqual(features.nearest_enemy_by_source[1].target_planet_id, 3)

    def test_behavior_with_no_enemy_planets(self) -> None:
        state = state_for_features(
            planets=(planet_at(1, 0, 0.0, 0.0, 10, 2), planet_at(2, -1, 3.0, 4.0, 2, 3)),
            fleets=(),
        )

        features = extract_board_features(state)

        self.assertEqual(features.enemy_planets, ())
        self.assertEqual(dict(features.nearest_enemy_by_source), {})
        self.assertEqual(features.nearest_neutral_by_source[1].target_planet_id, 2)

    def test_feature_objects_and_lookup_mappings_are_immutable(self) -> None:
        features = extract_board_features(state_for_features())

        with self.assertRaises(FrozenInstanceError):
            features.player_id = 1
        with self.assertRaises(TypeError):
            features.planet_by_id[1] = planet_at(99, 0, 0.0, 0.0, 1, 1)

    def test_extraction_does_not_mutate_game_state_or_raw_observation(self) -> None:
        state = state_for_features()
        state_before = copy.deepcopy(state)

        extract_board_features(state)

        self.assertEqual(state, state_before)
        self.assertEqual(state.planets, state_before.planets)
        self.assertEqual(state.fleets, state_before.fleets)
        self.assertEqual(state.comets, state_before.comets)
        self.assertEqual(state.raw_observation, state_before.raw_observation)

    def test_generate_candidates_placeholder_remains_deterministic_and_empty(self) -> None:
        state = state_for_features()

        self.assertEqual(generate_candidates(state), ())
        self.assertEqual(generate_candidates(state), generate_candidates(state))


if __name__ == "__main__":
    unittest.main()
