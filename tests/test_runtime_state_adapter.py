"""Tests for Runtime / Submission Cycle 1 state adapter."""

from __future__ import annotations

import copy
import importlib
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from agents import observation_to_game_state
from ow_sim.state import GameState


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def load_fixture(name: str) -> dict[str, object]:
    with (FIXTURES_DIR / name).open(encoding="utf-8") as fh:
        return json.load(fh)


class RuntimeStateAdapterTests(unittest.TestCase):
    def test_runtime_state_module_imports_and_package_export_is_available(self) -> None:
        module = importlib.import_module("agents.runtime_state")

        self.assertIs(module.observation_to_game_state, observation_to_game_state)

    def test_parses_two_player_step_zero_fixture(self) -> None:
        state = observation_to_game_state(load_fixture("kaggle_seed7_2p_step0.json"))

        self.assertIsInstance(state, GameState)
        self.assertEqual(state.step, 0)
        self.assertEqual(state.player_id, 0)
        self.assertEqual(len(state.planets), 24)
        self.assertEqual(state.fleets, ())

    def test_parses_four_player_active_non_neutral_owners(self) -> None:
        state = observation_to_game_state(load_fixture("kaggle_seed7_4p_step0.json"))

        self.assertEqual(
            {planet.owner for planet in state.planets if planet.owner >= 0},
            {0, 1, 2, 3},
        )

    def test_parses_fleet_containing_fixture(self) -> None:
        state = observation_to_game_state(load_fixture("kaggle_seed7_2p_step1_fleet.json"))

        self.assertEqual(len(state.fleets), 1)
        fleet = state.fleets[0]
        self.assertEqual(fleet.owner, 0)
        self.assertEqual(fleet.ships, 3)

    def test_adapter_does_not_mutate_input_observation(self) -> None:
        observation = load_fixture("kaggle_seed7_2p_step0.json")
        before = copy.deepcopy(observation)

        observation_to_game_state(observation)

        self.assertEqual(observation, before)

    def test_invalid_observation_shape_propagates_value_error(self) -> None:
        observation = load_fixture("kaggle_seed7_2p_step0.json")
        observation["planets"][0] = observation["planets"][0][:-1]

        with self.assertRaises(ValueError):
            observation_to_game_state(observation)

    def test_adapter_does_not_call_deferred_planner_or_action_layers(self) -> None:
        observation = load_fixture("kaggle_seed7_2p_step0.json")

        with (
            patch(
                "ow_planner.candidates.generate_candidates",
                side_effect=AssertionError("generate_candidates called"),
            ) as generate_candidates,
            patch(
                "ow_planner.evaluation.evaluate_and_score_candidates",
                side_effect=AssertionError("evaluate_and_score_candidates called"),
            ) as evaluate_and_score_candidates,
            patch(
                "ow_planner.response.evaluate_responses",
                side_effect=AssertionError("evaluate_responses called"),
            ) as evaluate_responses,
            patch(
                "ow_planner.commitment.commitment_options_for_candidates",
                side_effect=AssertionError("commitment_options_for_candidates called"),
            ) as commitment_options_for_candidates,
            patch(
                "ow_planner.strategy_dispatch.select_strategy_for_mode",
                side_effect=AssertionError("select_strategy_for_mode called"),
            ) as select_strategy_for_mode,
            patch(
                "ow_planner.actions.mission_candidate_to_actions",
                side_effect=AssertionError("mission_candidate_to_actions called"),
            ) as mission_candidate_to_actions,
        ):
            state = observation_to_game_state(observation)

        self.assertEqual(state.step, 0)
        generate_candidates.assert_not_called()
        evaluate_and_score_candidates.assert_not_called()
        evaluate_responses.assert_not_called()
        commitment_options_for_candidates.assert_not_called()
        select_strategy_for_mode.assert_not_called()
        mission_candidate_to_actions.assert_not_called()


if __name__ == "__main__":
    unittest.main()
