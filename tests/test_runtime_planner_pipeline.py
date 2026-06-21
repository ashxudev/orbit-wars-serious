"""Tests for Runtime / Submission Cycle 2 planner pipeline composition."""

from __future__ import annotations

import copy
import importlib
import unittest
from unittest.mock import patch

from agents import (
    RuntimePlannerConfig,
    RuntimePlannerResult,
    agent,
    run_planner_pipeline,
)
from ow_planner import (
    CandidateGenerationConfig,
    CandidateOutcome,
    CommitmentPolicyConfig,
    EvaluationConfig,
    EnemyDenialOpportunityReport,
    FourPlayerBoardFacts,
    FourPlayerPlateauReport,
    FourPlayerRankReport,
    LaunchCandidate,
    MissionCandidate,
    MissionEvaluation,
    MissionResponseEvaluation,
    MissionScoringConfig,
    MissionType,
    OwnTransferIntentReport,
    OwnedProductionThreatReport,
    PlannerDecisionBundle,
    ResponseConfig,
    StrategyDispatchConfig,
    StrategyMode,
    StrategyModeFacts,
    StrategySelectionResult,
    StrategySelectionStatus,
    TwoPlayerSelectionConfig,
)
from ow_sim.state import GameState, Planet


def planet_at(
    planet_id: int,
    owner: int,
    x: float,
    y: float,
    ships: int,
    production: int = 0,
    radius: float = 0.0,
) -> Planet:
    return Planet(
        planet_id=planet_id,
        owner=owner,
        x=x,
        y=y,
        radius=radius,
        ships=ships,
        production=production,
        raw=(planet_id, owner, x, y, radius, ships, production),
    )


def state_with_planets(*planets: Planet, player_id: int | None = 0) -> GameState:
    planet_tuple = tuple(planets)
    return GameState(
        tick=0,
        player_id=player_id,
        planets=planet_tuple,
        initial_planets=planet_tuple,
        next_fleet_id=100,
        raw_observation={
            "step": 0,
            "player": player_id,
            "planets": [list(planet.raw) for planet in planet_tuple],
            "fleets": [],
            "next_fleet_id": 100,
        },
    )


def two_player_pipeline_state() -> GameState:
    return state_with_planets(
        planet_at(1, 0, 0.0, 0.0, 20),
        planet_at(2, -1, 1.0, 0.0, 0, radius=0.5),
        planet_at(3, 1, 0.0, 1.0, 0, radius=0.5),
    )


def four_player_state() -> GameState:
    return state_with_planets(
        planet_at(1, 0, 0.0, 0.0, 10, production=1),
        planet_at(2, 1, 1.0, 0.0, 10, production=2),
        planet_at(3, 2, 0.0, 1.0, 10, production=3),
        planet_at(4, 3, 1.0, 1.0, 10, production=4),
    )


def empty_candidate_state() -> GameState:
    return state_with_planets(player_id=0)


def sample_candidate() -> MissionCandidate:
    launch = LaunchCandidate(
        source_planet_id=1,
        angle=0.0,
        ships=1,
        player_id=0,
    )
    return MissionCandidate(
        mission_type=MissionType.ATTACK_ENEMY,
        target_planet_id=2,
        source_planet_ids=(1,),
        launches=(launch,),
        outcome=CandidateOutcome.VALIDATED,
    )


class RuntimePlannerPipelineTests(unittest.TestCase):
    def test_runtime_planner_module_imports_and_exports_are_available(self) -> None:
        module = importlib.import_module("agents.runtime_planner")

        self.assertIs(module.RuntimePlannerConfig, RuntimePlannerConfig)
        self.assertIs(module.RuntimePlannerResult, RuntimePlannerResult)
        self.assertIs(module.run_planner_pipeline, run_planner_pipeline)

    def test_pipeline_runs_existing_stack_and_returns_structured_result(self) -> None:
        state = two_player_pipeline_state()

        result = run_planner_pipeline(state)

        self.assertIsInstance(result, RuntimePlannerResult)
        self.assertIs(result.state, state)
        self.assertIsInstance(result.candidates, tuple)
        self.assertIsInstance(result.evaluations, tuple)
        self.assertIsInstance(result.response_evaluations, tuple)
        self.assertIsInstance(result.commitment_options, tuple)
        self.assertIsInstance(result.bundles, tuple)
        self.assertIsInstance(result.selection, StrategySelectionResult)
        candidate_ids = {id(candidate) for candidate in result.candidates}
        self.assertTrue(candidate_ids)
        self.assertTrue(
            all(id(bundle.candidate) in candidate_ids for bundle in result.bundles)
        )

    def test_pipeline_does_not_mutate_input_state(self) -> None:
        state = two_player_pipeline_state()
        before = copy.deepcopy(state)

        run_planner_pipeline(state)

        self.assertEqual(state, before)

    def test_config_objects_are_passed_to_each_runtime_stage(self) -> None:
        state = two_player_pipeline_state()
        candidate_config = CandidateGenerationConfig(max_candidates=1)
        evaluation_config = EvaluationConfig(horizon_ticks=2)
        scoring_config = MissionScoringConfig(production_delta_weight=3.0)
        response_config = ResponseConfig(response_window_ticks=4)
        commitment_config = CommitmentPolicyConfig(max_options_per_candidate=2)
        dispatch_config = StrategyDispatchConfig()
        config = RuntimePlannerConfig(
            candidate_config=candidate_config,
            evaluation_config=evaluation_config,
            scoring_config=scoring_config,
            response_config=response_config,
            commitment_config=commitment_config,
            strategy_dispatch_config=dispatch_config,
        )
        candidate = sample_candidate()
        candidates = (candidate,)
        evaluations = (MissionEvaluation(candidate=candidate),)
        responses = (MissionResponseEvaluation(evaluation=evaluations[0]),)
        commitments = ()
        mode_facts = StrategyModeFacts(
            mode=StrategyMode.FOUR_PLAYER,
            player_id=0,
            active_player_ids=(0, 1, 2, 3),
            opponent_player_ids=(1, 2, 3),
            player_count=4,
        )
        board_facts = FourPlayerBoardFacts(
            strategy_mode_facts=mode_facts,
            is_four_player_mode=True,
            player_id=0,
            active_player_ids=mode_facts.active_player_ids,
        )
        bundles = (PlannerDecisionBundle(candidate=candidate),)
        selection = StrategySelectionResult(status=StrategySelectionStatus.REJECTED)
        plateau_report = FourPlayerPlateauReport(
            player_id=0,
            active_opponent_ids=(1, 2, 3),
            is_four_player_context=True,
            underexpanded=True,
            labels=("four_player_plateau",),
        )
        rank_report = FourPlayerRankReport(
            player_id=0,
            active_player_ids=(0, 1, 2, 3),
            active_opponent_ids=(1, 2, 3),
            active_player_count=4,
            is_active_four_player_context=True,
            is_four_player_context=True,
            leader_pressure=True,
            labels=("leader_pressure",),
        )

        with (
            patch(
                "agents.runtime_planner.generate_candidates",
                return_value=candidates,
            ) as generate_candidates,
            patch(
                "agents.runtime_planner.evaluate_and_score_candidates",
                return_value=evaluations,
            ) as evaluate_and_score_candidates,
            patch(
                "agents.runtime_planner.evaluate_responses",
                return_value=responses,
            ) as evaluate_responses,
            patch(
                "agents.runtime_planner.commitment_options_for_candidates",
                return_value=commitments,
            ) as commitment_options_for_candidates,
            patch(
                "agents.runtime_planner.strategy_mode_facts",
                return_value=mode_facts,
            ) as strategy_mode_facts,
            patch(
                "agents.runtime_planner.four_player_board_facts",
                return_value=board_facts,
            ) as four_player_board_facts,
            patch(
                "agents.runtime_planner.four_player_plateau_facts",
                return_value=plateau_report,
            ) as four_player_plateau_facts,
            patch(
                "agents.runtime_planner.four_player_rank_facts",
                return_value=rank_report,
            ) as four_player_rank_facts,
            patch(
                "agents.runtime_planner.planner_decision_bundles",
                return_value=bundles,
            ) as planner_decision_bundles,
            patch(
                "agents.runtime_planner.select_strategy_for_mode",
                return_value=selection,
            ) as select_strategy_for_mode,
        ):
            result = run_planner_pipeline(state, config)

        generate_candidates.assert_called_once_with(state, candidate_config)
        evaluate_and_score_candidates.assert_called_once_with(
            state,
            candidates,
            evaluation_config=evaluation_config,
            scoring_config=scoring_config,
        )
        evaluate_responses.assert_called_once_with(state, evaluations, response_config)
        commitment_options_for_candidates.assert_called_once_with(
            state,
            candidates,
            commitment_config,
        )
        strategy_mode_facts.assert_called_once_with(state)
        four_player_board_facts.assert_called_once_with(state, mode_facts)
        four_player_plateau_facts.assert_called_once_with(state)
        four_player_rank_facts.assert_called_once_with(state)
        planner_decision_bundles.assert_called_once_with(
            candidates,
            strategy_mode_facts=mode_facts,
            evaluations=evaluations,
            response_evaluations=responses,
            commitment_options=commitments,
        )
        _args, kwargs = select_strategy_for_mode.call_args
        self.assertEqual(_args, (bundles,))
        self.assertIs(kwargs["strategy_mode_facts"], mode_facts)
        self.assertIs(kwargs["four_player_board_facts"], board_facts)
        injected_dispatch_config = kwargs["config"]
        self.assertIsNot(injected_dispatch_config, dispatch_config)
        self.assertIsNone(injected_dispatch_config.two_player_config)
        self.assertIs(
            injected_dispatch_config.four_player_config.four_player_plateau_report,
            plateau_report,
        )
        self.assertIs(
            injected_dispatch_config.four_player_config.four_player_rank_report,
            rank_report,
        )
        self.assertIs(result.candidates, candidates)
        self.assertIs(result.four_player_board_facts, board_facts)
        self.assertIs(result.selection, selection)

    def test_two_player_state_injects_fact_reports_into_selector_config(
        self,
    ) -> None:
        state = two_player_pipeline_state()
        base_two_config = TwoPlayerSelectionConfig(minimum_total_score=-5.0)
        base_dispatch_config = StrategyDispatchConfig(
            two_player_config=base_two_config,
        )
        config = RuntimePlannerConfig(strategy_dispatch_config=base_dispatch_config)
        mode_facts = StrategyModeFacts(
            mode=StrategyMode.TWO_PLAYER,
            player_id=0,
            active_player_ids=(0, 1),
            opponent_player_ids=(1,),
            player_count=2,
        )
        threat_report = OwnedProductionThreatReport(
            player_id=0,
            horizon_ticks=80,
            production_pressure_count=1,
            labels=("owned_production_pressure",),
        )
        transfer_report = OwnTransferIntentReport(
            player_id=0,
            transfer_count=1,
            potentially_spammy_count=1,
            labels=("potentially_spammy_own_transfer",),
        )
        denial_report = EnemyDenialOpportunityReport(
            player_id=0,
            opponent_id=1,
            high_value_denial_count=1,
            labels=("high_value_enemy_denial",),
        )
        selection = StrategySelectionResult(status=StrategySelectionStatus.REJECTED)

        with (
            patch("agents.runtime_planner.generate_candidates", return_value=()),
            patch(
                "agents.runtime_planner.evaluate_and_score_candidates",
                return_value=(),
            ),
            patch("agents.runtime_planner.evaluate_responses", return_value=()),
            patch(
                "agents.runtime_planner.commitment_options_for_candidates",
                return_value=(),
            ),
            patch(
                "agents.runtime_planner.strategy_mode_facts",
                return_value=mode_facts,
            ),
            patch("agents.runtime_planner.planner_decision_bundles", return_value=()),
            patch(
                "agents.runtime_planner.owned_production_threat_facts",
                return_value=threat_report,
            ) as owned_production_threat_facts,
            patch(
                "agents.runtime_planner.own_transfer_intent_facts",
                return_value=transfer_report,
            ) as own_transfer_intent_facts,
            patch(
                "agents.runtime_planner.enemy_denial_opportunity_facts",
                return_value=denial_report,
            ) as enemy_denial_opportunity_facts,
            patch(
                "agents.runtime_planner.select_strategy_for_mode",
                return_value=selection,
            ) as select_strategy_for_mode,
        ):
            result = run_planner_pipeline(state, config)

        owned_production_threat_facts.assert_called_once_with(state)
        own_transfer_intent_facts.assert_called_once_with(
            state,
            threat_report=threat_report,
        )
        enemy_denial_opportunity_facts.assert_called_once_with(state)
        _args, kwargs = select_strategy_for_mode.call_args
        dispatch_config = kwargs["config"]
        self.assertIsNot(dispatch_config, base_dispatch_config)
        self.assertEqual(
            dispatch_config.two_player_config.minimum_total_score,
            -5.0,
        )
        self.assertIs(
            dispatch_config.two_player_config.owned_production_threat_report,
            threat_report,
        )
        self.assertIs(
            dispatch_config.two_player_config.own_transfer_intent_report,
            transfer_report,
        )
        self.assertIs(
            dispatch_config.two_player_config.enemy_denial_opportunity_report,
            denial_report,
        )
        self.assertIs(result.selection, selection)

    def test_four_player_state_computes_and_passes_board_facts(self) -> None:
        state = four_player_state()

        with (
            patch("agents.runtime_planner.generate_candidates", return_value=()),
            patch(
                "agents.runtime_planner.evaluate_and_score_candidates",
                return_value=(),
            ),
            patch("agents.runtime_planner.evaluate_responses", return_value=()),
            patch(
                "agents.runtime_planner.commitment_options_for_candidates",
                return_value=(),
            ),
            patch("agents.runtime_planner.planner_decision_bundles", return_value=()),
            patch(
                "agents.runtime_planner.four_player_board_facts",
                wraps=importlib.import_module(
                    "ow_planner.four_player_strategy"
                ).four_player_board_facts,
            ) as four_player_board_facts,
        ):
            result = run_planner_pipeline(state)

        self.assertEqual(result.strategy_mode_facts.mode, StrategyMode.FOUR_PLAYER)
        self.assertIsNotNone(result.four_player_board_facts)
        self.assertTrue(result.four_player_board_facts.is_four_player_mode)
        four_player_board_facts.assert_called_once_with(
            state,
            result.strategy_mode_facts,
        )

    def test_two_player_state_does_not_compute_four_player_board_facts(self) -> None:
        state = two_player_pipeline_state()

        with (
            patch("agents.runtime_planner.generate_candidates", return_value=()),
            patch(
                "agents.runtime_planner.evaluate_and_score_candidates",
                return_value=(),
            ),
            patch("agents.runtime_planner.evaluate_responses", return_value=()),
            patch(
                "agents.runtime_planner.commitment_options_for_candidates",
                return_value=(),
            ),
            patch("agents.runtime_planner.planner_decision_bundles", return_value=()),
            patch(
                "agents.runtime_planner.four_player_board_facts",
                side_effect=AssertionError("four_player_board_facts called"),
            ) as four_player_board_facts,
        ):
            result = run_planner_pipeline(state)

        self.assertEqual(result.strategy_mode_facts.mode, StrategyMode.TWO_PLAYER)
        self.assertIsNone(result.four_player_board_facts)
        four_player_board_facts.assert_not_called()

    def test_empty_candidate_state_returns_complete_empty_result(self) -> None:
        state = empty_candidate_state()

        result = run_planner_pipeline(state)

        self.assertEqual(result.candidates, ())
        self.assertEqual(result.evaluations, ())
        self.assertEqual(result.response_evaluations, ())
        self.assertEqual(result.commitment_options, ())
        self.assertEqual(result.bundles, ())
        self.assertEqual(result.strategy_mode_facts.mode, StrategyMode.UNKNOWN)
        self.assertEqual(result.selection.status, StrategySelectionStatus.REJECTED)
        self.assertEqual(result.selection.notes, ("unknown strategy mode",))

    def test_pipeline_does_not_convert_selected_commitments_to_actions(self) -> None:
        state = two_player_pipeline_state()

        with (
            patch(
                "ow_planner.actions.mission_candidate_to_actions",
                side_effect=AssertionError("mission_candidate_to_actions called"),
            ) as mission_candidate_to_actions,
            patch(
                "ow_planner.actions.mission_candidate_to_orders",
                side_effect=AssertionError("mission_candidate_to_orders called"),
            ) as mission_candidate_to_orders,
            patch("agents.runtime_planner.generate_candidates", return_value=()),
            patch(
                "agents.runtime_planner.evaluate_and_score_candidates",
                return_value=(),
            ),
            patch("agents.runtime_planner.evaluate_responses", return_value=()),
            patch(
                "agents.runtime_planner.commitment_options_for_candidates",
                return_value=(),
            ),
            patch("agents.runtime_planner.planner_decision_bundles", return_value=()),
        ):
            result = run_planner_pipeline(state)

        self.assertEqual(result.bundles, ())
        mission_candidate_to_actions.assert_not_called()
        mission_candidate_to_orders.assert_not_called()

    def test_agent_remains_no_action_and_does_not_call_pipeline(self) -> None:
        with patch(
            "agents.runtime_planner.run_planner_pipeline",
            side_effect=AssertionError("run_planner_pipeline called"),
        ) as pipeline:
            result = agent({}, {})

        self.assertEqual(result, [])
        pipeline.assert_not_called()


if __name__ == "__main__":
    unittest.main()
