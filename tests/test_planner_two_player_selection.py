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
    EnemyDenialOpportunityReport,
    EnemyDenialTargetFacts,
    LaunchCandidate,
    MissionCandidate,
    MissionEvaluation,
    MissionEvaluationFacts,
    MissionResponseEvaluation,
    MissionResponseFacts,
    MissionType,
    MissionValueFacts,
    OwnTransferIntentReport,
    OwnedPlanetThreatFacts,
    OwnedProductionThreatReport,
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
    mission_type: MissionType = MissionType.ATTACK_ENEMY,
    note: str | None = None,
) -> MissionCandidate:
    launch = LaunchCandidate(
        source_planet_id=source_planet_id,
        angle=0.25,
        ships=ships,
        player_id=0,
    )
    return MissionCandidate(
        mission_type=mission_type,
        target_planet_id=target_planet_id,
        source_planet_ids=(source_planet_id,),
        launches=(launch,),
        outcome=CandidateOutcome.VALIDATED,
        note=note,
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


def owned_pressure_report(
    *,
    pressured_planet_id: int = 1,
    production_pressure_count: int = 1,
) -> OwnedProductionThreatReport:
    planet_facts = ()
    if production_pressure_count > 0:
        planet_facts = (
            OwnedPlanetThreatFacts(
                planet_id=pressured_planet_id,
                owner=0,
                current_ships=5,
                production=3,
                production_bearing=True,
                incoming_enemy_ships=8,
                incoming_friendly_ships=0,
                earliest_hostile_eta=3,
                earliest_friendly_eta=None,
                projected_balance_at_earliest_hostile=-3,
                production_under_pressure=True,
                likely_flip=True,
                at_risk=True,
                outgoing_friendly_fleet_count=0,
                outgoing_friendly_ships=0,
                source_drained_by_outgoing=False,
                labels=(
                    "hostile_inbound",
                    "production_bearing",
                    "owned_production_pressure",
                    "likely_flip",
                    "owned_production_at_risk",
                ),
            ),
        )
    return OwnedProductionThreatReport(
        player_id=0,
        horizon_ticks=80,
        planet_facts=planet_facts,
        production_pressure_count=production_pressure_count,
        threatened_planet_count=1 if production_pressure_count > 0 else 0,
        likely_flip_count=1 if production_pressure_count > 0 else 0,
        production_under_pressure=3 if production_pressure_count > 0 else 0,
        production_at_risk=3 if production_pressure_count > 0 else 0,
        labels=(
            ("owned_production_pressure",)
            if production_pressure_count > 0
            else ()
        ),
    )


def own_transfer_spam_report(
    *,
    spammy_count: int = 1,
) -> OwnTransferIntentReport:
    return OwnTransferIntentReport(
        player_id=0,
        transfer_count=spammy_count,
        potentially_spammy_count=spammy_count,
        repeated_transfer_group_count=1 if spammy_count > 1 else 0,
        labels=(
            ("potentially_spammy_own_transfer",)
            if spammy_count > 0
            else ()
        ),
    )


def enemy_denial_report(
    *,
    high_value_target_ids: tuple[int, ...] = (3,),
) -> EnemyDenialOpportunityReport:
    target_facts = tuple(
        EnemyDenialTargetFacts(
            player_id=0,
            opponent_id=1,
            target_planet_id=target_id,
            target_owner=1,
            target_ships=10,
            target_production=4,
            production_bearing=True,
            owned_source_count=2,
            owned_source_capacity=40,
            sufficient_source_count=1,
            nearest_owned_source_id=1,
            nearest_owned_source_ships=30,
            nearest_owned_source_production=5,
            distance_to_nearest_source=10.0,
            eta_ticks_from_nearest_source=5,
            player_production=12,
            opponent_production=8,
            player_ships=60,
            opponent_ships=30,
            player_ahead_by_production=True,
            player_ahead_by_ships=True,
            plausible_denial=True,
            high_value_denial=True,
            labels=(
                "opponent_production_target",
                "plausible_denial_target",
                "high_value_denial_opportunity",
            ),
        )
        for target_id in high_value_target_ids
    )
    return EnemyDenialOpportunityReport(
        player_id=0,
        opponent_id=1,
        target_facts=target_facts,
        target_count=len(target_facts),
        plausible_denial_count=len(target_facts),
        high_value_denial_count=len(target_facts),
        player_production=12,
        opponent_production=8,
        player_ships=60,
        opponent_ships=30,
        player_ahead_by_production=True,
        player_ahead_by_ships=True,
        labels=(
            "opponent_production_targets",
            "ahead_state",
            "plausible_enemy_denial",
            "high_value_enemy_denial",
        ),
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
    mission_type: MissionType = MissionType.ATTACK_ENEMY,
    candidate_note: str | None = None,
) -> PlannerDecisionBundle:
    candidate = mission_candidate(
        target_planet_id,
        source_planet_id,
        mission_type=mission_type,
        note=candidate_note,
    )
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
        self.assertIsNone(config.owned_production_threat_report)
        self.assertIsNone(config.own_transfer_intent_report)
        self.assertIsNone(config.enemy_denial_opportunity_report)
        self.assertTrue(hasattr(TwoPlayerSelectionConfig, "__slots__"))
        with self.assertRaises(FrozenInstanceError):
            config.minimum_total_score = 1.0

    def test_two_player_selection_config_rejects_invalid_owned_threat_report(
        self,
    ) -> None:
        with self.assertRaisesRegex(ValueError, "owned_production_threat_report"):
            TwoPlayerSelectionConfig(owned_production_threat_report=object())
        with self.assertRaisesRegex(ValueError, "own_transfer_intent_report"):
            TwoPlayerSelectionConfig(own_transfer_intent_report=object())
        with self.assertRaisesRegex(ValueError, "enemy_denial_opportunity_report"):
            TwoPlayerSelectionConfig(enemy_denial_opportunity_report=object())

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

    def test_early_control_pressure_allows_recovery_candidate_below_floor(
        self,
    ) -> None:
        recovery = bundle_for(
            target_planet_id=2,
            source_planet_id=1,
            mission_type=MissionType.CAPTURE_NEUTRAL,
            mission_value_facts=value_facts(
                target_owner_baseline=-1,
                target_owner_mission=-1,
                target_production_before=3,
                production_delta_vs_baseline=0,
                ships_spent=1,
            ),
            total_score=-12.0,
            response_labels=("target_race_risk",),
            option_types=(CommitmentOptionType.RESERVE_PRESERVING,),
            candidate_note="early two-player pressure recovery",
        )

        result = select_two_player_direct_advantage((recovery,))

        self.assertEqual(result.status, StrategySelectionStatus.SELECTED)
        self.assertIs(result.selected_bundle, recovery)
        self.assertEqual(
            result.selected_commitment_option.option_type,
            CommitmentOptionType.RESERVE_PRESERVING,
        )
        self.assertEqual(
            result.notes,
            (
                "two-player direct advantage selected",
                "selected commitment option: reserve_preserving",
                "pressure retention preference: reserve_preserving",
            ),
        )

    def test_early_control_pressure_does_not_globally_lower_score_floor(
        self,
    ) -> None:
        ordinary_below_floor = bundle_for(
            target_planet_id=2,
            source_planet_id=1,
            mission_type=MissionType.CAPTURE_NEUTRAL,
            mission_value_facts=value_facts(
                target_owner_baseline=-1,
                target_owner_mission=-1,
                target_production_before=3,
                production_delta_vs_baseline=0,
                ships_spent=1,
            ),
            total_score=-12.0,
            response_labels=("target_race_risk",),
            option_types=(CommitmentOptionType.RESERVE_PRESERVING,),
        )

        result = select_two_player_direct_advantage((ordinary_below_floor,))

        self.assertEqual(result.status, StrategySelectionStatus.NO_ACTION)
        self.assertIn("below minimum total score", result.notes)

    def test_pressure_selection_prefers_owned_retention_over_higher_score_attack(
        self,
    ) -> None:
        reinforcement = bundle_for(
            target_planet_id=2,
            source_planet_id=1,
            mission_type=MissionType.REINFORCE,
            mission_value_facts=value_facts(
                target_owner_baseline=0,
                target_owner_mission=0,
                target_production_before=5,
                production_delta_vs_baseline=0,
            ),
            total_score=2.0,
            response_labels=("target_race_risk",),
            option_types=(CommitmentOptionType.RESERVE_PRESERVING,),
        )
        higher_score_attack = bundle_for(
            target_planet_id=3,
            source_planet_id=4,
            mission_type=MissionType.ATTACK_ENEMY,
            mission_value_facts=value_facts(
                target_owner_baseline=1,
                target_owner_mission=0,
                target_production_before=8,
                production_delta_vs_baseline=8,
            ),
            total_score=80.0,
            response_labels=("target_race_risk",),
            option_types=(CommitmentOptionType.RESERVE_PRESERVING,),
        )

        result = select_two_player_direct_advantage(
            (higher_score_attack, reinforcement)
        )

        self.assertEqual(result.status, StrategySelectionStatus.SELECTED)
        self.assertIs(result.selected_bundle, reinforcement)
        self.assertEqual(
            result.selected_commitment_option.option_type,
            CommitmentOptionType.RESERVE_PRESERVING,
        )

    def test_risky_capture_prefers_validated_capture_and_hold_commitment(
        self,
    ) -> None:
        risky_capture = bundle_for(
            target_planet_id=2,
            source_planet_id=1,
            mission_type=MissionType.CAPTURE_NEUTRAL,
            mission_value_facts=value_facts(
                target_owner_baseline=-1,
                target_owner_mission=0,
                target_production_before=4,
                production_delta_vs_baseline=4,
            ),
            total_score=20.0,
            response_labels=("target_reinforcement_feasible",),
            option_types=(
                CommitmentOptionType.MINIMUM_CAPTURE,
                CommitmentOptionType.CAPTURE_AND_HOLD,
            ),
        )

        result = select_two_player_direct_advantage((risky_capture,))

        self.assertEqual(result.status, StrategySelectionStatus.SELECTED)
        self.assertIs(result.selected_bundle, risky_capture)
        self.assertIs(
            result.selected_commitment_option,
            risky_capture.commitment_options.options[1],
        )
        self.assertEqual(
            result.notes,
            (
                "two-player direct advantage selected",
                "selected commitment option: capture_and_hold",
                "pressure capture-hold preference: capture_and_hold",
            ),
        )

    def test_risky_capture_preserves_validated_reserve_before_hold(
        self,
    ) -> None:
        risky_capture = bundle_for(
            target_planet_id=2,
            source_planet_id=1,
            mission_type=MissionType.CAPTURE_NEUTRAL,
            mission_value_facts=value_facts(
                target_owner_baseline=-1,
                target_owner_mission=0,
                target_production_before=4,
                production_delta_vs_baseline=4,
            ),
            total_score=20.0,
            response_labels=("target_race_risk",),
            option_types=(
                CommitmentOptionType.RESERVE_PRESERVING,
                CommitmentOptionType.CAPTURE_AND_HOLD,
            ),
        )

        result = select_two_player_direct_advantage((risky_capture,))

        self.assertEqual(result.status, StrategySelectionStatus.SELECTED)
        self.assertIs(
            result.selected_commitment_option,
            risky_capture.commitment_options.options[0],
        )

    def test_risky_thin_capture_yields_to_owned_retention_when_no_hold_exists(
        self,
    ) -> None:
        reinforcement = bundle_for(
            target_planet_id=2,
            source_planet_id=1,
            mission_type=MissionType.REINFORCE,
            mission_value_facts=value_facts(
                target_owner_baseline=0,
                target_owner_mission=0,
                target_production_before=5,
                production_delta_vs_baseline=0,
            ),
            total_score=2.0,
            response_labels=("target_race_risk",),
            option_types=(CommitmentOptionType.RESERVE_PRESERVING,),
        )
        risky_thin_capture = bundle_for(
            target_planet_id=3,
            source_planet_id=4,
            mission_type=MissionType.CAPTURE_NEUTRAL,
            mission_value_facts=value_facts(
                target_owner_baseline=-1,
                target_owner_mission=0,
                target_production_before=8,
                production_delta_vs_baseline=8,
            ),
            total_score=80.0,
            response_labels=("target_race_risk",),
            option_types=(
                CommitmentOptionType.RESERVE_PRESERVING,
                CommitmentOptionType.MINIMUM_CAPTURE,
            ),
        )

        result = select_two_player_direct_advantage(
            (risky_thin_capture, reinforcement)
        )

        self.assertEqual(result.status, StrategySelectionStatus.SELECTED)
        self.assertIs(result.selected_bundle, reinforcement)
        self.assertEqual(
            result.selected_commitment_option.option_type,
            CommitmentOptionType.RESERVE_PRESERVING,
        )

    def test_no_risk_capture_preserves_default_commitment_order(self) -> None:
        ordinary_capture = bundle_for(
            target_planet_id=2,
            source_planet_id=1,
            mission_type=MissionType.CAPTURE_NEUTRAL,
            mission_value_facts=value_facts(
                target_owner_baseline=-1,
                target_owner_mission=0,
                target_production_before=4,
                production_delta_vs_baseline=4,
            ),
            total_score=20.0,
            option_types=(
                CommitmentOptionType.RESERVE_PRESERVING,
                CommitmentOptionType.CAPTURE_AND_HOLD,
            ),
        )

        result = select_two_player_direct_advantage((ordinary_capture,))

        self.assertEqual(result.status, StrategySelectionStatus.SELECTED)
        self.assertIs(result.selected_bundle, ordinary_capture)
        self.assertIs(
            result.selected_commitment_option,
            ordinary_capture.commitment_options.options[0],
        )

    def test_no_pressure_preserves_direct_advantage_ordering_over_reinforcement(
        self,
    ) -> None:
        reinforcement = bundle_for(
            target_planet_id=2,
            source_planet_id=1,
            mission_type=MissionType.REINFORCE,
            mission_value_facts=value_facts(
                target_owner_baseline=0,
                target_owner_mission=0,
                target_production_before=5,
                production_delta_vs_baseline=0,
            ),
            total_score=2.0,
            option_types=(CommitmentOptionType.RESERVE_PRESERVING,),
        )
        attack = bundle_for(
            target_planet_id=3,
            source_planet_id=4,
            mission_type=MissionType.ATTACK_ENEMY,
            mission_value_facts=value_facts(
                target_owner_baseline=1,
                target_owner_mission=0,
                target_production_before=8,
                production_delta_vs_baseline=8,
            ),
            total_score=80.0,
            option_types=(CommitmentOptionType.RESERVE_PRESERVING,),
        )

        result = select_two_player_direct_advantage((reinforcement, attack))

        self.assertEqual(result.status, StrategySelectionStatus.SELECTED)
        self.assertIs(result.selected_bundle, attack)

    def test_owned_production_pressure_prefers_retention_over_attack(
        self,
    ) -> None:
        reinforcement = bundle_for(
            target_planet_id=1,
            source_planet_id=4,
            mission_type=MissionType.REINFORCE,
            mission_value_facts=value_facts(
                target_owner_baseline=0,
                target_owner_mission=0,
                target_production_before=3,
                production_delta_vs_baseline=0,
            ),
            total_score=-20.0,
            option_types=(CommitmentOptionType.RESERVE_PRESERVING,),
        )
        higher_score_attack = bundle_for(
            target_planet_id=3,
            source_planet_id=1,
            mission_type=MissionType.ATTACK_ENEMY,
            mission_value_facts=value_facts(
                target_owner_baseline=1,
                target_owner_mission=0,
                target_production_before=8,
                production_delta_vs_baseline=8,
            ),
            total_score=80.0,
            option_types=(CommitmentOptionType.RESERVE_PRESERVING,),
        )

        result = select_two_player_direct_advantage(
            (higher_score_attack, reinforcement),
            config=TwoPlayerSelectionConfig(
                owned_production_threat_report=owned_pressure_report(),
            ),
        )

        self.assertEqual(result.status, StrategySelectionStatus.SELECTED)
        self.assertIs(result.selected_bundle, reinforcement)
        self.assertEqual(
            result.selected_commitment_option.option_type,
            CommitmentOptionType.RESERVE_PRESERVING,
        )
        self.assertIn(
            "owned-production pressure preference: reserve_preserving retention",
            result.notes,
        )

    def test_owned_production_pressure_allows_conservative_below_floor(
        self,
    ) -> None:
        conservative = bundle_for(
            target_planet_id=3,
            source_planet_id=4,
            mission_type=MissionType.CAPTURE_NEUTRAL,
            mission_value_facts=value_facts(
                target_owner_baseline=-1,
                target_owner_mission=0,
                target_production_before=4,
                production_delta_vs_baseline=4,
            ),
            total_score=-5.0,
            option_types=(CommitmentOptionType.RESERVE_PRESERVING,),
        )

        result = select_two_player_direct_advantage(
            (conservative,),
            config=TwoPlayerSelectionConfig(
                minimum_total_score=0.0,
                owned_production_threat_report=owned_pressure_report(),
            ),
        )

        self.assertEqual(result.status, StrategySelectionStatus.SELECTED)
        self.assertIs(result.selected_bundle, conservative)
        self.assertIn(
            "owned-production pressure preference: non-draining reserve",
            result.notes,
        )

    def test_no_owned_production_pressure_preserves_score_floor(self) -> None:
        conservative = bundle_for(
            target_planet_id=3,
            source_planet_id=4,
            mission_type=MissionType.CAPTURE_NEUTRAL,
            mission_value_facts=value_facts(
                target_owner_baseline=-1,
                target_owner_mission=0,
                target_production_before=4,
                production_delta_vs_baseline=4,
            ),
            total_score=-5.0,
            option_types=(CommitmentOptionType.RESERVE_PRESERVING,),
        )

        result = select_two_player_direct_advantage(
            (conservative,),
            config=TwoPlayerSelectionConfig(
                minimum_total_score=0.0,
                owned_production_threat_report=owned_pressure_report(
                    production_pressure_count=0,
                ),
            ),
        )

        self.assertEqual(result.status, StrategySelectionStatus.NO_ACTION)
        self.assertIn("below minimum total score", result.notes)

    def test_spammy_own_transfer_facts_prefer_productive_alternative(
        self,
    ) -> None:
        reinforcement = bundle_for(
            target_planet_id=2,
            source_planet_id=1,
            mission_type=MissionType.REINFORCE,
            mission_value_facts=value_facts(
                target_owner_baseline=0,
                target_owner_mission=0,
                target_production_before=5,
                production_delta_vs_baseline=0,
            ),
            total_score=90.0,
            option_types=(CommitmentOptionType.RESERVE_PRESERVING,),
        )
        productive_capture = bundle_for(
            target_planet_id=3,
            source_planet_id=4,
            mission_type=MissionType.CAPTURE_NEUTRAL,
            mission_value_facts=value_facts(
                target_owner_baseline=-1,
                target_owner_mission=0,
                target_production_before=8,
                production_delta_vs_baseline=8,
            ),
            total_score=20.0,
            option_types=(CommitmentOptionType.RESERVE_PRESERVING,),
        )

        result = select_two_player_direct_advantage(
            (reinforcement, productive_capture),
            config=TwoPlayerSelectionConfig(
                own_transfer_intent_report=own_transfer_spam_report(),
            ),
        )

        self.assertEqual(result.status, StrategySelectionStatus.SELECTED)
        self.assertIs(result.selected_bundle, productive_capture)
        self.assertIn(
            "own-transfer spam preference: productive alternative",
            result.notes,
        )

    def test_no_spam_control_preserves_existing_ordering(self) -> None:
        reinforcement = bundle_for(
            target_planet_id=2,
            source_planet_id=1,
            mission_type=MissionType.REINFORCE,
            mission_value_facts=value_facts(
                target_owner_baseline=0,
                target_owner_mission=0,
                target_production_before=5,
                production_delta_vs_baseline=0,
            ),
            total_score=90.0,
            option_types=(CommitmentOptionType.RESERVE_PRESERVING,),
        )
        productive_capture = bundle_for(
            target_planet_id=3,
            source_planet_id=4,
            mission_type=MissionType.CAPTURE_NEUTRAL,
            mission_value_facts=value_facts(
                target_owner_baseline=-1,
                target_owner_mission=0,
                target_production_before=8,
                production_delta_vs_baseline=8,
            ),
            total_score=20.0,
            option_types=(CommitmentOptionType.RESERVE_PRESERVING,),
        )

        default_result = select_two_player_direct_advantage(
            (reinforcement, productive_capture),
        )
        result = select_two_player_direct_advantage(
            (reinforcement, productive_capture),
            config=TwoPlayerSelectionConfig(
                own_transfer_intent_report=own_transfer_spam_report(
                    spammy_count=0,
                ),
            ),
        )

        self.assertEqual(result.status, StrategySelectionStatus.SELECTED)
        self.assertIs(result.selected_bundle, default_result.selected_bundle)
        self.assertNotIn(
            "own-transfer spam preference: productive alternative",
            result.notes,
        )

    def test_owned_production_pressure_overrides_spam_suppression(
        self,
    ) -> None:
        reinforcement = bundle_for(
            target_planet_id=1,
            source_planet_id=4,
            mission_type=MissionType.REINFORCE,
            mission_value_facts=value_facts(
                target_owner_baseline=0,
                target_owner_mission=0,
                target_production_before=3,
                production_delta_vs_baseline=0,
            ),
            total_score=-20.0,
            option_types=(CommitmentOptionType.RESERVE_PRESERVING,),
        )
        productive_capture = bundle_for(
            target_planet_id=3,
            source_planet_id=4,
            mission_type=MissionType.CAPTURE_NEUTRAL,
            mission_value_facts=value_facts(
                target_owner_baseline=-1,
                target_owner_mission=0,
                target_production_before=8,
                production_delta_vs_baseline=8,
            ),
            total_score=80.0,
            option_types=(CommitmentOptionType.RESERVE_PRESERVING,),
        )

        result = select_two_player_direct_advantage(
            (productive_capture, reinforcement),
            config=TwoPlayerSelectionConfig(
                owned_production_threat_report=owned_pressure_report(),
                own_transfer_intent_report=own_transfer_spam_report(),
            ),
        )

        self.assertEqual(result.status, StrategySelectionStatus.SELECTED)
        self.assertIs(result.selected_bundle, reinforcement)
        self.assertIn(
            "owned-production pressure preference: reserve_preserving retention",
            result.notes,
        )

    def test_enemy_denial_prefers_high_value_opponent_production_target(
        self,
    ) -> None:
        lower_value_denial = bundle_for(
            target_planet_id=2,
            source_planet_id=1,
            mission_type=MissionType.ATTACK_ENEMY,
            mission_value_facts=value_facts(
                target_owner_baseline=1,
                target_owner_mission=0,
                target_production_before=6,
                production_delta_vs_baseline=6,
            ),
            total_score=80.0,
            option_types=(CommitmentOptionType.RESERVE_PRESERVING,),
        )
        high_value_report_target = bundle_for(
            target_planet_id=3,
            source_planet_id=4,
            mission_type=MissionType.ATTACK_ENEMY,
            mission_value_facts=value_facts(
                target_owner_baseline=1,
                target_owner_mission=0,
                target_production_before=4,
                production_delta_vs_baseline=4,
            ),
            total_score=10.0,
            option_types=(CommitmentOptionType.RESERVE_PRESERVING,),
        )

        result = select_two_player_direct_advantage(
            (lower_value_denial, high_value_report_target),
            config=TwoPlayerSelectionConfig(
                enemy_denial_opportunity_report=enemy_denial_report(
                    high_value_target_ids=(3,),
                ),
            ),
        )

        self.assertEqual(result.status, StrategySelectionStatus.SELECTED)
        self.assertIs(result.selected_bundle, high_value_report_target)
        self.assertIn(
            "enemy-production denial preference: high_value_denial",
            result.notes,
        )

    def test_owned_production_pressure_overrides_enemy_denial_preference(
        self,
    ) -> None:
        reinforcement = bundle_for(
            target_planet_id=1,
            source_planet_id=4,
            mission_type=MissionType.REINFORCE,
            mission_value_facts=value_facts(
                target_owner_baseline=0,
                target_owner_mission=0,
                target_production_before=3,
                production_delta_vs_baseline=0,
            ),
            total_score=-20.0,
            option_types=(CommitmentOptionType.RESERVE_PRESERVING,),
        )
        high_value_denial = bundle_for(
            target_planet_id=3,
            source_planet_id=4,
            mission_type=MissionType.ATTACK_ENEMY,
            mission_value_facts=value_facts(
                target_owner_baseline=1,
                target_owner_mission=0,
                target_production_before=8,
                production_delta_vs_baseline=8,
            ),
            total_score=80.0,
            option_types=(CommitmentOptionType.RESERVE_PRESERVING,),
        )

        result = select_two_player_direct_advantage(
            (high_value_denial, reinforcement),
            config=TwoPlayerSelectionConfig(
                owned_production_threat_report=owned_pressure_report(),
                enemy_denial_opportunity_report=enemy_denial_report(
                    high_value_target_ids=(3,),
                ),
            ),
        )

        self.assertEqual(result.status, StrategySelectionStatus.SELECTED)
        self.assertIs(result.selected_bundle, reinforcement)
        self.assertIn(
            "owned-production pressure preference: reserve_preserving retention",
            result.notes,
        )
        self.assertNotIn(
            "enemy-production denial preference: high_value_denial",
            result.notes,
        )

    def test_spam_suppression_allows_high_value_enemy_denial_as_productive_option(
        self,
    ) -> None:
        ordinary_capture = bundle_for(
            target_planet_id=2,
            source_planet_id=1,
            mission_type=MissionType.CAPTURE_NEUTRAL,
            mission_value_facts=value_facts(
                target_owner_baseline=-1,
                target_owner_mission=0,
                target_production_before=8,
                production_delta_vs_baseline=8,
            ),
            total_score=80.0,
            option_types=(CommitmentOptionType.RESERVE_PRESERVING,),
        )
        high_value_denial = bundle_for(
            target_planet_id=3,
            source_planet_id=4,
            mission_type=MissionType.ATTACK_ENEMY,
            mission_value_facts=value_facts(
                target_owner_baseline=1,
                target_owner_mission=0,
                target_production_before=4,
                production_delta_vs_baseline=4,
            ),
            total_score=10.0,
            option_types=(CommitmentOptionType.RESERVE_PRESERVING,),
        )

        result = select_two_player_direct_advantage(
            (ordinary_capture, high_value_denial),
            config=TwoPlayerSelectionConfig(
                own_transfer_intent_report=own_transfer_spam_report(),
                enemy_denial_opportunity_report=enemy_denial_report(
                    high_value_target_ids=(3,),
                ),
            ),
        )

        self.assertEqual(result.status, StrategySelectionStatus.SELECTED)
        self.assertIs(result.selected_bundle, high_value_denial)
        self.assertIn(
            "own-transfer spam preference: productive alternative",
            result.notes,
        )
        self.assertIn(
            "enemy-production denial preference: high_value_denial",
            result.notes,
        )

    def test_no_enemy_denial_report_preserves_existing_ordering(self) -> None:
        lower_score_denial = bundle_for(
            target_planet_id=3,
            source_planet_id=4,
            mission_type=MissionType.ATTACK_ENEMY,
            mission_value_facts=value_facts(
                target_owner_baseline=1,
                target_owner_mission=0,
                target_production_before=4,
                production_delta_vs_baseline=4,
            ),
            total_score=10.0,
            option_types=(CommitmentOptionType.RESERVE_PRESERVING,),
        )
        higher_denied_target = bundle_for(
            target_planet_id=2,
            source_planet_id=1,
            mission_type=MissionType.ATTACK_ENEMY,
            mission_value_facts=value_facts(
                target_owner_baseline=1,
                target_owner_mission=0,
                target_production_before=6,
                production_delta_vs_baseline=6,
            ),
            total_score=80.0,
            option_types=(CommitmentOptionType.RESERVE_PRESERVING,),
        )

        result = select_two_player_direct_advantage(
            (lower_score_denial, higher_denied_target),
        )

        self.assertIs(result.selected_bundle, higher_denied_target)
        self.assertNotIn(
            "enemy-production denial preference: high_value_denial",
            result.notes,
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
