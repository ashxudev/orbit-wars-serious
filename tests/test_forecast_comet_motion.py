"""Tests for Cycle 4 comet path-index projection helpers."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from ow_sim.constants import GEOMETRY_ABS_TOL
from ow_sim.forecast import (
    comet_group_for_planet,
    comet_path_for_tick,
    comet_position_after_ticks,
    comet_position_at_path_index,
    planet_path_for_tick,
    planet_position_after_ticks,
    planet_position_at_step,
)
from ow_sim.state import GameState


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
COMET_PLANET_ID = 24
STATIC_PLANET_ID = 0


def load_obs(name: str) -> dict[str, object]:
    with (FIXTURE_DIR / name).open(encoding="utf-8") as fh:
        return json.load(fh)


def load_state(name: str) -> GameState:
    return GameState.from_obs(load_obs(name))


def planet_by_id(state: GameState, planet_id: int):
    for planet in state.planets:
        if planet.planet_id == planet_id:
            return planet
    raise AssertionError(f"missing planet {planet_id}")


class ForecastCometMotionTests(unittest.TestCase):
    def assertPointAlmostEqual(
        self,
        actual: tuple[float, float],
        expected: tuple[float, float],
    ) -> None:
        self.assertAlmostEqual(actual[0], expected[0], delta=GEOMETRY_ABS_TOL)
        self.assertAlmostEqual(actual[1], expected[1], delta=GEOMETRY_ABS_TOL)

    def test_current_comet_position_matches_path_index(self) -> None:
        state = load_state("kaggle_seed7_2p_step50_comet.json")
        group, slot = comet_group_for_planet(state, COMET_PLANET_ID)

        self.assertEqual(group.path_index, 0)
        self.assertPointAlmostEqual(
            comet_position_at_path_index(state, COMET_PLANET_ID, group.path_index),
            group.paths[slot][group.path_index],
        )
        self.assertPointAlmostEqual(
            planet_by_id(state, COMET_PLANET_ID).position,
            group.paths[slot][group.path_index],
        )

    def test_future_comet_position_advances_by_path_index(self) -> None:
        state = load_state("kaggle_seed7_2p_step50_comet.json")
        group, slot = comet_group_for_planet(state, COMET_PLANET_ID)

        self.assertPointAlmostEqual(
            comet_position_after_ticks(state, COMET_PLANET_ID, 1),
            group.paths[slot][group.path_index + 1],
        )

    def test_future_comet_position_matches_official_step51_observation(self) -> None:
        state50 = load_state("kaggle_seed7_2p_step50_comet.json")
        state51 = load_state("kaggle_seed7_2p_step51_comet.json")
        observed51 = planet_by_id(state51, COMET_PLANET_ID)

        self.assertPointAlmostEqual(
            comet_position_after_ticks(state50, COMET_PLANET_ID, 1),
            observed51.position,
        )
        self.assertPointAlmostEqual(
            planet_position_at_step(state50, COMET_PLANET_ID, 51),
            observed51.position,
        )

    def test_expiry_position_returns_none_beyond_path_length(self) -> None:
        state = load_state("kaggle_seed7_2p_step50_comet.json")
        group, _ = comet_group_for_planet(state, COMET_PLANET_ID)
        dt_to_expiry_position = len(group.paths[0])

        self.assertIsNone(
            comet_position_after_ticks(state, COMET_PLANET_ID, dt_to_expiry_position)
        )
        self.assertIsNone(
            comet_position_at_path_index(state, COMET_PLANET_ID, len(group.paths[0]))
        )

    def test_post_expiry_official_observation_has_no_comet_projection(self) -> None:
        state = load_state("kaggle_seed7_2p_step82_post_comet.json")

        self.assertIsNone(comet_group_for_planet(state, COMET_PLANET_ID))
        self.assertIsNone(planet_position_at_step(state, COMET_PLANET_ID, state.step))

    def test_first_placement_path_disables_collision_check(self) -> None:
        obs = load_obs("kaggle_seed7_2p_step50_comet.json")
        group = obs["comets"][0]
        group["path_index"] = -1
        for planet in obs["planets"]:
            if planet[0] in obs["comet_planet_ids"]:
                planet[2] = -99
                planet[3] = -99
        state = GameState.from_obs(obs)

        path = comet_path_for_tick(state, COMET_PLANET_ID, dt=1)

        self.assertIsNotNone(path)
        old_position, new_position, check_collision = path
        self.assertEqual(old_position, (-99.0, -99.0))
        self.assertPointAlmostEqual(new_position, group["paths"][0][0])
        self.assertFalse(check_collision)

    def test_active_comet_path_interval_checks_collision(self) -> None:
        state = load_state("kaggle_seed7_2p_step50_comet.json")
        group, slot = comet_group_for_planet(state, COMET_PLANET_ID)

        path = comet_path_for_tick(state, COMET_PLANET_ID, dt=1)

        self.assertIsNotNone(path)
        old_position, new_position, check_collision = path
        self.assertPointAlmostEqual(old_position, group.paths[slot][0])
        self.assertPointAlmostEqual(new_position, group.paths[slot][1])
        self.assertTrue(check_collision)

    def test_expiry_path_interval_stays_put_and_checks_collision(self) -> None:
        state = load_state("kaggle_seed7_2p_step50_comet.json")
        group, slot = comet_group_for_planet(state, COMET_PLANET_ID)

        path = comet_path_for_tick(state, COMET_PLANET_ID, dt=len(group.paths[slot]))

        self.assertIsNotNone(path)
        old_position, new_position, check_collision = path
        self.assertPointAlmostEqual(old_position, group.paths[slot][-1])
        self.assertPointAlmostEqual(new_position, group.paths[slot][-1])
        self.assertTrue(check_collision)

    def test_generic_helpers_handle_non_comet_and_comet_planets(self) -> None:
        state = load_state("kaggle_seed7_2p_step50_comet.json")
        group, slot = comet_group_for_planet(state, COMET_PLANET_ID)

        self.assertPointAlmostEqual(
            planet_position_after_ticks(state, COMET_PLANET_ID, 1),
            group.paths[slot][1],
        )

        comet_path = planet_path_for_tick(state, COMET_PLANET_ID)
        self.assertIsNotNone(comet_path)
        self.assertEqual(len(comet_path), 3)

        non_comet_path = planet_path_for_tick(state, STATIC_PLANET_ID)
        self.assertIsNotNone(non_comet_path)
        self.assertEqual(len(non_comet_path), 2)

    def test_missing_comet_group_data_returns_none(self) -> None:
        obs = load_obs("kaggle_seed7_2p_step50_comet.json")
        obs["comets"] = []
        state = GameState.from_obs(obs)

        self.assertIsNone(comet_group_for_planet(state, COMET_PLANET_ID))
        self.assertIsNone(comet_position_after_ticks(state, COMET_PLANET_ID, 1))
        self.assertIsNone(planet_path_for_tick(state, COMET_PLANET_ID))

    def test_missing_comet_path_slot_returns_none(self) -> None:
        obs = load_obs("kaggle_seed7_2p_step50_comet.json")
        obs = copy.deepcopy(obs)
        obs["comets"][0]["paths"] = []
        state = GameState.from_obs(obs)

        self.assertIsNone(comet_group_for_planet(state, COMET_PLANET_ID))
        self.assertIsNone(comet_position_after_ticks(state, COMET_PLANET_ID, 1))
        self.assertIsNone(planet_path_for_tick(state, COMET_PLANET_ID))
