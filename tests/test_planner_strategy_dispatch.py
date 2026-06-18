"""Tests for Strategy Modes Cycle 8 unified strategy dispatch."""

from __future__ import annotations

import copy
import importlib
import unittest
from dataclasses import FrozenInstanceError
from unittest.mock import patch

from ow_planner import (
    FourPlayerBoardFacts,
    FourPlayerSelectionConfig,
    LaunchCandidate,
    MissionCandidate,
    MissionType,
    PlannerDecisionBundle,
    StrategyDispatchConfig,
    StrategyMode,
    StrategyModeFacts,
    StrategySelectionResult,
    StrategySelectionStatus,
    TwoPlayerSelectionConfig,
    select_strategy_for_mode,
)


def strategy_facts(mode: StrategyMode) -> StrategyModeFacts:
    if mode is StrategyMode.TWO_PLAYER:
        return StrategyModeFacts(
            mode=StrategyMode.TWO_PLAYER,
            player_id=0,
            active_player_ids=(0, 1),
            opponent_player_ids=(1,),
            player_count=2,
        )
    if mode is StrategyMode.FOUR_PLAYER:
        return StrategyModeFacts(
            mode=StrategyMode.FOUR_PLAYER,
            player_id=0,
            active_player_ids=(0, 1, 2, 3),
            opponent_player_ids=(1, 2, 3),
            player_count=4,
        )
    return StrategyModeFacts(
        mode=StrategyMode.UNKNOWN,
        player_id=0,
        active_player_ids=(0, 1, 2),
        opponent_player_ids=(1, 2),
        player_count=3,
        note="unknown player count",
    )


def mission_candidate(target_planet_id: int = 2) -> MissionCandidate:
    launch = LaunchCandidate(
        source_planet_id=1,
        angle=0.25,
        ships=3,
        player_id=0,
    )
    return MissionCandidate(
        mission_type=MissionType.CAPTURE_NEUTRAL,
        target_planet_id=target_planet_id,
        source_planet_ids=(1,),
        launches=(launch,),
    )


def bundle(
    mode_facts: StrategyModeFacts | None,
    *,
    target_planet_id: int = 2,
) -> PlannerDecisionBundle:
    return PlannerDecisionBundle(
        candidate=mission_candidate(target_planet_id),
        strategy_mode_facts=mode_facts,
    )


class PlannerStrategyDispatchTests(unittest.TestCase):
    def test_strategy_dispatch_module_imports_and_exports_are_available(self) -> None:
        importlib.import_module("ow_planner.strategy_dispatch")

        self.assertIs(StrategyDispatchConfig, StrategyDispatchConfig)
        self.assertIsNotNone(select_strategy_for_mode)

    def test_strategy_dispatch_config_is_constructible_frozen_and_slotted(self) -> None:
        two_config = TwoPlayerSelectionConfig(minimum_total_score=1.0)
        four_config = FourPlayerSelectionConfig(minimum_total_score=2.0)
        config = StrategyDispatchConfig(
            two_player_config=two_config,
            four_player_config=four_config,
        )

        self.assertIs(config.two_player_config, two_config)
        self.assertIs(config.four_player_config, four_config)
        self.assertTrue(hasattr(StrategyDispatchConfig, "__slots__"))
        with self.assertRaises(FrozenInstanceError):
            config.two_player_config = None

    def test_invalid_strategy_dispatch_config_values_raise_value_error(self) -> None:
        invalid_configs = (
            {"two_player_config": object()},
            {"four_player_config": object()},
        )

        for kwargs in invalid_configs:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    StrategyDispatchConfig(**kwargs)

    def test_two_player_mode_routes_to_two_player_selector(self) -> None:
        two_config = TwoPlayerSelectionConfig(minimum_total_score=5.0)
        dispatch_config = StrategyDispatchConfig(two_player_config=two_config)
        bundles = (bundle(strategy_facts(StrategyMode.TWO_PLAYER)),)
        expected = StrategySelectionResult(
            status=StrategySelectionStatus.NO_ACTION,
            notes=("two",),
        )

        with (
            patch(
                "ow_planner.strategy_dispatch.select_two_player_direct_advantage",
                return_value=expected,
            ) as two_selector,
            patch(
                "ow_planner.strategy_dispatch.select_four_player_strategy",
                side_effect=AssertionError("four-player selector called"),
            ),
        ):
            result = select_strategy_for_mode(
                bundles,
                config=dispatch_config,
            )

        self.assertIs(result, expected)
        two_selector.assert_called_once_with(bundles, config=two_config)

    def test_four_player_mode_routes_to_four_player_selector_with_board_facts(
        self,
    ) -> None:
        four_config = FourPlayerSelectionConfig(minimum_total_score=7.0)
        dispatch_config = StrategyDispatchConfig(four_player_config=four_config)
        mode_facts = strategy_facts(StrategyMode.FOUR_PLAYER)
        board_facts = FourPlayerBoardFacts(
            strategy_mode_facts=mode_facts,
            is_four_player_mode=True,
            player_id=0,
            active_player_ids=(0, 1, 2, 3),
        )
        bundles = (bundle(mode_facts),)
        expected = StrategySelectionResult(
            status=StrategySelectionStatus.NO_ACTION,
            notes=("four",),
        )

        with (
            patch(
                "ow_planner.strategy_dispatch.select_two_player_direct_advantage",
                side_effect=AssertionError("two-player selector called"),
            ),
            patch(
                "ow_planner.strategy_dispatch.select_four_player_strategy",
                return_value=expected,
            ) as four_selector,
        ):
            result = select_strategy_for_mode(
                bundles,
                four_player_board_facts=board_facts,
                config=dispatch_config,
            )

        self.assertIs(result, expected)
        four_selector.assert_called_once_with(
            bundles,
            board_facts,
            config=four_config,
        )

    def test_explicit_mode_facts_override_bundle_inferred_facts(self) -> None:
        explicit_two_player = strategy_facts(StrategyMode.TWO_PLAYER)
        inferred_four_player = strategy_facts(StrategyMode.FOUR_PLAYER)
        bundles = (bundle(inferred_four_player),)
        expected = StrategySelectionResult(
            status=StrategySelectionStatus.NO_ACTION,
            notes=("explicit",),
        )

        with (
            patch(
                "ow_planner.strategy_dispatch.select_two_player_direct_advantage",
                return_value=expected,
            ) as two_selector,
            patch(
                "ow_planner.strategy_dispatch.select_four_player_strategy",
                side_effect=AssertionError("four-player selector called"),
            ),
        ):
            result = select_strategy_for_mode(
                bundles,
                strategy_mode_facts=explicit_two_player,
            )

        self.assertIs(result, expected)
        two_selector.assert_called_once_with(bundles, config=None)

    def test_omitted_mode_facts_are_inferred_from_first_available_bundle(self) -> None:
        first = bundle(None, target_planet_id=2)
        second_mode_facts = strategy_facts(StrategyMode.FOUR_PLAYER)
        second = bundle(second_mode_facts, target_planet_id=3)
        board_facts = FourPlayerBoardFacts(
            strategy_mode_facts=second_mode_facts,
            is_four_player_mode=True,
        )
        expected = StrategySelectionResult(
            status=StrategySelectionStatus.NO_ACTION,
            notes=("inferred",),
        )

        with patch(
            "ow_planner.strategy_dispatch.select_four_player_strategy",
            return_value=expected,
        ) as four_selector:
            result = select_strategy_for_mode(
                (first, second),
                four_player_board_facts=board_facts,
            )

        self.assertIs(result, expected)
        four_selector.assert_called_once_with(
            (first, second),
            board_facts,
            config=None,
        )

    def test_missing_mode_facts_return_deterministic_rejection(self) -> None:
        result = select_strategy_for_mode((bundle(None),))

        self.assertEqual(result.status, StrategySelectionStatus.REJECTED)
        self.assertIsNone(result.strategy_mode_facts)
        self.assertEqual(result.notes, ("missing strategy mode facts",))

    def test_unknown_mode_facts_return_deterministic_rejection(self) -> None:
        unknown_facts = strategy_facts(StrategyMode.UNKNOWN)

        result = select_strategy_for_mode(
            (bundle(unknown_facts),),
        )

        self.assertEqual(result.status, StrategySelectionStatus.REJECTED)
        self.assertIs(result.strategy_mode_facts, unknown_facts)
        self.assertEqual(result.notes, ("unknown strategy mode",))

    def test_dispatch_does_not_mutate_inputs(self) -> None:
        mode_facts = strategy_facts(StrategyMode.TWO_PLAYER)
        bundles = (bundle(mode_facts),)
        config = StrategyDispatchConfig(
            two_player_config=TwoPlayerSelectionConfig(minimum_total_score=3.0),
        )
        before = (copy.deepcopy(bundles), copy.deepcopy(config), copy.deepcopy(mode_facts))
        expected = StrategySelectionResult(status=StrategySelectionStatus.NO_ACTION)

        with patch(
            "ow_planner.strategy_dispatch.select_two_player_direct_advantage",
            return_value=expected,
        ):
            select_strategy_for_mode(
                bundles,
                strategy_mode_facts=mode_facts,
                config=config,
            )

        self.assertEqual((bundles, config, mode_facts), before)

    def test_dispatch_does_not_call_deferred_planner_or_simulator_logic(self) -> None:
        bundles = (bundle(strategy_facts(StrategyMode.TWO_PLAYER)),)
        expected = StrategySelectionResult(status=StrategySelectionStatus.NO_ACTION)

        with (
            patch(
                "ow_planner.strategy_dispatch.select_two_player_direct_advantage",
                return_value=expected,
            ),
            patch(
                "ow_planner.candidates.generate_candidates",
                side_effect=AssertionError("generate_candidates called"),
            ),
            patch(
                "ow_planner.evaluation.evaluate_candidates",
                side_effect=AssertionError("evaluate_candidates called"),
            ),
            patch(
                "ow_planner.scoring.score_evaluations",
                side_effect=AssertionError("score_evaluations called"),
            ),
            patch(
                "ow_planner.response.evaluate_responses",
                side_effect=AssertionError("evaluate_responses called"),
            ),
            patch(
                "ow_planner.commitment.commitment_options_for_candidates",
                side_effect=AssertionError("commitment_options_for_candidates called"),
            ),
            patch(
                "ow_planner.actions.mission_candidate_to_actions",
                side_effect=AssertionError("mission_candidate_to_actions called"),
            ),
            patch(
                "ow_planner.actions.mission_candidate_to_orders",
                side_effect=AssertionError("mission_candidate_to_orders called"),
            ),
            patch(
                "ow_sim.timeline.simulate_ticks",
                side_effect=AssertionError("simulate_ticks called"),
            ),
            patch(
                "ow_sim.whatif.simulate_launch_orders",
                side_effect=AssertionError("simulate_launch_orders called"),
            ),
        ):
            result = select_strategy_for_mode(bundles)

        self.assertIs(result, expected)


if __name__ == "__main__":
    unittest.main()
