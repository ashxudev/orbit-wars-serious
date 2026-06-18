"""Tests for Runtime / Submission Cycle 0 agent entrypoint."""

from __future__ import annotations

import copy
import importlib
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from agents import agent


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def load_fixture(name: str) -> dict[str, object]:
    with (FIXTURES_DIR / name).open(encoding="utf-8") as fh:
        return json.load(fh)


class RuntimeAgentEntrypointTests(unittest.TestCase):
    def test_agent_module_imports_and_package_export_is_available(self) -> None:
        module = importlib.import_module("agents.orbit_wars_agent")

        self.assertIs(module.agent, agent)

    def test_agent_returns_empty_action_list_for_standard_call_shape(self) -> None:
        result = agent({}, {})

        self.assertEqual(result, [])
        self.assertIsInstance(result, list)

    def test_agent_returns_empty_action_list_for_fixture_observation(self) -> None:
        observation = load_fixture("kaggle_seed7_2p_step0.json")
        configuration = {"episodeSteps": 400}

        result = agent(observation, configuration)

        self.assertEqual(result, [])

    def test_agent_returns_fresh_list_each_call(self) -> None:
        first = agent({}, {})
        second = agent({}, {})

        self.assertEqual(first, [])
        self.assertEqual(second, [])
        self.assertIsNot(first, second)

    def test_agent_does_not_mutate_observation_or_configuration(self) -> None:
        observation = load_fixture("kaggle_seed7_2p_step0.json")
        configuration = {"episodeSteps": 400, "nested": {"safe": True}}
        observation_before = copy.deepcopy(observation)
        configuration_before = copy.deepcopy(configuration)

        agent(observation, configuration)

        self.assertEqual(observation, observation_before)
        self.assertEqual(configuration, configuration_before)

    def test_agent_does_not_call_deferred_planner_or_simulator_layers(self) -> None:
        observation = load_fixture("kaggle_seed7_2p_step0.json")
        configuration = {"episodeSteps": 400}

        with (
            patch(
                "ow_sim.state.GameState.from_obs",
                side_effect=AssertionError("GameState.from_obs called"),
            ) as from_obs,
            patch(
                "ow_planner.candidates.generate_candidates",
                side_effect=AssertionError("generate_candidates called"),
            ) as generate_candidates,
            patch(
                "ow_planner.strategy_dispatch.select_strategy_for_mode",
                side_effect=AssertionError("select_strategy_for_mode called"),
            ) as select_strategy_for_mode,
            patch(
                "ow_planner.actions.mission_candidate_to_actions",
                side_effect=AssertionError("mission_candidate_to_actions called"),
            ) as mission_candidate_to_actions,
        ):
            result = agent(observation, configuration)

        self.assertEqual(result, [])
        from_obs.assert_not_called()
        generate_candidates.assert_not_called()
        select_strategy_for_mode.assert_not_called()
        mission_candidate_to_actions.assert_not_called()


if __name__ == "__main__":
    unittest.main()
