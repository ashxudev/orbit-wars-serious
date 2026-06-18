"""Tests for Strategy Modes Cycle 6 four-player mission/target facts."""

from __future__ import annotations

import copy
import importlib
import unittest
from dataclasses import FrozenInstanceError
from unittest.mock import patch

from ow_planner import (
    CandidateOutcome,
    FourPlayerBoardFacts,
    FourPlayerMissionFacts,
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
    four_player_mission_facts,
    four_player_mission_facts_for_bundles,
)


def board_facts(
    *,
    is_four_player_mode: bool = True,
    player_id: int | None = 0,
    survival_pressure: bool | None = False,
) -> FourPlayerBoardFacts:
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
        is_four_player_mode=is_four_player_mode,
        player_id=player_id,
        active_player_ids=(0, 1, 2, 3),
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
    target_planet_id: int = 4,
    *,
    source_planet_id: int = 1,
) -> MissionCandidate:
    launch = LaunchCandidate(
        source_planet_id=source_planet_id,
        angle=0.25,
        ships=6,
        player_id=0,
    )
    return MissionCandidate(
        mission_type=MissionType.ATTACK_ENEMY,
        target_planet_id=target_planet_id,
        source_planet_ids=(source_planet_id,),
        launches=(launch,),
        outcome=CandidateOutcome.VALIDATED,
    )


def mission_evaluation(
    candidate: MissionCandidate,
    value_facts: MissionValueFacts | None,
    *,
    total_score: float | None = 10.0,
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


def response_evaluation(
    evaluation: MissionEvaluation,
    *,
    labels: tuple[str, ...] = (),
    third_party_benefit_possible: bool = False,
    source_counterattack_risk: bool = False,
    facts_missing: bool = False,
) -> MissionResponseEvaluation:
    if facts_missing:
        return MissionResponseEvaluation(evaluation=evaluation, facts=None)
    return MissionResponseEvaluation(
        evaluation=evaluation,
        facts=MissionResponseFacts(
            response_labels=labels,
            response_summary=ResponseSummaryFacts(
                labels=labels,
                third_party_benefit_possible=third_party_benefit_possible,
                source_counterattack_risk=source_counterattack_risk,
            ),
        ),
    )


def bundle_for(
    value_facts: MissionValueFacts | None,
    *,
    labels: tuple[str, ...] = (),
    third_party_benefit_possible: bool = False,
    source_counterattack_risk: bool = False,
    response_missing: bool = False,
    response_facts_missing: bool = False,
    total_score: float | None = 10.0,
    candidate: MissionCandidate | None = None,
) -> PlannerDecisionBundle:
    effective_candidate = candidate or mission_candidate()
    evaluation = mission_evaluation(
        effective_candidate,
        value_facts,
        total_score=total_score,
    )
    return PlannerDecisionBundle(
        candidate=effective_candidate,
        evaluation=evaluation,
        response_evaluation=(
            None
            if response_missing
            else response_evaluation(
                evaluation,
                labels=labels,
                third_party_benefit_possible=third_party_benefit_possible,
                source_counterattack_risk=source_counterattack_risk,
                facts_missing=response_facts_missing,
            )
        ),
    )


def production_leader_capture_value_facts() -> MissionValueFacts:
    return MissionValueFacts(
        target_owner_before=2,
        target_owner_baseline=2,
        target_owner_mission=0,
        target_captured_by_player=True,
        target_production_before=7,
        production_delta_vs_baseline=7,
        target_ship_delta_vs_baseline=4,
        total_source_ship_delta_vs_baseline=-6,
        ships_spent=6,
        mission_valid_for_value=True,
    )


class PlannerFourPlayerMissionTests(unittest.TestCase):
    def test_four_player_mission_module_imports_and_exports_are_available(self) -> None:
        importlib.import_module("ow_planner.four_player_missions")

        self.assertIs(FourPlayerMissionFacts, FourPlayerMissionFacts)
        self.assertIsNotNone(four_player_mission_facts)
        self.assertIsNotNone(four_player_mission_facts_for_bundles)

    def test_four_player_mission_facts_are_constructible_frozen_and_slotted(
        self,
    ) -> None:
        bundle = bundle_for(production_leader_capture_value_facts())
        facts = FourPlayerMissionFacts(bundle=bundle)

        self.assertIs(facts.bundle, bundle)
        self.assertFalse(facts.is_four_player_mode)
        self.assertEqual(facts.response_labels, ())
        self.assertTrue(hasattr(FourPlayerMissionFacts, "__slots__"))
        with self.assertRaises(FrozenInstanceError):
            facts.ships_spent = 1

    def test_valid_production_leader_target_capture_extracts_facts(self) -> None:
        board = board_facts(survival_pressure=True)
        bundle = bundle_for(
            production_leader_capture_value_facts(),
            labels=("third_party_benefit_possible", "source_counterattack_risk"),
            third_party_benefit_possible=True,
            source_counterattack_risk=True,
            total_score=15.5,
        )

        facts = four_player_mission_facts(bundle, board)

        self.assertIs(facts.bundle, bundle)
        self.assertIs(facts.board_facts, board)
        self.assertTrue(facts.is_four_player_mode)
        self.assertEqual(facts.player_id, 0)
        self.assertEqual(facts.production_leader_player_id, 2)
        self.assertEqual(facts.total_ship_leader_player_id, 3)
        self.assertTrue(facts.survival_pressure)
        self.assertEqual(facts.target_owner_before, 2)
        self.assertEqual(facts.target_owner_baseline, 2)
        self.assertEqual(facts.target_owner_mission, 0)
        self.assertEqual(facts.target_owner_production_rank, 1)
        self.assertEqual(facts.target_owner_total_ship_rank, 2)
        self.assertFalse(facts.target_was_current_player_owned)
        self.assertFalse(facts.target_was_non_player_owned)
        self.assertTrue(facts.target_was_production_leader_owned)
        self.assertFalse(facts.target_was_total_ship_leader_owned)
        self.assertTrue(facts.target_captured_by_player)
        self.assertTrue(facts.target_taken_from_production_leader)
        self.assertFalse(facts.target_taken_from_total_ship_leader)
        self.assertEqual(facts.production_delta_vs_baseline, 7)
        self.assertEqual(facts.leader_production_denied, 7)
        self.assertEqual(facts.target_ship_delta_vs_baseline, 4)
        self.assertEqual(facts.total_source_ship_delta_vs_baseline, -6)
        self.assertEqual(facts.net_ship_delta_vs_baseline, -2)
        self.assertEqual(facts.ships_spent, 6)
        self.assertTrue(facts.third_party_benefit_possible)
        self.assertTrue(facts.source_counterattack_risk)
        self.assertEqual(
            facts.response_labels,
            ("third_party_benefit_possible", "source_counterattack_risk"),
        )
        self.assertEqual(facts.evaluation_total_score, 15.5)
        self.assertEqual(facts.notes, ())

    def test_total_ship_leader_target_capture_extracts_total_ship_leader_flag(
        self,
    ) -> None:
        bundle = bundle_for(
            MissionValueFacts(
                target_owner_before=3,
                target_owner_baseline=3,
                target_owner_mission=0,
                target_captured_by_player=True,
                target_production_before=2,
                production_delta_vs_baseline=2,
                target_ship_delta_vs_baseline=5,
                total_source_ship_delta_vs_baseline=-4,
                ships_spent=4,
                mission_valid_for_value=True,
            ),
        )

        facts = four_player_mission_facts(bundle, board_facts())

        self.assertFalse(facts.target_was_production_leader_owned)
        self.assertTrue(facts.target_was_total_ship_leader_owned)
        self.assertFalse(facts.target_taken_from_production_leader)
        self.assertTrue(facts.target_taken_from_total_ship_leader)
        self.assertEqual(facts.leader_production_denied, 0)
        self.assertEqual(facts.target_owner_production_rank, 4)
        self.assertEqual(facts.target_owner_total_ship_rank, 1)
        self.assertEqual(facts.net_ship_delta_vs_baseline, 1)

    def test_neutral_target_sets_non_player_flags_and_no_leader_denial(self) -> None:
        bundle = bundle_for(
            MissionValueFacts(
                target_owner_before=-1,
                target_owner_baseline=-1,
                target_owner_mission=0,
                target_captured_by_player=True,
                target_production_before=3,
                production_delta_vs_baseline=3,
                target_ship_delta_vs_baseline=1,
                total_source_ship_delta_vs_baseline=-2,
                ships_spent=2,
                mission_valid_for_value=True,
            ),
        )

        facts = four_player_mission_facts(bundle, board_facts())

        self.assertIsNone(facts.target_owner_production_rank)
        self.assertIsNone(facts.target_owner_total_ship_rank)
        self.assertFalse(facts.target_was_current_player_owned)
        self.assertTrue(facts.target_was_non_player_owned)
        self.assertFalse(facts.target_was_production_leader_owned)
        self.assertFalse(facts.target_was_total_ship_leader_owned)
        self.assertFalse(facts.target_taken_from_production_leader)
        self.assertFalse(facts.target_taken_from_total_ship_leader)
        self.assertEqual(facts.leader_production_denied, 0)
        self.assertEqual(facts.notes, ())

    def test_target_owner_not_active_is_reported_without_throwing(self) -> None:
        bundle = bundle_for(
            MissionValueFacts(
                target_owner_before=9,
                target_owner_baseline=9,
                target_owner_mission=0,
                target_captured_by_player=True,
                target_production_before=3,
                production_delta_vs_baseline=3,
                target_ship_delta_vs_baseline=1,
                total_source_ship_delta_vs_baseline=-2,
                ships_spent=2,
                mission_valid_for_value=True,
            ),
        )

        facts = four_player_mission_facts(bundle, board_facts())

        self.assertIsNone(facts.target_owner_production_rank)
        self.assertIsNone(facts.target_owner_total_ship_rank)
        self.assertIn("target owner not active player", facts.notes)

    def test_missing_board_facts_and_non_four_player_board_are_reported(self) -> None:
        bundle = bundle_for(production_leader_capture_value_facts())

        missing_board = four_player_mission_facts(bundle, None)
        non_four_player = four_player_mission_facts(
            bundle,
            board_facts(is_four_player_mode=False),
        )

        self.assertIn("missing board facts", missing_board.notes)
        self.assertFalse(missing_board.is_four_player_mode)
        self.assertIn("not four-player mode", non_four_player.notes)
        self.assertFalse(non_four_player.is_four_player_mode)

    def test_missing_player_id_is_reported(self) -> None:
        bundle = bundle_for(production_leader_capture_value_facts())

        facts = four_player_mission_facts(bundle, board_facts(player_id=None))

        self.assertIn("missing player id", facts.notes)
        self.assertIsNone(facts.player_id)

    def test_missing_evaluation_and_evaluation_facts_are_reported(self) -> None:
        candidate = mission_candidate()
        no_evaluation = PlannerDecisionBundle(candidate=candidate)
        missing_facts = bundle_for(
            None,
            response_missing=True,
            candidate=candidate,
        )

        no_evaluation_facts = four_player_mission_facts(no_evaluation, board_facts())
        missing_facts_result = four_player_mission_facts(missing_facts, board_facts())

        self.assertIn("missing evaluation", no_evaluation_facts.notes)
        self.assertIn("missing response evaluation", no_evaluation_facts.notes)
        self.assertIn("missing evaluation facts", missing_facts_result.notes)
        self.assertIn("missing response evaluation", missing_facts_result.notes)

    def test_missing_response_evaluation_and_facts_are_reported(self) -> None:
        missing_response = bundle_for(
            production_leader_capture_value_facts(),
            response_missing=True,
        )
        missing_response_facts = bundle_for(
            production_leader_capture_value_facts(),
            response_facts_missing=True,
        )

        response_missing_facts = four_player_mission_facts(
            missing_response,
            board_facts(),
        )
        response_facts_missing = four_player_mission_facts(
            missing_response_facts,
            board_facts(),
        )

        self.assertIn("missing response evaluation", response_missing_facts.notes)
        self.assertIsNone(response_missing_facts.third_party_benefit_possible)
        self.assertIsNone(response_missing_facts.source_counterattack_risk)
        self.assertEqual(response_missing_facts.response_labels, ())
        self.assertIn("missing response facts", response_facts_missing.notes)
        self.assertIsNone(response_facts_missing.third_party_benefit_possible)
        self.assertIsNone(response_facts_missing.source_counterattack_risk)
        self.assertEqual(response_facts_missing.response_labels, ())

    def test_batch_helper_preserves_bundle_order(self) -> None:
        first = bundle_for(
            production_leader_capture_value_facts(),
            candidate=mission_candidate(4, source_planet_id=1),
        )
        second = bundle_for(
            MissionValueFacts(
                target_owner_before=-1,
                target_owner_baseline=-1,
                target_owner_mission=0,
                target_production_before=3,
                target_ship_delta_vs_baseline=0,
                total_source_ship_delta_vs_baseline=0,
                ships_spent=0,
            ),
            candidate=mission_candidate(5, source_planet_id=2),
        )
        board = board_facts()

        facts = four_player_mission_facts_for_bundles((first, second), board)

        self.assertEqual(tuple(item.bundle for item in facts), (first, second))
        self.assertIs(facts[0].board_facts, board)
        self.assertIs(facts[1].board_facts, board)

    def test_four_player_mission_facts_do_not_mutate_inputs(self) -> None:
        board = board_facts()
        bundle = bundle_for(
            production_leader_capture_value_facts(),
            labels=("third_party_benefit_possible",),
            third_party_benefit_possible=True,
        )
        before = (copy.deepcopy(board), copy.deepcopy(bundle))

        four_player_mission_facts(bundle, board)
        four_player_mission_facts_for_bundles((bundle,), board)

        self.assertEqual((board, bundle), before)

    def test_four_player_mission_facts_do_not_call_deferred_logic(self) -> None:
        board = board_facts()
        bundle = bundle_for(production_leader_capture_value_facts())

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
            facts = four_player_mission_facts(bundle, board)
            batch_facts = four_player_mission_facts_for_bundles((bundle,), board)

        self.assertIs(facts.bundle, bundle)
        self.assertEqual(batch_facts[0].notes, ())


if __name__ == "__main__":
    unittest.main()
