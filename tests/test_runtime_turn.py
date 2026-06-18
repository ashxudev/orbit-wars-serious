"""Tests for Runtime / Submission Cycle 4 safe turn orchestration."""

from __future__ import annotations

import copy
import importlib
import unittest
from unittest.mock import patch

from agents import (
    RuntimePlannerConfig,
    RuntimePlannerResult,
    RuntimeTurnConfig,
    RuntimeTurnResult,
    RuntimeTurnStatus,
    run_runtime_turn,
    safe_actions_for_observation,
)
from ow_planner import (
    StrategyMode,
    StrategyModeFacts,
    StrategySelectionResult,
    StrategySelectionStatus,
)
from ow_sim.state import GameState, Planet


def state_fixture() -> GameState:
    planet = Planet(
        planet_id=1,
        owner=0,
        x=0.0,
        y=0.0,
        radius=0.5,
        ships=10,
        production=1,
        raw=(1, 0, 0.0, 0.0, 0.5, 10, 1),
    )
    return GameState(
        tick=0,
        player_id=0,
        planets=(planet,),
        initial_planets=(planet,),
        next_fleet_id=100,
    )


def planner_result_fixture(state: GameState) -> RuntimePlannerResult:
    strategy_mode_facts = StrategyModeFacts(
        mode=StrategyMode.TWO_PLAYER,
        player_id=0,
        active_player_ids=(0, 1),
        opponent_player_ids=(1,),
        player_count=2,
    )
    return RuntimePlannerResult(
        state=state,
        candidates=(),
        evaluations=(),
        response_evaluations=(),
        commitment_options=(),
        strategy_mode_facts=strategy_mode_facts,
        four_player_board_facts=None,
        bundles=(),
        selection=StrategySelectionResult(status=StrategySelectionStatus.NO_ACTION),
    )


class RuntimeTurnTests(unittest.TestCase):
    def test_runtime_turn_module_imports_and_exports_are_available(self) -> None:
        module = importlib.import_module("agents.runtime_turn")

        self.assertIs(module.RuntimeTurnStatus, RuntimeTurnStatus)
        self.assertIs(module.RuntimeTurnConfig, RuntimeTurnConfig)
        self.assertIs(module.RuntimeTurnResult, RuntimeTurnResult)
        self.assertIs(module.run_runtime_turn, run_runtime_turn)
        self.assertIs(module.safe_actions_for_observation, safe_actions_for_observation)

    def test_successful_turn_with_actions_preserves_stage_order_and_config(self) -> None:
        observation = {"step": 0}
        configuration = {"episodeSteps": 400}
        planner_config = RuntimePlannerConfig()
        turn_config = RuntimeTurnConfig(planner_config=planner_config)
        state = state_fixture()
        planner_result = planner_result_fixture(state)
        expected_actions = [[1, 0.25, 3]]
        call_order: list[str] = []

        def parse_side_effect(observation_arg: object) -> GameState:
            self.assertIs(observation_arg, observation)
            call_order.append("parse")
            return state

        def planner_side_effect(
            state_arg: GameState,
            config_arg: RuntimePlannerConfig | None = None,
        ) -> RuntimePlannerResult:
            self.assertIs(state_arg, state)
            self.assertIs(config_arg, planner_config)
            call_order.append("planner")
            return planner_result

        def actions_side_effect(
            result_arg: RuntimePlannerResult,
        ) -> list[list[int | float]]:
            self.assertIs(result_arg, planner_result)
            call_order.append("actions")
            return expected_actions

        with (
            patch(
                "agents.runtime_turn.observation_to_game_state",
                side_effect=parse_side_effect,
            ) as parse,
            patch(
                "agents.runtime_turn.run_planner_pipeline",
                side_effect=planner_side_effect,
            ) as planner,
            patch(
                "agents.runtime_turn.planner_result_to_actions",
                side_effect=actions_side_effect,
            ) as actions,
        ):
            result = run_runtime_turn(observation, configuration, turn_config)

        self.assertEqual(call_order, ["parse", "planner", "actions"])
        self.assertEqual(result.status, RuntimeTurnStatus.ACTIONS)
        self.assertEqual(result.actions, expected_actions)
        self.assertIsNot(result.actions, expected_actions)
        self.assertIs(result.state, state)
        self.assertIs(result.planner_result, planner_result)
        self.assertIsNone(result.error)
        parse.assert_called_once()
        planner.assert_called_once()
        actions.assert_called_once()

    def test_successful_turn_with_empty_actions_returns_no_action(self) -> None:
        state = state_fixture()
        planner_result = planner_result_fixture(state)

        with (
            patch("agents.runtime_turn.observation_to_game_state", return_value=state),
            patch(
                "agents.runtime_turn.run_planner_pipeline",
                return_value=planner_result,
            ),
            patch("agents.runtime_turn.planner_result_to_actions", return_value=[]),
        ):
            first = run_runtime_turn({"step": 0})
            second = run_runtime_turn({"step": 0})

        self.assertEqual(first.status, RuntimeTurnStatus.NO_ACTION)
        self.assertEqual(second.status, RuntimeTurnStatus.NO_ACTION)
        self.assertEqual(first.actions, [])
        self.assertEqual(second.actions, [])
        self.assertIsNot(first.actions, second.actions)

    def test_parse_error_returns_safe_fallback_without_later_stages(self) -> None:
        with (
            patch(
                "agents.runtime_turn.observation_to_game_state",
                side_effect=ValueError("bad observation"),
            ) as parse,
            patch(
                "agents.runtime_turn.run_planner_pipeline",
                side_effect=AssertionError("run_planner_pipeline called"),
            ) as planner,
            patch(
                "agents.runtime_turn.planner_result_to_actions",
                side_effect=AssertionError("planner_result_to_actions called"),
            ) as actions,
        ):
            result = run_runtime_turn({"bad": object()})

        self.assertEqual(result.status, RuntimeTurnStatus.PARSE_ERROR)
        self.assertEqual(result.actions, [])
        self.assertIsNone(result.state)
        self.assertIsNone(result.planner_result)
        self.assertEqual(result.error, "ValueError: bad observation")
        parse.assert_called_once()
        planner.assert_not_called()
        actions.assert_not_called()

    def test_planner_error_returns_safe_fallback_with_state(self) -> None:
        state = state_fixture()

        with (
            patch("agents.runtime_turn.observation_to_game_state", return_value=state),
            patch(
                "agents.runtime_turn.run_planner_pipeline",
                side_effect=RuntimeError("planner failed"),
            ) as planner,
            patch(
                "agents.runtime_turn.planner_result_to_actions",
                side_effect=AssertionError("planner_result_to_actions called"),
            ) as actions,
        ):
            result = run_runtime_turn({"step": 0})

        self.assertEqual(result.status, RuntimeTurnStatus.PLANNER_ERROR)
        self.assertEqual(result.actions, [])
        self.assertIs(result.state, state)
        self.assertIsNone(result.planner_result)
        self.assertEqual(result.error, "RuntimeError: planner failed")
        planner.assert_called_once()
        actions.assert_not_called()

    def test_action_error_returns_safe_fallback_with_planner_result(self) -> None:
        state = state_fixture()
        planner_result = planner_result_fixture(state)

        with (
            patch("agents.runtime_turn.observation_to_game_state", return_value=state),
            patch(
                "agents.runtime_turn.run_planner_pipeline",
                return_value=planner_result,
            ),
            patch(
                "agents.runtime_turn.planner_result_to_actions",
                side_effect=ValueError("invalid action"),
            ) as actions,
        ):
            result = run_runtime_turn({"step": 0})

        self.assertEqual(result.status, RuntimeTurnStatus.ACTION_ERROR)
        self.assertEqual(result.actions, [])
        self.assertIs(result.state, state)
        self.assertIs(result.planner_result, planner_result)
        self.assertEqual(result.error, "ValueError: invalid action")
        actions.assert_called_once()

    def test_safe_actions_for_observation_returns_only_action_list(self) -> None:
        expected_actions = [[1, 0.0, 1]]
        result = RuntimeTurnResult(
            actions=expected_actions,
            status=RuntimeTurnStatus.ACTIONS,
        )

        with patch("agents.runtime_turn.run_runtime_turn", return_value=result) as turn:
            actions = safe_actions_for_observation({"step": 0}, {}, RuntimeTurnConfig())

        self.assertIs(actions, expected_actions)
        turn.assert_called_once()

    def test_runtime_turn_does_not_mutate_observation_or_configuration(self) -> None:
        observation = {"step": 0, "nested": {"safe": True}}
        configuration = {"episodeSteps": 400, "nested": {"safe": True}}
        observation_before = copy.deepcopy(observation)
        configuration_before = copy.deepcopy(configuration)
        state = state_fixture()
        planner_result = planner_result_fixture(state)

        with (
            patch("agents.runtime_turn.observation_to_game_state", return_value=state),
            patch(
                "agents.runtime_turn.run_planner_pipeline",
                return_value=planner_result,
            ),
            patch("agents.runtime_turn.planner_result_to_actions", return_value=[]),
        ):
            run_runtime_turn(observation, configuration)

        self.assertEqual(observation, observation_before)
        self.assertEqual(configuration, configuration_before)


if __name__ == "__main__":
    unittest.main()
