"""Tests for Cycle 12 multi-tick idle rollouts."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from ow_sim.constants import GEOMETRY_ABS_TOL
from ow_sim.state import CometGroup, GameState, Planet
from ow_sim.timeline import next_game_state_after_tick, simulate_ticks


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def load_state(name: str) -> GameState:
    with (FIXTURE_DIR / name).open(encoding="utf-8") as fh:
        return GameState.from_obs(json.load(fh))


def comet_planet(
    planet_id: int,
    x: float,
    y: float,
) -> Planet:
    return Planet(
        planet_id=planet_id,
        owner=-1,
        x=x,
        y=y,
        radius=0.2,
        ships=0,
        production=1,
        is_comet=True,
        raw=(planet_id, -1, x, y, 0.2, 0, 1),
    )


class TimelineRolloutTests(unittest.TestCase):
    def assertPointAlmostEqual(
        self,
        actual: tuple[float, float],
        expected: tuple[float, float],
    ) -> None:
        self.assertAlmostEqual(actual[0], expected[0], delta=GEOMETRY_ABS_TOL)
        self.assertAlmostEqual(actual[1], expected[1], delta=GEOMETRY_ABS_TOL)

    def assertStateMatchesFixtureSemantics(
        self,
        actual: GameState,
        expected: GameState,
    ) -> None:
        self.assertEqual(actual.tick, expected.tick)
        self.assertEqual(actual.player_id, expected.player_id)
        self.assertEqual(actual.next_fleet_id, expected.next_fleet_id)
        self.assertEqual(actual.comet_planet_ids, expected.comet_planet_ids)
        self.assertEqual(len(actual.planets), len(expected.planets))
        self.assertEqual(len(actual.fleets), len(expected.fleets))

        for actual_planet, expected_planet in zip(actual.planets, expected.planets):
            self.assertEqual(actual_planet.planet_id, expected_planet.planet_id)
            self.assertEqual(actual_planet.owner, expected_planet.owner)
            self.assertPointAlmostEqual(actual_planet.position, expected_planet.position)
            self.assertEqual(actual_planet.radius, expected_planet.radius)
            self.assertEqual(actual_planet.ships, expected_planet.ships)
            self.assertEqual(actual_planet.production, expected_planet.production)

        for actual_fleet, expected_fleet in zip(actual.fleets, expected.fleets):
            self.assertEqual(actual_fleet.fleet_id, expected_fleet.fleet_id)
            self.assertEqual(actual_fleet.owner, expected_fleet.owner)
            self.assertPointAlmostEqual(actual_fleet.position, expected_fleet.position)
            self.assertEqual(actual_fleet.angle, expected_fleet.angle)
            self.assertEqual(actual_fleet.from_planet_id, expected_fleet.from_planet_id)
            self.assertEqual(actual_fleet.ships, expected_fleet.ships)

    def test_ticks_zero_returns_input_state_without_mutation(self) -> None:
        state = load_state("kaggle_seed7_2p_step1_fleet.json")
        raw_before = copy.deepcopy(state.raw_observation)

        result = simulate_ticks(state, 0)

        self.assertIs(result, state)
        self.assertEqual(state.raw_observation, raw_before)

    def test_ticks_one_matches_next_game_state_after_tick(self) -> None:
        state = load_state("kaggle_seed7_2p_step1_fleet.json")

        self.assertEqual(
            simulate_ticks(state, 1),
            next_game_state_after_tick(state),
        )

    def test_multiple_ticks_match_repeated_one_tick_application(self) -> None:
        state = load_state("kaggle_seed7_2p_step1_fleet.json")
        expected = state
        for _ in range(3):
            expected = next_game_state_after_tick(expected)

        self.assertEqual(simulate_ticks(state, 3), expected)

    def test_invalid_tick_counts_raise_value_error(self) -> None:
        state = GameState(tick=0)

        for ticks in (-1, True, False, 1.5, "2", None):
            with self.subTest(ticks=ticks):
                with self.assertRaises(ValueError):
                    simulate_ticks(state, ticks)

    def test_official_step1_to_step2_fixture_matches_one_tick_rollout(self) -> None:
        state = load_state("kaggle_seed7_2p_step1_fleet.json")
        expected = load_state("kaggle_seed7_2p_step2_fleet.json")

        actual = simulate_ticks(state, 1)

        self.assertStateMatchesFixtureSemantics(actual, expected)

    def test_rollout_preserves_metadata_and_advances_existing_comet_metadata(self) -> None:
        comet = comet_planet(24, -99.0, -99.0)
        state = GameState(
            tick=49,
            player_id=0,
            planets=(comet,),
            initial_planets=(comet,),
            angular_velocity=0.04,
            next_fleet_id=12,
            comet_planet_ids=frozenset({24}),
            comets=(
                CometGroup(
                    planet_ids=(24,),
                    paths=(((0.0, 0.0), (1.0, 0.0), (2.0, 0.0)),),
                    path_index=-1,
                ),
            ),
            remaining_overage_time=3.5,
            raw_observation={"step": 49},
        )

        result = simulate_ticks(state, 2)

        self.assertEqual(result.tick, 51)
        self.assertEqual(result.player_id, state.player_id)
        self.assertEqual(result.angular_velocity, state.angular_velocity)
        self.assertEqual(result.next_fleet_id, state.next_fleet_id)
        self.assertEqual(result.remaining_overage_time, state.remaining_overage_time)
        self.assertEqual(result.comet_planet_ids, frozenset({24}))
        self.assertEqual(result.comets[0].path_index, 1)
        self.assertPointAlmostEqual(result.planets[0].position, (1.0, 0.0))
        self.assertIsNone(result.raw_observation)

    def test_rollout_does_not_mutate_fixture_state(self) -> None:
        state = load_state("kaggle_seed7_2p_step1_fleet.json")
        planets_before = state.planets
        fleets_before = state.fleets
        comets_before = state.comets
        raw_before = copy.deepcopy(state.raw_observation)

        simulate_ticks(state, 2)

        self.assertEqual(state.planets, planets_before)
        self.assertEqual(state.fleets, fleets_before)
        self.assertEqual(state.comets, comets_before)
        self.assertEqual(state.raw_observation, raw_before)


if __name__ == "__main__":
    unittest.main()
