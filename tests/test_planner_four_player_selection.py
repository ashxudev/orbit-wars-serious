"""Tests for Strategy Modes Cycle 7 first-pass four-player selection."""

from __future__ import annotations

import copy
import importlib
import unittest
from dataclasses import FrozenInstanceError
from unittest.mock import patch

from ow_planner import (
    CandidateCommitmentOptions,
    CandidateOutcome,
    CommitmentOption,
    CommitmentOptionStatus,
    CommitmentOptionType,
    FourPlayerBoardFacts,
    FourPlayerSelectionConfig,
    FourPlayerStandingFacts,
    LaunchCandidate,
    MissionCandidate,
    MissionEvaluation,
    MissionEvaluationFacts,
    MissionResponseEvaluation,
    MissionResponseFacts,
    MissionType,
    MissionValueFacts,
    PlannerDecisionBundle,
    ResponseSummaryFacts,
    StrategyMode,
    StrategyModeFacts,
    StrategySelectionStatus,
    select_four_player_strategy,
)


def board_facts(
    *,
    is_four_player_mode: bool = True,
    player_id: int | None = 0,
    survival_pressure: bool | None = False,
) -> FourPlayerBoardFacts:
    strategy_mode = StrategyModeFacts(
        mode=StrategyMode.FOUR_PLAYER if is_four_player_mode else StrategyMode.TWO_PLAYER,
        player_id=player_id,
        active_player_ids=(0, 1, 2, 3) if is_four_player_mode else (0, 1),
        opponent_player_ids=(1, 2, 3) if is_four_player_mode else (1,),
        player_count=4 if is_four_player_mode else 2,
    )
    standings = (
        FourPlayerStandingFacts(
            player_id=0,
            production=3,
            total_ships=20,
            production_rank=3,
            total_ship_rank=3,
            is_current_player=player_id == 0,
        ),
        FourPlayerStandingFacts(
            player_id=1,
            production=4,
            total_ships=18,
            production_rank=2,
            total_ship_rank=4,
            is_current_player=player_id == 1,
        ),
        FourPlayerStandingFacts(
            player_id=2,
            production=8,
            total_ships=30,
            production_rank=1,
            total_ship_rank=2,
            is_current_player=player_id == 2,
            is_production_leader=True,
        ),
        FourPlayerStandingFacts(
            player_id=3,
            production=2,
            total_ships=50,
            production_rank=4,
            total_ship_rank=1,
            is_current_player=player_id == 3,
            is_total_ship_leader=True,
        ),
    )
    return FourPlayerBoardFacts(
        strategy_mode_facts=strategy_mode,
        is_four_player_mode=is_four_player_mode,
        player_id=player_id,
        active_player_ids=strategy_mode.active_player_ids,
        standings=standings,
        current_player_standing=next(
            (standing for standing in standings if standing.player_id == player_id),
            None,
        ),
        production_leader_player_id=2,
        total_ship_leader_player_id=3,
        survival_pressure=survival_pressure,
    )


def mission_candidate(
    target_planet_id: int,
    source_planet_id: int,
    ships: int = 6,
) -> MissionCandidate:
    launch = LaunchCandidate(
        source_planet_id=source_planet_id,
        angle=0.25,
        ships=ships,
        player_id=0,
    )
    return MissionCandidate(
        mission_type=MissionType.ATTACK_ENEMY,
        target_planet_id=target_planet_id,
        source_planet_ids=(source_planet_id,),
        launches=(launch,),
        outcome=CandidateOutcome.VALIDATED,
    )


def mission_value_facts(
    *,
    target_owner_baseline: int,
    target_owner_mission: int,
    target_production_before: int,
    production_delta_vs_baseline: int,
    target_ship_delta_vs_baseline: int = 0,
    total_source_ship_delta_vs_baseline: int = 0,
    ships_spent: int = 6,
) -> MissionValueFacts:
    return MissionValueFacts(
        target_owner_before=target_owner_baseline,
        target_owner_baseline=target_owner_baseline,
        target_owner_mission=target_owner_mission,
        target_captured_by_player=target_owner_mission == 0,
        target_production_before=target_production_before,
        production_delta_vs_baseline=production_delta_vs_baseline,
        target_ship_delta_vs_baseline=target_ship_delta_vs_baseline,
        total_source_ship_delta_vs_baseline=total_source_ship_delta_vs_baseline,
        ships_spent=ships_spent,
        mission_valid_for_value=True,
    )


def mission_evaluation(
    candidate: MissionCandidate,
    value_facts: MissionValueFacts | None,
    *,
    total_score: float | None,
) -> MissionEvaluation:
    facts = None
    if value_facts is not None:
        facts = MissionEvaluationFacts(
            mission_type=candidate.mission_type,
            target_planet_id=candidate.target_planet_id,
            source_planet_ids=candidate.source_planet_ids,
            launch_count=len(candidate.launches),
            ships_spent=sum(launch.ships for launch in candidate.launches),
            launch_angles=tuple(launch.angle for launch in candidate.launches),
            candidate_outcome=candidate.outcome,
            value_facts=value_facts,
        )
    return MissionEvaluation(
        candidate=candidate,
        facts=facts,
        total_score=total_score,
    )


def commitment_option(
    candidate: MissionCandidate,
    option_type: CommitmentOptionType,
    *,
    status: CommitmentOptionStatus = CommitmentOptionStatus.VALIDATED,
) -> CommitmentOption:
    return CommitmentOption(
        option_type=option_type,
        candidate=candidate,
        launches=candidate.launches,
        source_planet_ids=candidate.source_planet_ids,
        ships_committed=sum(launch.ships for launch in candidate.launches),
        status=status,
        note=option_type.value,
    )


def bundle_for(
    *,
    target_planet_id: int,
    source_planet_id: int,
    value_facts: MissionValueFacts | None,
    total_score: float | None,
    third_party_benefit_possible: bool = False,
    source_counterattack_risk: bool = False,
    option_types: tuple[CommitmentOptionType, ...] = (
        CommitmentOptionType.MINIMUM_CAPTURE,
    ),
    option_status: CommitmentOptionStatus = CommitmentOptionStatus.VALIDATED,
) -> PlannerDecisionBundle:
    candidate = mission_candidate(target_planet_id, source_planet_id)
    evaluation = mission_evaluation(candidate, value_facts, total_score=total_score)
    options = tuple(
        commitment_option(candidate, option_type, status=option_status)
        for option_type in option_types
    )
    labels = []
    if third_party_benefit_possible:
        labels.append("third_party_benefit_possible")
    if source_counterattack_risk:
        labels.append("source_counterattack_risk")
    return PlannerDecisionBundle(
        candidate=candidate,
        evaluation=evaluation,
        response_evaluation=MissionResponseEvaluation(
            evaluation=evaluation,
            facts=MissionResponseFacts(
                response_summary=ResponseSummaryFacts(
                    labels=tuple(labels),
                    third_party_benefit_possible=third_party_benefit_possible,
                    source_counterattack_risk=source_counterattack_risk,
                ),
            ),
        ),
        commitment_options=CandidateCommitmentOptions(
            candidate=candidate,
            options=options,
        ),
    )


class PlannerFourPlayerSelectionTests(unittest.TestCase):
    def test_four_player_selection_module_imports_and_exports_are_available(
        self,
    ) -> None:
        importlib.import_module("ow_planner.four_player_selection")

        self.assertIs(FourPlayerSelectionConfig, FourPlayerSelectionConfig)
        self.assertIsNotNone(select_four_player_strategy)

    def test_four_player_selection_config_defaults_are_stable_and_frozen(self) -> None:
        config = FourPlayerSelectionConfig()

        self.assertEqual(config.minimum_total_score, 0.0)
        self.assertFalse(config.allow_source_counterattack_risk)
        self.assertFalse(config.allow_third_party_benefit)
        self.assertEqual(
            config.commitment_preference_order,
            (
                CommitmentOptionType.RESERVE_PRESERVING,
                CommitmentOptionType.MINIMUM_CAPTURE,
                CommitmentOptionType.CAPTURE_AND_HOLD,
                CommitmentOptionType.COORDINATED_MULTI_SOURCE,
                CommitmentOptionType.FULL_SOURCE,
            ),
        )
        self.assertTrue(hasattr(FourPlayerSelectionConfig, "__slots__"))
        with self.assertRaises(FrozenInstanceError):
            config.minimum_total_score = 1.0

    def test_invalid_config_values_raise_value_error(self) -> None:
        invalid_configs = (
            {"minimum_total_score": True},
            {"minimum_total_score": float("nan")},
            {"allow_source_counterattack_risk": 1},
            {"allow_third_party_benefit": 1},
            {"commitment_preference_order": (CommitmentOptionType.NO_ATTACK, "bad")},
        )

        for kwargs in invalid_configs:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    FourPlayerSelectionConfig(**kwargs)

    def test_selects_production_leader_target_over_neutral_target(self) -> None:
        production_leader = bundle_for(
            target_planet_id=2,
            source_planet_id=1,
            value_facts=mission_value_facts(
                target_owner_baseline=2,
                target_owner_mission=0,
                target_production_before=8,
                production_delta_vs_baseline=8,
            ),
            total_score=1.0,
        )
        neutral = bundle_for(
            target_planet_id=3,
            source_planet_id=4,
            value_facts=mission_value_facts(
                target_owner_baseline=-1,
                target_owner_mission=0,
                target_production_before=20,
                production_delta_vs_baseline=20,
            ),
            total_score=50.0,
        )

        result = select_four_player_strategy(
            (neutral, production_leader),
            board_facts(),
        )

        self.assertEqual(result.status, StrategySelectionStatus.SELECTED)
        self.assertIs(result.selected_bundle, production_leader)
        self.assertIs(
            result.selected_commitment_option,
            production_leader.commitment_options.options[0],
        )
        self.assertEqual(
            result.notes,
            (
                "four-player strategy selected",
                "selected commitment option: minimum_capture",
                "production leader target",
            ),
        )

    def test_selects_total_ship_leader_when_no_production_leader_target_exists(
        self,
    ) -> None:
        total_ship_leader = bundle_for(
            target_planet_id=2,
            source_planet_id=1,
            value_facts=mission_value_facts(
                target_owner_baseline=3,
                target_owner_mission=0,
                target_production_before=2,
                production_delta_vs_baseline=2,
            ),
            total_score=1.0,
        )
        neutral = bundle_for(
            target_planet_id=3,
            source_planet_id=4,
            value_facts=mission_value_facts(
                target_owner_baseline=-1,
                target_owner_mission=0,
                target_production_before=20,
                production_delta_vs_baseline=20,
            ),
            total_score=50.0,
        )

        result = select_four_player_strategy((neutral, total_ship_leader), board_facts())

        self.assertEqual(result.status, StrategySelectionStatus.SELECTED)
        self.assertIs(result.selected_bundle, total_ship_leader)
        self.assertEqual(
            result.notes,
            (
                "four-player strategy selected",
                "selected commitment option: minimum_capture",
                "total ship leader target",
            ),
        )

    def test_ranks_by_leader_production_denied(self) -> None:
        lower_denied = bundle_for(
            target_planet_id=2,
            source_planet_id=1,
            value_facts=mission_value_facts(
                target_owner_baseline=2,
                target_owner_mission=0,
                target_production_before=4,
                production_delta_vs_baseline=4,
            ),
            total_score=100.0,
        )
        higher_denied = bundle_for(
            target_planet_id=3,
            source_planet_id=4,
            value_facts=mission_value_facts(
                target_owner_baseline=2,
                target_owner_mission=0,
                target_production_before=9,
                production_delta_vs_baseline=9,
            ),
            total_score=1.0,
        )

        result = select_four_player_strategy((lower_denied, higher_denied), board_facts())

        self.assertIs(result.selected_bundle, higher_denied)

    def test_ranks_by_total_score_when_stronger_four_player_facts_tie(self) -> None:
        lower_score = bundle_for(
            target_planet_id=2,
            source_planet_id=1,
            value_facts=mission_value_facts(
                target_owner_baseline=2,
                target_owner_mission=0,
                target_production_before=6,
                production_delta_vs_baseline=6,
            ),
            total_score=3.0,
        )
        higher_score = bundle_for(
            target_planet_id=3,
            source_planet_id=4,
            value_facts=mission_value_facts(
                target_owner_baseline=2,
                target_owner_mission=0,
                target_production_before=6,
                production_delta_vs_baseline=6,
            ),
            total_score=8.0,
        )

        result = select_four_player_strategy((lower_score, higher_score), board_facts())

        self.assertIs(result.selected_bundle, higher_score)

    def test_input_order_breaks_complete_ties(self) -> None:
        first = bundle_for(
            target_planet_id=2,
            source_planet_id=1,
            value_facts=mission_value_facts(
                target_owner_baseline=2,
                target_owner_mission=0,
                target_production_before=6,
                production_delta_vs_baseline=6,
            ),
            total_score=8.0,
        )
        second = bundle_for(
            target_planet_id=3,
            source_planet_id=4,
            value_facts=mission_value_facts(
                target_owner_baseline=2,
                target_owner_mission=0,
                target_production_before=6,
                production_delta_vs_baseline=6,
            ),
            total_score=8.0,
        )

        result = select_four_player_strategy((first, second), board_facts())

        self.assertIs(result.selected_bundle, first)

    def test_excludes_source_counterattack_risk_by_default(self) -> None:
        risky = bundle_for(
            target_planet_id=2,
            source_planet_id=1,
            value_facts=mission_value_facts(
                target_owner_baseline=2,
                target_owner_mission=0,
                target_production_before=8,
                production_delta_vs_baseline=8,
            ),
            total_score=50.0,
            source_counterattack_risk=True,
        )
        safe = bundle_for(
            target_planet_id=3,
            source_planet_id=4,
            value_facts=mission_value_facts(
                target_owner_baseline=1,
                target_owner_mission=0,
                target_production_before=1,
                production_delta_vs_baseline=1,
            ),
            total_score=1.0,
        )

        result = select_four_player_strategy((risky, safe), board_facts())

        self.assertIs(result.selected_bundle, safe)

    def test_allows_source_counterattack_risk_when_configured(self) -> None:
        risky = bundle_for(
            target_planet_id=2,
            source_planet_id=1,
            value_facts=mission_value_facts(
                target_owner_baseline=2,
                target_owner_mission=0,
                target_production_before=8,
                production_delta_vs_baseline=8,
            ),
            total_score=50.0,
            source_counterattack_risk=True,
        )

        result = select_four_player_strategy(
            (risky,),
            board_facts(),
            config=FourPlayerSelectionConfig(allow_source_counterattack_risk=True),
        )

        self.assertEqual(result.status, StrategySelectionStatus.SELECTED)
        self.assertIs(result.selected_bundle, risky)

    def test_excludes_third_party_benefit_by_default(self) -> None:
        third_party = bundle_for(
            target_planet_id=2,
            source_planet_id=1,
            value_facts=mission_value_facts(
                target_owner_baseline=2,
                target_owner_mission=0,
                target_production_before=8,
                production_delta_vs_baseline=8,
            ),
            total_score=50.0,
            third_party_benefit_possible=True,
        )
        safe = bundle_for(
            target_planet_id=3,
            source_planet_id=4,
            value_facts=mission_value_facts(
                target_owner_baseline=1,
                target_owner_mission=0,
                target_production_before=1,
                production_delta_vs_baseline=1,
            ),
            total_score=1.0,
        )

        result = select_four_player_strategy((third_party, safe), board_facts())

        self.assertIs(result.selected_bundle, safe)

    def test_allows_third_party_benefit_when_configured(self) -> None:
        third_party = bundle_for(
            target_planet_id=2,
            source_planet_id=1,
            value_facts=mission_value_facts(
                target_owner_baseline=2,
                target_owner_mission=0,
                target_production_before=8,
                production_delta_vs_baseline=8,
            ),
            total_score=50.0,
            third_party_benefit_possible=True,
        )

        result = select_four_player_strategy(
            (third_party,),
            board_facts(),
            config=FourPlayerSelectionConfig(allow_third_party_benefit=True),
        )

        self.assertEqual(result.status, StrategySelectionStatus.SELECTED)
        self.assertIs(result.selected_bundle, third_party)

    def test_threshold_rejection_returns_no_action(self) -> None:
        bundle = bundle_for(
            target_planet_id=2,
            source_planet_id=1,
            value_facts=mission_value_facts(
                target_owner_baseline=2,
                target_owner_mission=0,
                target_production_before=6,
                production_delta_vs_baseline=6,
            ),
            total_score=2.0,
        )

        result = select_four_player_strategy(
            (bundle,),
            board_facts(),
            config=FourPlayerSelectionConfig(minimum_total_score=5.0),
        )

        self.assertEqual(result.status, StrategySelectionStatus.NO_ACTION)
        self.assertEqual(
            result.notes,
            (
                "no eligible four-player strategy",
                "below minimum total score",
            ),
        )

    def test_selects_preferred_validated_commitment_option_by_configured_order(
        self,
    ) -> None:
        bundle = bundle_for(
            target_planet_id=2,
            source_planet_id=1,
            value_facts=mission_value_facts(
                target_owner_baseline=2,
                target_owner_mission=0,
                target_production_before=6,
                production_delta_vs_baseline=6,
            ),
            total_score=8.0,
            option_types=(
                CommitmentOptionType.FULL_SOURCE,
                CommitmentOptionType.RESERVE_PRESERVING,
                CommitmentOptionType.MINIMUM_CAPTURE,
            ),
        )

        default_result = select_four_player_strategy((bundle,), board_facts())
        custom_result = select_four_player_strategy(
            (bundle,),
            board_facts(),
            config=FourPlayerSelectionConfig(
                commitment_preference_order=(CommitmentOptionType.FULL_SOURCE,),
            ),
        )

        self.assertIs(
            default_result.selected_commitment_option,
            bundle.commitment_options.options[1],
        )
        self.assertIs(
            custom_result.selected_commitment_option,
            bundle.commitment_options.options[0],
        )

    def test_no_action_when_no_validated_non_no_attack_commitment_exists(self) -> None:
        no_attack_only = bundle_for(
            target_planet_id=2,
            source_planet_id=1,
            value_facts=mission_value_facts(
                target_owner_baseline=2,
                target_owner_mission=0,
                target_production_before=6,
                production_delta_vs_baseline=6,
            ),
            total_score=8.0,
            option_types=(CommitmentOptionType.NO_ATTACK,),
        )
        rejected_attack = bundle_for(
            target_planet_id=3,
            source_planet_id=4,
            value_facts=mission_value_facts(
                target_owner_baseline=1,
                target_owner_mission=0,
                target_production_before=5,
                production_delta_vs_baseline=5,
            ),
            total_score=10.0,
            option_types=(CommitmentOptionType.MINIMUM_CAPTURE,),
            option_status=CommitmentOptionStatus.REJECTED,
        )

        result = select_four_player_strategy(
            (no_attack_only, rejected_attack),
            board_facts(),
        )

        self.assertEqual(result.status, StrategySelectionStatus.NO_ACTION)
        self.assertEqual(
            result.notes,
            (
                "no eligible four-player strategy",
                "missing validated commitment option",
            ),
        )

    def test_no_action_when_only_current_player_owned_or_uncaptured_targets_exist(
        self,
    ) -> None:
        already_owned = bundle_for(
            target_planet_id=2,
            source_planet_id=1,
            value_facts=mission_value_facts(
                target_owner_baseline=0,
                target_owner_mission=0,
                target_production_before=2,
                production_delta_vs_baseline=0,
            ),
            total_score=8.0,
        )
        not_captured = bundle_for(
            target_planet_id=3,
            source_planet_id=4,
            value_facts=mission_value_facts(
                target_owner_baseline=1,
                target_owner_mission=1,
                target_production_before=5,
                production_delta_vs_baseline=0,
            ),
            total_score=10.0,
        )

        result = select_four_player_strategy(
            (already_owned, not_captured),
            board_facts(),
        )

        self.assertEqual(result.status, StrategySelectionStatus.NO_ACTION)
        self.assertEqual(result.notes, ("no eligible four-player strategy",))

    def test_rejected_result_for_empty_inputs(self) -> None:
        board = board_facts()

        result = select_four_player_strategy((), board)

        self.assertEqual(result.status, StrategySelectionStatus.REJECTED)
        self.assertIs(result.strategy_mode_facts, board.strategy_mode_facts)
        self.assertEqual(result.notes, ("no bundles",))

    def test_rejected_result_for_missing_board_facts(self) -> None:
        bundle = bundle_for(
            target_planet_id=2,
            source_planet_id=1,
            value_facts=mission_value_facts(
                target_owner_baseline=2,
                target_owner_mission=0,
                target_production_before=6,
                production_delta_vs_baseline=6,
            ),
            total_score=8.0,
        )

        result = select_four_player_strategy((bundle,), None)

        self.assertEqual(result.status, StrategySelectionStatus.REJECTED)
        self.assertEqual(result.notes, ("missing board facts",))

    def test_rejected_result_for_non_four_player_board_facts(self) -> None:
        board = board_facts(is_four_player_mode=False)
        bundle = bundle_for(
            target_planet_id=2,
            source_planet_id=1,
            value_facts=mission_value_facts(
                target_owner_baseline=2,
                target_owner_mission=0,
                target_production_before=6,
                production_delta_vs_baseline=6,
            ),
            total_score=8.0,
        )

        result = select_four_player_strategy((bundle,), board)

        self.assertEqual(result.status, StrategySelectionStatus.REJECTED)
        self.assertIs(result.strategy_mode_facts, board.strategy_mode_facts)
        self.assertEqual(result.notes, ("not four-player mode",))

    def test_rejected_result_when_no_complete_four_player_facts_exist(self) -> None:
        incomplete = bundle_for(
            target_planet_id=2,
            source_planet_id=1,
            value_facts=mission_value_facts(
                target_owner_baseline=2,
                target_owner_mission=0,
                target_production_before=6,
                production_delta_vs_baseline=6,
            ),
            total_score=8.0,
        )
        incomplete = PlannerDecisionBundle(
            candidate=incomplete.candidate,
            evaluation=MissionEvaluation(
                candidate=incomplete.candidate,
                facts=None,
                total_score=8.0,
            ),
            response_evaluation=incomplete.response_evaluation,
            commitment_options=incomplete.commitment_options,
        )
        board = board_facts()

        result = select_four_player_strategy((incomplete,), board)

        self.assertEqual(result.status, StrategySelectionStatus.REJECTED)
        self.assertIs(result.strategy_mode_facts, board.strategy_mode_facts)
        self.assertEqual(result.notes, ("no complete four-player facts",))

    def test_selection_does_not_mutate_bundles_board_or_options(self) -> None:
        board = board_facts()
        bundle = bundle_for(
            target_planet_id=2,
            source_planet_id=1,
            value_facts=mission_value_facts(
                target_owner_baseline=2,
                target_owner_mission=0,
                target_production_before=6,
                production_delta_vs_baseline=6,
            ),
            total_score=8.0,
            option_types=(
                CommitmentOptionType.RESERVE_PRESERVING,
                CommitmentOptionType.MINIMUM_CAPTURE,
            ),
        )
        before = (copy.deepcopy(board), copy.deepcopy(bundle))

        select_four_player_strategy((bundle,), board)

        self.assertEqual((board, bundle), before)

    def test_selection_does_not_call_deferred_planner_or_simulator_logic(self) -> None:
        board = board_facts()
        bundle = bundle_for(
            target_planet_id=2,
            source_planet_id=1,
            value_facts=mission_value_facts(
                target_owner_baseline=2,
                target_owner_mission=0,
                target_production_before=6,
                production_delta_vs_baseline=6,
            ),
            total_score=8.0,
        )

        with (
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
            result = select_four_player_strategy((bundle,), board)

        self.assertEqual(result.status, StrategySelectionStatus.SELECTED)


if __name__ == "__main__":
    unittest.main()
