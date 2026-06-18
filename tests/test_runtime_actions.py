"""Tests for Runtime / Submission Cycle 3 action conversion boundary."""

from __future__ import annotations

import copy
import importlib
import unittest
from unittest.mock import patch

from agents import (
    RuntimePlannerResult,
    RuntimeTurnConfig,
    agent,
    planner_result_to_actions,
    selected_commitment_to_actions,
)
from ow_planner import (
    CandidateOutcome,
    CommitmentOption,
    CommitmentOptionStatus,
    CommitmentOptionType,
    LaunchCandidate,
    MissionCandidate,
    MissionType,
    PlannerDecisionBundle,
    StrategyMode,
    StrategyModeFacts,
    StrategySelectionResult,
    StrategySelectionStatus,
)
from ow_sim.state import GameState, Planet


def planet_at(
    planet_id: int,
    owner: int,
    ships: int,
    *,
    x: float = 0.0,
    y: float = 0.0,
) -> Planet:
    return Planet(
        planet_id=planet_id,
        owner=owner,
        x=x,
        y=y,
        radius=0.5,
        ships=ships,
        production=0,
        raw=(planet_id, owner, x, y, 0.5, ships, 0),
    )


def state_with_source(*, ships: int = 10, owner: int = 0) -> GameState:
    source = planet_at(1, owner, ships)
    return GameState(
        tick=0,
        player_id=0,
        planets=(source,),
        initial_planets=(source,),
        next_fleet_id=100,
        raw_observation={
            "step": 0,
            "player": 0,
            "planets": [list(source.raw)],
            "fleets": [],
            "next_fleet_id": 100,
        },
    )


def candidate_with_launch(*, ships: int = 3, angle: float = 0.25) -> MissionCandidate:
    launch = LaunchCandidate(
        source_planet_id=1,
        angle=angle,
        ships=ships,
        player_id=0,
    )
    return MissionCandidate(
        mission_type=MissionType.ATTACK_ENEMY,
        target_planet_id=2,
        source_planet_ids=(1,),
        launches=(launch,),
        outcome=CandidateOutcome.VALIDATED,
    )


def commitment_option(
    candidate: MissionCandidate,
    *,
    option_type: CommitmentOptionType = CommitmentOptionType.MINIMUM_CAPTURE,
    status: CommitmentOptionStatus = CommitmentOptionStatus.VALIDATED,
    launches: tuple[LaunchCandidate, ...] | None = None,
) -> CommitmentOption:
    option_launches = candidate.launches if launches is None else launches
    return CommitmentOption(
        option_type=option_type,
        candidate=candidate,
        launches=option_launches,
        source_planet_ids=tuple(launch.source_planet_id for launch in option_launches),
        ships_committed=sum(launch.ships for launch in option_launches),
        status=status,
        note=option_type.value,
    )


def selected_result(
    candidate: MissionCandidate,
    option: CommitmentOption | None,
) -> StrategySelectionResult:
    return StrategySelectionResult(
        status=StrategySelectionStatus.SELECTED,
        selected_bundle=PlannerDecisionBundle(candidate=candidate),
        selected_commitment_option=option,
    )


def runtime_result(
    state: GameState,
    selection: StrategySelectionResult,
) -> RuntimePlannerResult:
    mode_facts = StrategyModeFacts(
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
        strategy_mode_facts=mode_facts,
        four_player_board_facts=None,
        bundles=(),
        selection=selection,
    )


class RuntimeActionConversionTests(unittest.TestCase):
    def test_runtime_actions_module_imports_and_package_exports_are_available(
        self,
    ) -> None:
        module = importlib.import_module("agents.runtime_actions")

        self.assertIs(
            module.selected_commitment_to_actions,
            selected_commitment_to_actions,
        )
        self.assertIs(module.planner_result_to_actions, planner_result_to_actions)

    def test_selected_validated_minimum_capture_converts_to_action_rows(self) -> None:
        state = state_with_source()
        candidate = candidate_with_launch(ships=3, angle=0.25)
        option = commitment_option(candidate)

        actions = selected_commitment_to_actions(
            state,
            selected_result(candidate, option),
        )

        self.assertEqual(actions, [[1, 0.25, 3]])

    def test_conversion_uses_commitment_option_launches_not_candidate_launches(self) -> None:
        state = state_with_source(ships=10)
        candidate = candidate_with_launch(ships=2, angle=0.25)
        adjusted_launch = LaunchCandidate(
            source_planet_id=1,
            angle=0.75,
            ships=5,
            player_id=0,
        )
        option = commitment_option(candidate, launches=(adjusted_launch,))

        actions = selected_commitment_to_actions(
            state,
            selected_result(candidate, option),
        )

        self.assertEqual(actions, [[1, 0.75, 5]])
        self.assertEqual(candidate.launches[0].ships, 2)

    def test_conversion_calls_existing_planner_action_validation(self) -> None:
        state = state_with_source()
        candidate = candidate_with_launch()
        option = commitment_option(candidate)
        expected_actions = [[1, 0.25, 3]]

        with patch(
            "agents.runtime_actions.mission_candidate_to_actions",
            return_value=expected_actions,
        ) as convert:
            actions = selected_commitment_to_actions(
                state,
                selected_result(candidate, option),
            )

        self.assertIs(actions, expected_actions)
        convert.assert_called_once()
        called_state, called_mission = convert.call_args.args
        self.assertIs(called_state, state)
        self.assertEqual(called_mission.launches, option.launches)
        self.assertIsNot(called_mission, candidate)

    def test_non_selected_statuses_return_fresh_empty_lists(self) -> None:
        state = state_with_source()

        for status in (
            StrategySelectionStatus.NO_ACTION,
            StrategySelectionStatus.REJECTED,
            StrategySelectionStatus.UNSELECTED,
        ):
            with self.subTest(status=status):
                selection = StrategySelectionResult(status=status)

                first = selected_commitment_to_actions(state, selection)
                second = selected_commitment_to_actions(state, selection)

                self.assertEqual(first, [])
                self.assertEqual(second, [])
                self.assertIsNot(first, second)

    def test_selected_empty_or_invalid_commitments_return_empty_lists(self) -> None:
        state = state_with_source()
        candidate = candidate_with_launch()
        empty_launch_option = commitment_option(candidate, launches=())

        cases = (
            selected_result(candidate, None),
            selected_result(
                candidate,
                commitment_option(
                    candidate,
                    status=CommitmentOptionStatus.REJECTED,
                ),
            ),
            selected_result(candidate, empty_launch_option),
            selected_result(
                candidate,
                commitment_option(
                    candidate,
                    option_type=CommitmentOptionType.NO_ATTACK,
                    launches=(),
                ),
            ),
        )

        for selection in cases:
            first = selected_commitment_to_actions(state, selection)
            second = selected_commitment_to_actions(state, selection)

            self.assertEqual(first, [])
            self.assertEqual(second, [])
            self.assertIsNot(first, second)

    def test_invalid_selected_commitment_propagates_value_error(self) -> None:
        state = state_with_source(ships=2)
        candidate = candidate_with_launch(ships=5)
        option = commitment_option(candidate)

        with self.assertRaises(ValueError):
            selected_commitment_to_actions(state, selected_result(candidate, option))

    def test_planner_result_to_actions_delegates_to_selection_converter(self) -> None:
        state = state_with_source()
        candidate = candidate_with_launch()
        option = commitment_option(candidate)
        selection = selected_result(candidate, option)
        result = runtime_result(state, selection)
        expected_actions = [[1, 0.25, 3]]

        with patch(
            "agents.runtime_actions.selected_commitment_to_actions",
            return_value=expected_actions,
        ) as convert:
            actions = planner_result_to_actions(result)

        self.assertIs(actions, expected_actions)
        convert.assert_called_once_with(result.state, result.selection)

    def test_action_conversion_does_not_run_planner_or_parse_observations(self) -> None:
        state = state_with_source()
        candidate = candidate_with_launch()
        option = commitment_option(candidate)

        with (
            patch(
                "agents.runtime_planner.run_planner_pipeline",
                side_effect=AssertionError("run_planner_pipeline called"),
            ) as run_planner_pipeline,
            patch(
                "agents.runtime_state.observation_to_game_state",
                side_effect=AssertionError("observation_to_game_state called"),
            ) as observation_to_game_state,
        ):
            actions = selected_commitment_to_actions(
                state,
                selected_result(candidate, option),
            )

        self.assertEqual(actions, [[1, 0.25, 3]])
        run_planner_pipeline.assert_not_called()
        observation_to_game_state.assert_not_called()

    def test_conversion_does_not_mutate_state_selection_or_commitment(self) -> None:
        state = state_with_source()
        candidate = candidate_with_launch()
        option = commitment_option(candidate)
        selection = selected_result(candidate, option)
        state_before = copy.deepcopy(state)
        selection_before = copy.deepcopy(selection)
        option_before = copy.deepcopy(option)

        selected_commitment_to_actions(state, selection)

        self.assertEqual(state, state_before)
        self.assertEqual(selection, selection_before)
        self.assertEqual(option, option_before)

    def test_agent_delegates_to_safe_turn_boundary_not_actions_directly(self) -> None:
        with patch(
            "agents.orbit_wars_agent.safe_actions_for_observation",
            return_value=[],
        ) as safe_actions:
            result = agent({}, {})

        self.assertEqual(result, [])
        safe_actions.assert_called_once()
        self.assertEqual(safe_actions.call_args.args[:2], ({}, {}))
        self.assertIsInstance(safe_actions.call_args.args[2], RuntimeTurnConfig)


if __name__ == "__main__":
    unittest.main()
