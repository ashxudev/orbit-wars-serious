"""Tests for Orbit Wars observation parsing."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from ow_sim.state import GameState


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def load_fixture(name: str) -> dict[str, object]:
    with (FIXTURE_DIR / name).open(encoding="utf-8") as fh:
        return json.load(fh)


class GameStateParserTests(unittest.TestCase):
    def test_normal_observation_with_planets(self) -> None:
        obs = load_fixture("kaggle_seed7_2p_step0.json")

        state = GameState.from_obs(obs)

        self.assertEqual(state.step, 0)
        self.assertEqual(state.player_id, 0)
        self.assertEqual(len(state.planets), 24)
        self.assertEqual(state.planets[0].planet_id, 0)
        self.assertEqual(state.planets[0].owner, 0)
        self.assertEqual(state.planets[0].ships, 10)
        self.assertEqual(state.planets[0].production, 4)
        self.assertEqual(state.planets[0].initial_position, state.planets[0].position)
        self.assertEqual(len(state.initial_planets), 24)
        self.assertEqual(state.angular_velocity, obs["angular_velocity"])
        self.assertEqual(state.remaining_overage_time, 60.0)

    def test_empty_fleets_parse_as_empty_tuple(self) -> None:
        obs = load_fixture("kaggle_seed7_2p_step0.json")

        state = GameState.from_obs(obs)

        self.assertEqual(state.fleets, ())
        self.assertEqual(state.next_fleet_id, 0)

    def test_missing_optional_fields_do_not_crash(self) -> None:
        obs = load_fixture("kaggle_seed7_2p_step0.json")
        for key in (
            "angular_velocity",
            "initial_planets",
            "next_fleet_id",
            "comets",
            "comet_planet_ids",
            "remainingOverageTime",
        ):
            obs.pop(key, None)

        state = GameState.from_obs(obs)

        self.assertEqual(len(state.planets), 24)
        self.assertIsNone(state.angular_velocity)
        self.assertEqual(state.initial_planets, ())
        self.assertIsNone(state.next_fleet_id)
        self.assertEqual(state.comets, ())
        self.assertEqual(state.comet_planet_ids, frozenset())
        self.assertIsNone(state.remaining_overage_time)

    def test_fleet_parsing_from_official_launch_observation(self) -> None:
        obs = load_fixture("kaggle_seed7_2p_step1_fleet.json")

        state = GameState.from_obs(obs)

        self.assertEqual(state.step, 1)
        self.assertEqual(state.next_fleet_id, 1)
        self.assertEqual(len(state.fleets), 1)
        fleet = state.fleets[0]
        self.assertEqual(fleet.fleet_id, 0)
        self.assertEqual(fleet.owner, 0)
        self.assertEqual(fleet.position, (94.94284785935255, 75.12728435190571))
        self.assertEqual(fleet.angle, 0.0)
        self.assertEqual(fleet.from_planet_id, 0)
        self.assertEqual(fleet.ships, 3)

    def test_2p_and_4p_state_shapes(self) -> None:
        two_player = GameState.from_obs(load_fixture("kaggle_seed7_2p_step0.json"))
        four_player = GameState.from_obs(load_fixture("kaggle_seed7_4p_step0.json"))

        self.assertEqual(
            {planet.owner for planet in two_player.planets if planet.owner != -1},
            {0, 1},
        )
        self.assertEqual(
            {planet.owner for planet in four_player.planets if planet.owner != -1},
            {0, 1, 2, 3},
        )

    def test_comet_fields_parse_from_official_observation(self) -> None:
        obs = load_fixture("kaggle_seed7_2p_step50_comet.json")

        state = GameState.from_obs(obs)

        self.assertEqual(state.step, 50)
        self.assertEqual(state.comet_planet_ids, frozenset({24, 25, 26, 27}))
        self.assertEqual(len(state.comets), 1)
        comet = state.comets[0]
        self.assertEqual(comet.planet_ids, (24, 25, 26, 27))
        self.assertEqual(comet.path_index, 0)
        self.assertEqual(len(comet.paths), 4)
        self.assertTrue(all(len(path) == 32 for path in comet.paths))
        comet_planets = [planet for planet in state.planets if planet.is_comet]
        self.assertEqual([planet.planet_id for planet in comet_planets], [24, 25, 26, 27])

    def test_parser_does_not_mutate_input_observation(self) -> None:
        obs = load_fixture("kaggle_seed7_2p_step1_fleet.json")
        original = copy.deepcopy(obs)

        state = GameState.from_obs(obs)
        obs["planets"][0][5] = 999

        self.assertEqual(original["planets"][0][5], 11)
        self.assertEqual(state.planets[0].ships, 11)
        self.assertEqual(state.raw_observation["planets"][0][5], 11)
        self.assertNotEqual(obs, original)

    def test_invalid_planet_row_length_raises(self) -> None:
        obs = load_fixture("kaggle_seed7_2p_step0.json")
        obs["planets"][0] = obs["planets"][0][:-1]

        with self.assertRaises(ValueError):
            GameState.from_obs(obs)
