"""End-to-end strategy-mode fixture tests through public dispatch."""

from __future__ import annotations

import unittest

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
    StrategyDispatchConfig,
    StrategyMode,
    StrategyModeFacts,
    StrategySelectionStatus,
    TwoPlayerSelectionConfig,
    select_strategy_for_mode,
)


def two_player_mode_facts() -> StrategyModeFacts:
    return StrategyModeFacts(
        mode=StrategyMode.TWO_PLAYER,
        player_id=0,
        active_player_ids=(0, 1),
        opponent_player_ids=(1,),
        player_count=2,
    )


def four_player_mode_facts() -> StrategyModeFacts:
    return StrategyModeFacts(
        mode=StrategyMode.FOUR_PLAYER,
        player_id=0,
        active_player_ids=(0, 1, 2, 3),
        opponent_player_ids=(1, 2, 3),
        player_count=4,
    )


def unknown_mode_facts() -> StrategyModeFacts:
    return StrategyModeFacts(
        mode=StrategyMode.UNKNOWN,
        player_id=0,
        active_player_ids=(0, 1, 2),
        opponent_player_ids=(1, 2),
        player_count=3,
        note="unknown player count",
    )


def four_player_board_facts() -> FourPlayerBoardFacts:
    mode_facts = four_player_mode_facts()
    standings = (
        FourPlayerStandingFacts(
            player_id=0,
            production=3,
            total_ships=20,
            production_rank=3,
            total_ship_rank=3,
            is_current_player=True,
        ),
        FourPlayerStandingFacts(
            player_id=1,
            production=4,
            total_ships=18,
            production_rank=2,
            total_ship_rank=4,
        ),
        FourPlayerStandingFacts(
            player_id=2,
            production=8,
            total_ships=30,
            production_rank=1,
            total_ship_rank=2,
            is_production_leader=True,
        ),
        FourPlayerStandingFacts(
            player_id=3,
            production=2,
            total_ships=50,
            production_rank=4,
            total_ship_rank=1,
            is_total_ship_leader=True,
        ),
    )
    return FourPlayerBoardFacts(
        strategy_mode_facts=mode_facts,
        is_four_player_mode=True,
        player_id=0,
        active_player_ids=mode_facts.active_player_ids,
        standings=standings,
        current_player_standing=standings[0],
        production_leader_player_id=2,
        total_ship_leader_player_id=3,
        survival_pressure=False,
    )


def mission_candidate(
    target_planet_id: int,
    source_planet_id: int,
    *,
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
    target_owner_mission: int = 0,
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
    value_facts: MissionValueFacts,
    *,
    total_score: float,
) -> MissionEvaluation:
    return MissionEvaluation(
        candidate=candidate,
        facts=MissionEvaluationFacts(
            mission_type=candidate.mission_type,
            target_planet_id=candidate.target_planet_id,
            source_planet_ids=candidate.source_planet_ids,
            launch_count=len(candidate.launches),
            ships_spent=sum(launch.ships for launch in candidate.launches),
            launch_angles=tuple(launch.angle for launch in candidate.launches),
            candidate_outcome=candidate.outcome,
            value_facts=value_facts,
        ),
        total_score=total_score,
    )


def commitment_option(
    candidate: MissionCandidate,
    option_type: CommitmentOptionType,
) -> CommitmentOption:
    return CommitmentOption(
        option_type=option_type,
        candidate=candidate,
        launches=candidate.launches,
        source_planet_ids=candidate.source_planet_ids,
        ships_committed=sum(launch.ships for launch in candidate.launches),
        status=CommitmentOptionStatus.VALIDATED,
        note=option_type.value,
    )


def bundle_for(
    *,
    strategy_mode_facts: StrategyModeFacts | None,
    target_planet_id: int,
    source_planet_id: int,
    value_facts: MissionValueFacts,
    total_score: float,
    source_counterattack_risk: bool = False,
    third_party_benefit_possible: bool = False,
    option_types: tuple[CommitmentOptionType, ...] = (
        CommitmentOptionType.MINIMUM_CAPTURE,
    ),
) -> PlannerDecisionBundle:
    candidate = mission_candidate(target_planet_id, source_planet_id)
    evaluation = mission_evaluation(candidate, value_facts, total_score=total_score)
    response_labels = []
    if source_counterattack_risk:
        response_labels.append("source_counterattack_risk")
    if third_party_benefit_possible:
        response_labels.append("third_party_benefit_possible")
    options = tuple(commitment_option(candidate, option_type) for option_type in option_types)
    return PlannerDecisionBundle(
        candidate=candidate,
        strategy_mode_facts=strategy_mode_facts,
        evaluation=evaluation,
        response_evaluation=MissionResponseEvaluation(
            evaluation=evaluation,
            facts=MissionResponseFacts(
                response_summary=ResponseSummaryFacts(
                    labels=tuple(response_labels),
                    source_counterattack_risk=source_counterattack_risk,
                    third_party_benefit_possible=third_party_benefit_possible,
                ),
            ),
        ),
        commitment_options=CandidateCommitmentOptions(
            candidate=candidate,
            options=options,
        ),
    )


class PlannerStrategyModeFixtureTests(unittest.TestCase):
    def test_two_player_dispatch_selects_direct_opponent_owned_advantage(self) -> None:
        mode_facts = two_player_mode_facts()
        opponent_bundle = bundle_for(
            strategy_mode_facts=mode_facts,
            target_planet_id=2,
            source_planet_id=1,
            value_facts=mission_value_facts(
                target_owner_baseline=1,
                target_production_before=3,
                production_delta_vs_baseline=3,
            ),
            total_score=1.0,
        )
        neutral_bundle = bundle_for(
            strategy_mode_facts=mode_facts,
            target_planet_id=3,
            source_planet_id=4,
            value_facts=mission_value_facts(
                target_owner_baseline=-1,
                target_production_before=10,
                production_delta_vs_baseline=10,
            ),
            total_score=20.0,
        )

        result = select_strategy_for_mode((neutral_bundle, opponent_bundle))

        self.assertEqual(result.status, StrategySelectionStatus.SELECTED)
        self.assertIs(result.selected_bundle, opponent_bundle)
        self.assertIs(
            result.selected_commitment_option,
            opponent_bundle.commitment_options.options[0],
        )

    def test_two_player_dispatch_respects_selection_config(self) -> None:
        mode_facts = two_player_mode_facts()
        low_score = bundle_for(
            strategy_mode_facts=mode_facts,
            target_planet_id=2,
            source_planet_id=1,
            value_facts=mission_value_facts(
                target_owner_baseline=1,
                target_production_before=5,
                production_delta_vs_baseline=5,
            ),
            total_score=2.0,
        )
        risky = bundle_for(
            strategy_mode_facts=mode_facts,
            target_planet_id=3,
            source_planet_id=4,
            value_facts=mission_value_facts(
                target_owner_baseline=1,
                target_production_before=8,
                production_delta_vs_baseline=8,
            ),
            total_score=50.0,
            source_counterattack_risk=True,
        )

        threshold_result = select_strategy_for_mode(
            (low_score,),
            config=StrategyDispatchConfig(
                two_player_config=TwoPlayerSelectionConfig(minimum_total_score=5.0),
            ),
        )
        risk_excluded_result = select_strategy_for_mode((risky,))
        risk_allowed_result = select_strategy_for_mode(
            (risky,),
            config=StrategyDispatchConfig(
                two_player_config=TwoPlayerSelectionConfig(
                    allow_source_counterattack_risk=True,
                ),
            ),
        )

        self.assertEqual(threshold_result.status, StrategySelectionStatus.NO_ACTION)
        self.assertIn("below minimum total score", threshold_result.notes)
        self.assertEqual(risk_excluded_result.status, StrategySelectionStatus.NO_ACTION)
        self.assertIn(
            "source counterattack risk excluded",
            risk_excluded_result.notes,
        )
        self.assertEqual(risk_allowed_result.status, StrategySelectionStatus.SELECTED)
        self.assertIs(risk_allowed_result.selected_bundle, risky)
        self.assertIs(
            risk_allowed_result.selected_commitment_option,
            risky.commitment_options.options[0],
        )

    def test_four_player_dispatch_selects_rank_aware_leader_target(self) -> None:
        board_facts = four_player_board_facts()
        production_leader_bundle = bundle_for(
            strategy_mode_facts=board_facts.strategy_mode_facts,
            target_planet_id=2,
            source_planet_id=1,
            value_facts=mission_value_facts(
                target_owner_baseline=2,
                target_production_before=8,
                production_delta_vs_baseline=8,
            ),
            total_score=1.0,
        )
        neutral_bundle = bundle_for(
            strategy_mode_facts=board_facts.strategy_mode_facts,
            target_planet_id=3,
            source_planet_id=4,
            value_facts=mission_value_facts(
                target_owner_baseline=-1,
                target_production_before=20,
                production_delta_vs_baseline=20,
            ),
            total_score=50.0,
        )

        result = select_strategy_for_mode(
            (neutral_bundle, production_leader_bundle),
            strategy_mode_facts=board_facts.strategy_mode_facts,
            four_player_board_facts=board_facts,
        )

        self.assertEqual(result.status, StrategySelectionStatus.SELECTED)
        self.assertIs(result.selected_bundle, production_leader_bundle)
        self.assertIs(
            result.selected_commitment_option,
            production_leader_bundle.commitment_options.options[0],
        )
        self.assertIn("production leader target", result.notes)

    def test_four_player_dispatch_respects_selection_config(self) -> None:
        board_facts = four_player_board_facts()
        third_party_bundle = bundle_for(
            strategy_mode_facts=board_facts.strategy_mode_facts,
            target_planet_id=2,
            source_planet_id=1,
            value_facts=mission_value_facts(
                target_owner_baseline=2,
                target_production_before=8,
                production_delta_vs_baseline=8,
            ),
            total_score=50.0,
            third_party_benefit_possible=True,
        )

        default_result = select_strategy_for_mode(
            (third_party_bundle,),
            strategy_mode_facts=board_facts.strategy_mode_facts,
            four_player_board_facts=board_facts,
        )
        allowed_result = select_strategy_for_mode(
            (third_party_bundle,),
            strategy_mode_facts=board_facts.strategy_mode_facts,
            four_player_board_facts=board_facts,
            config=StrategyDispatchConfig(
                four_player_config=FourPlayerSelectionConfig(
                    allow_third_party_benefit=True,
                ),
            ),
        )

        self.assertEqual(default_result.status, StrategySelectionStatus.NO_ACTION)
        self.assertIn("third-party benefit excluded", default_result.notes)
        self.assertEqual(allowed_result.status, StrategySelectionStatus.SELECTED)
        self.assertIs(allowed_result.selected_bundle, third_party_bundle)
        self.assertIs(
            allowed_result.selected_commitment_option,
            third_party_bundle.commitment_options.options[0],
        )

    def test_unknown_and_missing_mode_facts_are_rejected(self) -> None:
        unknown_facts = unknown_mode_facts()
        unknown_bundle = bundle_for(
            strategy_mode_facts=unknown_facts,
            target_planet_id=2,
            source_planet_id=1,
            value_facts=mission_value_facts(
                target_owner_baseline=1,
                target_production_before=5,
                production_delta_vs_baseline=5,
            ),
            total_score=5.0,
        )
        missing_mode_bundle = bundle_for(
            strategy_mode_facts=None,
            target_planet_id=3,
            source_planet_id=4,
            value_facts=mission_value_facts(
                target_owner_baseline=1,
                target_production_before=5,
                production_delta_vs_baseline=5,
            ),
            total_score=5.0,
        )

        unknown_result = select_strategy_for_mode((unknown_bundle,))
        missing_result = select_strategy_for_mode((missing_mode_bundle,))

        self.assertEqual(unknown_result.status, StrategySelectionStatus.REJECTED)
        self.assertIs(unknown_result.strategy_mode_facts, unknown_facts)
        self.assertEqual(unknown_result.notes, ("unknown strategy mode",))
        self.assertEqual(missing_result.status, StrategySelectionStatus.REJECTED)
        self.assertEqual(missing_result.notes, ("missing strategy mode facts",))


if __name__ == "__main__":
    unittest.main()
