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

    def test_agent_delegates_standard_call_shape_to_safe_runtime_turn(self) -> None:
        with patch(
            "agents.orbit_wars_agent.safe_actions_for_observation",
            return_value=[],
        ) as safe_actions:
            result = agent({}, {})

        self.assertEqual(result, [])
        self.assertIsInstance(result, list)
        safe_actions.assert_called_once_with({}, {})

    def test_agent_delegates_fixture_observation_to_safe_runtime_turn(self) -> None:
        observation = load_fixture("kaggle_seed7_2p_step0.json")
        configuration = {"episodeSteps": 400}

        with patch(
            "agents.orbit_wars_agent.safe_actions_for_observation",
            return_value=[],
        ) as safe_actions:
            result = agent(observation, configuration)

        self.assertEqual(result, [])
        safe_actions.assert_called_once_with(observation, configuration)

    def test_agent_returns_fresh_list_each_call(self) -> None:
        with patch(
            "agents.orbit_wars_agent.safe_actions_for_observation",
            side_effect=lambda observation, configuration=None: [],
        ):
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

        with patch(
            "agents.orbit_wars_agent.safe_actions_for_observation",
            return_value=[],
        ):
            agent(observation, configuration)

        self.assertEqual(observation, observation_before)
        self.assertEqual(configuration, configuration_before)

    def test_agent_uses_safe_turn_boundary_instead_of_direct_runtime_stages(self) -> None:
        observation = load_fixture("kaggle_seed7_2p_step0.json")
        configuration = {"episodeSteps": 400}

        with (
            patch(
                "agents.orbit_wars_agent.safe_actions_for_observation",
                return_value=[],
            ) as safe_actions,
            patch(
                "agents.runtime_state.observation_to_game_state",
                side_effect=AssertionError("observation_to_game_state called"),
            ) as observation_to_game_state,
            patch(
                "agents.runtime_planner.run_planner_pipeline",
                side_effect=AssertionError("run_planner_pipeline called"),
            ) as run_planner_pipeline,
            patch(
                "agents.runtime_actions.planner_result_to_actions",
                side_effect=AssertionError("planner_result_to_actions called"),
            ) as planner_result_to_actions,
        ):
            result = agent(observation, configuration)

        self.assertEqual(result, [])
        safe_actions.assert_called_once_with(observation, configuration)
        observation_to_game_state.assert_not_called()
        run_planner_pipeline.assert_not_called()
        planner_result_to_actions.assert_not_called()


if __name__ == "__main__":
    unittest.main()
