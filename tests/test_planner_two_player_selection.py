"""Tests for Strategy Modes Cycle 4 two-player direct-advantage selection."""

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
    TwoPlayerSelectionConfig,
    TwoPlayerPressureFacts,
    select_two_player_direct_advantage,
    two_player_advantage_facts,
    two_player_pressure_facts,
)


def strategy_facts(
    *,
    mode: StrategyMode = StrategyMode.TWO_PLAYER,
    player_id: int | None = 0,
    opponent_player_ids: tuple[int, ...] = (1,),
) -> StrategyModeFacts:
    active_player_ids = (
        (player_id,) if player_id is not None else ()
    ) + opponent_player_ids
    return StrategyModeFacts(
        mode=mode,
        player_id=player_id,
        active_player_ids=tuple(sorted(active_player_ids)),
        opponent_player_ids=opponent_player_ids,
        player_count=len(tuple(sorted(active_player_ids))),
    )


def mission_candidate(
    target_planet_id: int,
    source_planet_id: int,
    ships: int = 5,
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


def value_facts(
    *,
    target_owner_baseline: int,
    target_owner_mission: int,
    target_production_before: int,
    production_delta_vs_baseline: int,
    target_ship_delta_vs_baseline: int = 0,
    total_source_ship_delta_vs_baseline: int = 0,
    ships_spent: int = 5,
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
    mission_value_facts: MissionValueFacts | None,
    *,
    total_score: float | None,
) -> MissionEvaluation:
    facts = None
    if mission_value_facts is not None:
        facts = MissionEvaluationFacts(
            mission_type=candidate.mission_type,
            target_planet_id=candidate.target_planet_id,
            source_planet_ids=candidate.source_planet_ids,
            launch_count=len(candidate.launches),
            ships_spent=sum(launch.ships for launch in candidate.launches),
            launch_angles=tuple(launch.angle for launch in candidate.launches),
            candidate_outcome=candidate.outcome,
            value_facts=mission_value_facts,
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
    mission_value_facts: MissionValueFacts,
    total_score: float,
    strategy_mode_facts: StrategyModeFacts | None = None,
    source_counterattack_risk: bool = False,
    response_labels: tuple[str, ...] = (),
    option_types: tuple[CommitmentOptionType, ...] = (
        CommitmentOptionType.MINIMUM_CAPTURE,
    ),
    option_status: CommitmentOptionStatus = CommitmentOptionStatus.VALIDATED,
) -> PlannerDecisionBundle:
    candidate = mission_candidate(target_planet_id, source_planet_id)
    evaluation = mission_evaluation(
        candidate,
        mission_value_facts,
        total_score=total_score,
    )
    options = tuple(
        commitment_option(candidate, option_type, status=option_status)
        for option_type in option_types
    )
    return PlannerDecisionBundle(
        candidate=candidate,
        strategy_mode_facts=strategy_mode_facts or strategy_facts(),
        evaluation=evaluation,
        response_evaluation=MissionResponseEvaluation(
            evaluation=evaluation,
            facts=MissionResponseFacts(
                response_labels=response_labels,
                response_summary=ResponseSummaryFacts(
                    labels=response_labels,
                    source_counterattack_risk=source_counterattack_risk,
                ),
            ),
        ),
        commitment_options=CandidateCommitmentOptions(
            candidate=candidate,
            options=options,
        ),
    )


class PlannerTwoPlayerSelectionTests(unittest.TestCase):
    def test_two_player_selection_module_imports_and_exports_are_available(self) -> None:
        importlib.import_module("ow_planner.two_player_selection")

        self.assertIs(TwoPlayerSelectionConfig, TwoPlayerSelectionConfig)
        self.assertIsNotNone(select_two_player_direct_advantage)

    def test_two_player_selection_config_defaults_are_stable_and_frozen(self) -> None:
        config = TwoPlayerSelectionConfig()

        self.assertEqual(config.minimum_total_score, 0.0)
        self.assertFalse(config.allow_source_counterattack_risk)
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
        self.assertTrue(hasattr(TwoPlayerSelectionConfig, "__slots__"))
        with self.assertRaises(FrozenInstanceError):
            config.minimum_total_score = 1.0

    def test_selects_opponent_owned_capture_over_neutral_capture(self) -> None:
        opponent_bundle = bundle_for(
            target_planet_id=2,
            source_planet_id=1,
            mission_value_facts=value_facts(
                target_owner_baseline=1,
                target_owner_mission=0,
                target_production_before=3,
                production_delta_vs_baseline=3,
            ),
            total_score=1.0,
        )
        neutral_bundle = bundle_for(
            target_planet_id=3,
            source_planet_id=4,
            mission_value_facts=value_facts(
                target_owner_baseline=-1,
                target_owner_mission=0,
                target_production_before=10,
                production_delta_vs_baseline=10,
            ),
            total_score=20.0,
        )

        result = select_two_player_direct_advantage((neutral_bundle, opponent_bundle))

        self.assertEqual(result.status, StrategySelectionStatus.SELECTED)
        self.assertIs(result.selected_bundle, opponent_bundle)
        self.assertIs(
            result.selected_commitment_option,
            opponent_bundle.commitment_options.options[0],
        )
        self.assertEqual(
            result.notes,
            (
                "two-player direct advantage selected",
                "selected commitment option: minimum_capture",
            ),
        )

    def test_ranks_by_opponent_production_denied(self) -> None:
        lower_denied = bundle_for(
            target_planet_id=2,
            source_planet_id=1,
            mission_value_facts=value_facts(
                target_owner_baseline=1,
                target_owner_mission=0,
                target_production_before=2,
                production_delta_vs_baseline=2,
            ),
            total_score=50.0,
        )
        higher_denied = bundle_for(
            target_planet_id=3,
            source_planet_id=4,
            mission_value_facts=value_facts(
                target_owner_baseline=1,
                target_owner_mission=0,
                target_production_before=6,
                production_delta_vs_baseline=6,
            ),
            total_score=1.0,
        )

        result = select_two_player_direct_advantage((lower_denied, higher_denied))

        self.assertIs(result.selected_bundle, higher_denied)

    def test_ranks_by_total_score_when_stronger_advantage_facts_tie(self) -> None:
        lower_score = bundle_for(
            target_planet_id=2,
            source_planet_id=1,
            mission_value_facts=value_facts(
                target_owner_baseline=1,
                target_owner_mission=0,
                target_production_before=4,
                production_delta_vs_baseline=4,
            ),
            total_score=3.0,
        )
        higher_score = bundle_for(
            target_planet_id=3,
            source_planet_id=4,
            mission_value_facts=value_facts(
                target_owner_baseline=1,
                target_owner_mission=0,
                target_production_before=4,
                production_delta_vs_baseline=4,
            ),
            total_score=8.0,
        )

        result = select_two_player_direct_advantage((lower_score, higher_score))

        self.assertIs(result.selected_bundle, higher_score)

    def test_input_order_breaks_complete_ties(self) -> None:
        first = bundle_for(
            target_planet_id=2,
            source_planet_id=1,
            mission_value_facts=value_facts(
                target_owner_baseline=1,
                target_owner_mission=0,
                target_production_before=4,
                production_delta_vs_baseline=4,
            ),
            total_score=5.0,
        )
        second = bundle_for(
            target_planet_id=3,
            source_planet_id=4,
            mission_value_facts=value_facts(
                target_owner_baseline=1,
                target_owner_mission=0,
                target_production_before=4,
                production_delta_vs_baseline=4,
            ),
            total_score=5.0,
        )

        result = select_two_player_direct_advantage((first, second))

        self.assertIs(result.selected_bundle, first)

    def test_excludes_source_counterattack_risk_by_default(self) -> None:
        risky = bundle_for(
            target_planet_id=2,
            source_planet_id=1,
            mission_value_facts=value_facts(
                target_owner_baseline=1,
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
            mission_value_facts=value_facts(
                target_owner_baseline=1,
                target_owner_mission=0,
                target_production_before=1,
                production_delta_vs_baseline=1,
            ),
            total_score=1.0,
        )

        result = select_two_player_direct_advantage((risky, safe))

        self.assertIs(result.selected_bundle, safe)

    def test_allows_source_counterattack_risk_when_configured(self) -> None:
        risky = bundle_for(
            target_planet_id=2,
            source_planet_id=1,
            mission_value_facts=value_facts(
                target_owner_baseline=1,
                target_owner_mission=0,
                target_production_before=8,
                production_delta_vs_baseline=8,
            ),
            total_score=50.0,
            source_counterattack_risk=True,
        )

        result = select_two_player_direct_advantage(
            (risky,),
            config=TwoPlayerSelectionConfig(allow_source_counterattack_risk=True),
        )

        self.assertEqual(result.status, StrategySelectionStatus.SELECTED)
        self.assertIs(result.selected_bundle, risky)

    def test_threshold_rejection_returns_no_action(self) -> None:
        bundle = bundle_for(
            target_planet_id=2,
            source_planet_id=1,
            mission_value_facts=value_facts(
                target_owner_baseline=1,
                target_owner_mission=0,
                target_production_before=4,
                production_delta_vs_baseline=4,
            ),
            total_score=2.0,
        )

        result = select_two_player_direct_advantage(
            (bundle,),
            config=TwoPlayerSelectionConfig(minimum_total_score=5.0),
        )

        self.assertEqual(result.status, StrategySelectionStatus.NO_ACTION)
        self.assertEqual(
            result.notes,
            (
                "no eligible two-player direct advantage",
                "below minimum total score",
            ),
        )

    def test_selects_preferred_validated_commitment_option_by_configured_order(
        self,
    ) -> None:
        bundle = bundle_for(
            target_planet_id=2,
            source_planet_id=1,
            mission_value_facts=value_facts(
                target_owner_baseline=1,
                target_owner_mission=0,
                target_production_before=4,
                production_delta_vs_baseline=4,
            ),
            total_score=8.0,
            option_types=(
                CommitmentOptionType.FULL_SOURCE,
                CommitmentOptionType.RESERVE_PRESERVING,
                CommitmentOptionType.MINIMUM_CAPTURE,
            ),
        )

        default_result = select_two_player_direct_advantage((bundle,))
        custom_result = select_two_player_direct_advantage(
            (bundle,),
            config=TwoPlayerSelectionConfig(
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

    def test_two_player_pressure_facts_mark_reserve_preserving_pressure_option(
        self,
    ) -> None:
        bundle = bundle_for(
            target_planet_id=2,
            source_planet_id=1,
            mission_value_facts=value_facts(
                target_owner_baseline=1,
                target_owner_mission=0,
                target_production_before=4,
                production_delta_vs_baseline=4,
            ),
            total_score=8.0,
            response_labels=("target_race_risk",),
            option_types=(CommitmentOptionType.RESERVE_PRESERVING,),
        )

        facts = two_player_advantage_facts(bundle)
        pressure_facts = two_player_pressure_facts(
            facts,
            bundle.commitment_options.options[0],
        )

        self.assertIsInstance(pressure_facts, TwoPlayerPressureFacts)
        self.assertTrue(pressure_facts.response_pressure_active)
        self.assertTrue(pressure_facts.reserve_preserving_commitment)
        self.assertEqual(pressure_facts.pressure_labels, ("target_race_risk",))
        self.assertEqual(
            pressure_facts.notes,
            ("pressure reserve-preserving option",),
        )

    def test_pressure_selection_prefers_reserve_preserving_over_higher_score_minimum(
        self,
    ) -> None:
        reserve_preserving = bundle_for(
            target_planet_id=2,
            source_planet_id=1,
            mission_value_facts=value_facts(
                target_owner_baseline=1,
                target_owner_mission=0,
                target_production_before=3,
                production_delta_vs_baseline=3,
            ),
            total_score=2.0,
            response_labels=("target_race_risk",),
            option_types=(CommitmentOptionType.RESERVE_PRESERVING,),
        )
        higher_score_minimum = bundle_for(
            target_planet_id=3,
            source_planet_id=4,
            mission_value_facts=value_facts(
                target_owner_baseline=1,
                target_owner_mission=0,
                target_production_before=3,
                production_delta_vs_baseline=3,
            ),
            total_score=50.0,
            response_labels=("target_race_risk",),
            option_types=(CommitmentOptionType.MINIMUM_CAPTURE,),
        )

        result = select_two_player_direct_advantage(
            (higher_score_minimum, reserve_preserving)
        )

        self.assertEqual(result.status, StrategySelectionStatus.SELECTED)
        self.assertIs(result.selected_bundle, reserve_preserving)
        self.assertIs(
            result.selected_commitment_option,
            reserve_preserving.commitment_options.options[0],
        )
        self.assertEqual(
            result.notes,
            (
                "two-player direct advantage selected",
                "selected commitment option: reserve_preserving",
                "pressure retention preference: reserve_preserving",
            ),
        )

    def test_no_action_when_no_validated_non_no_attack_commitment_exists(self) -> None:
        no_attack_only = bundle_for(
            target_planet_id=2,
            source_planet_id=1,
            mission_value_facts=value_facts(
                target_owner_baseline=1,
                target_owner_mission=0,
                target_production_before=4,
                production_delta_vs_baseline=4,
            ),
            total_score=8.0,
            option_types=(CommitmentOptionType.NO_ATTACK,),
        )
        rejected_attack = bundle_for(
            target_planet_id=3,
            source_planet_id=4,
            mission_value_facts=value_facts(
                target_owner_baseline=1,
                target_owner_mission=0,
                target_production_before=5,
                production_delta_vs_baseline=5,
            ),
            total_score=10.0,
            option_types=(CommitmentOptionType.MINIMUM_CAPTURE,),
            option_status=CommitmentOptionStatus.REJECTED,
        )

        result = select_two_player_direct_advantage((no_attack_only, rejected_attack))

        self.assertEqual(result.status, StrategySelectionStatus.NO_ACTION)
        self.assertEqual(
            result.notes,
            (
                "no eligible two-player direct advantage",
                "missing validated commitment option",
            ),
        )

    def test_rejected_result_for_empty_inputs(self) -> None:
        result = select_two_player_direct_advantage(())

        self.assertEqual(result.status, StrategySelectionStatus.REJECTED)
        self.assertEqual(result.notes, ("no bundles",))

    def test_rejected_result_for_non_two_player_inputs(self) -> None:
        bundle = bundle_for(
            target_planet_id=2,
            source_planet_id=1,
            mission_value_facts=value_facts(
                target_owner_baseline=1,
                target_owner_mission=0,
                target_production_before=4,
                production_delta_vs_baseline=4,
            ),
            total_score=8.0,
            strategy_mode_facts=strategy_facts(
                mode=StrategyMode.FOUR_PLAYER,
                opponent_player_ids=(1, 2, 3),
            ),
        )

        result = select_two_player_direct_advantage((bundle,))

        self.assertEqual(result.status, StrategySelectionStatus.REJECTED)
        self.assertEqual(result.notes, ("not two-player mode",))

    def test_rejected_result_when_no_complete_two_player_facts_exist(self) -> None:
        incomplete = bundle_for(
            target_planet_id=2,
            source_planet_id=1,
            mission_value_facts=value_facts(
                target_owner_baseline=1,
                target_owner_mission=0,
                target_production_before=4,
                production_delta_vs_baseline=4,
            ),
            total_score=8.0,
            strategy_mode_facts=strategy_facts(player_id=None, opponent_player_ids=()),
        )

        result = select_two_player_direct_advantage((incomplete,))

        self.assertEqual(result.status, StrategySelectionStatus.REJECTED)
        self.assertEqual(result.notes, ("no complete two-player facts",))

    def test_selection_does_not_mutate_bundles_candidates_or_options(self) -> None:
        bundle = bundle_for(
            target_planet_id=2,
            source_planet_id=1,
            mission_value_facts=value_facts(
                target_owner_baseline=1,
                target_owner_mission=0,
                target_production_before=4,
                production_delta_vs_baseline=4,
            ),
            total_score=8.0,
            option_types=(
                CommitmentOptionType.RESERVE_PRESERVING,
                CommitmentOptionType.MINIMUM_CAPTURE,
            ),
        )
        before = copy.deepcopy(bundle)

        select_two_player_direct_advantage((bundle,))

        self.assertEqual(bundle, before)

    def test_selection_does_not_call_deferred_planner_or_simulator_logic(self) -> None:
        bundle = bundle_for(
            target_planet_id=2,
            source_planet_id=1,
            mission_value_facts=value_facts(
                target_owner_baseline=1,
                target_owner_mission=0,
                target_production_before=4,
                production_delta_vs_baseline=4,
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
            result = select_two_player_direct_advantage((bundle,))

        self.assertEqual(result.status, StrategySelectionStatus.SELECTED)


if __name__ == "__main__":
    unittest.main()
