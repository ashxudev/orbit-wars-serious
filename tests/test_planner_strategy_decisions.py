"""Tests for Strategy Modes Cycle 1 planner decision bundles."""

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
    MissionResponseEvaluation,
    MissionType,
    PlannerDecisionBundle,
    StrategyMode,
    StrategyModeFacts,
    planner_decision_bundles,
)


def mission_candidate(
    target_planet_id: int = 2,
    *,
    source_planet_id: int = 1,
) -> MissionCandidate:
    launch = LaunchCandidate(
        source_planet_id=source_planet_id,
        angle=0.25,
        ships=3,
        player_id=0,
    )
    return MissionCandidate(
        mission_type=MissionType.CAPTURE_NEUTRAL,
        target_planet_id=target_planet_id,
        source_planet_ids=(source_planet_id,),
        launches=(launch,),
        outcome=CandidateOutcome.VALIDATED,
    )


def mission_evaluation(
    candidate: MissionCandidate,
    *,
    note: str | None = None,
    total_score: float | None = None,
) -> MissionEvaluation:
    return MissionEvaluation(
        candidate=candidate,
        total_score=total_score,
        note=note,
    )


def response_evaluation(
    evaluation: MissionEvaluation,
    *,
    note: str | None = None,
) -> MissionResponseEvaluation:
    return MissionResponseEvaluation(
        evaluation=evaluation,
        note=note,
    )


def commitment_options(
    candidate: MissionCandidate,
    *,
    note: str = "commitments",
) -> CandidateCommitmentOptions:
    option = CommitmentOption(
        option_type=CommitmentOptionType.NO_ATTACK,
        candidate=candidate,
        status=CommitmentOptionStatus.VALIDATED,
        note="no attack",
    )
    return CandidateCommitmentOptions(
        candidate=candidate,
        options=(option,),
        notes=(note,),
    )


def strategy_facts() -> StrategyModeFacts:
    return StrategyModeFacts(
        mode=StrategyMode.TWO_PLAYER,
        player_id=0,
        active_player_ids=(0, 1),
        opponent_player_ids=(1,),
        player_count=2,
    )


class PlannerStrategyDecisionTests(unittest.TestCase):
    def test_strategy_decision_module_imports_and_exports_are_available(self) -> None:
        importlib.import_module("ow_planner.strategy_decisions")

        self.assertIs(PlannerDecisionBundle, PlannerDecisionBundle)
        self.assertIsNotNone(planner_decision_bundles)

    def test_planner_decision_bundle_is_constructible_frozen_and_slotted(self) -> None:
        candidate = mission_candidate()
        bundle = PlannerDecisionBundle(candidate=candidate)

        self.assertIs(bundle.candidate, candidate)
        self.assertEqual(bundle.notes, ())
        self.assertTrue(hasattr(PlannerDecisionBundle, "__slots__"))
        with self.assertRaises(FrozenInstanceError):
            bundle.notes = ("changed",)

    def test_full_bundle_joins_existing_artifacts_by_candidate_identity(self) -> None:
        candidate = mission_candidate()
        evaluation = mission_evaluation(candidate, total_score=12.0)
        response = response_evaluation(evaluation)
        commitments = commitment_options(candidate)
        facts = strategy_facts()

        bundles = planner_decision_bundles(
            (candidate,),
            strategy_mode_facts=facts,
            evaluations=(evaluation,),
            response_evaluations=(response,),
            commitment_options=(commitments,),
        )

        self.assertEqual(len(bundles), 1)
        bundle = bundles[0]
        self.assertIs(bundle.candidate, candidate)
        self.assertIs(bundle.strategy_mode_facts, facts)
        self.assertIs(bundle.evaluation, evaluation)
        self.assertIs(bundle.response_evaluation, response)
        self.assertIs(bundle.commitment_options, commitments)
        self.assertEqual(bundle.notes, ())

    def test_candidate_order_is_preserved_even_when_artifacts_are_unordered(self) -> None:
        first = mission_candidate(2, source_planet_id=1)
        second = mission_candidate(3, source_planet_id=4)
        first_evaluation = mission_evaluation(first, note="first")
        second_evaluation = mission_evaluation(second, note="second")
        first_response = response_evaluation(first_evaluation, note="first response")
        second_response = response_evaluation(second_evaluation, note="second response")
        first_commitments = commitment_options(first, note="first commitments")
        second_commitments = commitment_options(second, note="second commitments")

        bundles = planner_decision_bundles(
            (first, second),
            evaluations=(second_evaluation, first_evaluation),
            response_evaluations=(second_response, first_response),
            commitment_options=(second_commitments, first_commitments),
        )

        self.assertEqual(tuple(bundle.candidate for bundle in bundles), (first, second))
        self.assertIs(bundles[0].evaluation, first_evaluation)
        self.assertIs(bundles[1].evaluation, second_evaluation)
        self.assertIs(bundles[0].response_evaluation, first_response)
        self.assertIs(bundles[1].response_evaluation, second_response)
        self.assertIs(bundles[0].commitment_options, first_commitments)
        self.assertIs(bundles[1].commitment_options, second_commitments)

    def test_missing_artifacts_leave_none_fields_and_deterministic_notes(self) -> None:
        candidate = mission_candidate()

        bundle = planner_decision_bundles((candidate,))[0]

        self.assertIsNone(bundle.evaluation)
        self.assertIsNone(bundle.response_evaluation)
        self.assertIsNone(bundle.commitment_options)
        self.assertEqual(
            bundle.notes,
            (
                "missing evaluation",
                "missing response evaluation",
                "missing commitment options",
            ),
        )

    def test_duplicate_artifacts_for_same_candidate_use_first_match(self) -> None:
        candidate = mission_candidate()
        first_evaluation = mission_evaluation(candidate, note="first evaluation")
        second_evaluation = mission_evaluation(candidate, note="second evaluation")
        first_response = response_evaluation(first_evaluation, note="first response")
        second_response = response_evaluation(second_evaluation, note="second response")
        first_commitments = commitment_options(candidate, note="first commitments")
        second_commitments = commitment_options(candidate, note="second commitments")

        bundle = planner_decision_bundles(
            (candidate,),
            evaluations=(first_evaluation, second_evaluation),
            response_evaluations=(first_response, second_response),
            commitment_options=(first_commitments, second_commitments),
        )[0]

        self.assertIs(bundle.evaluation, first_evaluation)
        self.assertIs(bundle.response_evaluation, first_response)
        self.assertIs(bundle.commitment_options, first_commitments)

    def test_equal_but_distinct_candidates_do_not_match_by_value(self) -> None:
        candidate = mission_candidate()
        equal_candidate = mission_candidate()
        self.assertEqual(candidate, equal_candidate)
        self.assertIsNot(candidate, equal_candidate)
        evaluation = mission_evaluation(equal_candidate)
        response = response_evaluation(evaluation)
        commitments = commitment_options(equal_candidate)

        bundle = planner_decision_bundles(
            (candidate,),
            evaluations=(evaluation,),
            response_evaluations=(response,),
            commitment_options=(commitments,),
        )[0]

        self.assertIsNone(bundle.evaluation)
        self.assertIsNone(bundle.response_evaluation)
        self.assertIsNone(bundle.commitment_options)
        self.assertEqual(
            bundle.notes,
            (
                "missing evaluation",
                "missing response evaluation",
                "missing commitment options",
            ),
        )

    def test_strategy_mode_facts_are_attached_unchanged_to_each_bundle(self) -> None:
        first = mission_candidate(2, source_planet_id=1)
        second = mission_candidate(3, source_planet_id=4)
        facts = strategy_facts()

        bundles = planner_decision_bundles(
            (first, second),
            strategy_mode_facts=facts,
        )

        self.assertIs(bundles[0].strategy_mode_facts, facts)
        self.assertIs(bundles[1].strategy_mode_facts, facts)

    def test_bundle_composition_does_not_mutate_inputs(self) -> None:
        candidate = mission_candidate()
        evaluation = mission_evaluation(candidate, total_score=3.5)
        response = response_evaluation(evaluation)
        commitments = commitment_options(candidate)
        facts = strategy_facts()
        before = (
            copy.deepcopy(candidate),
            copy.deepcopy(evaluation),
            copy.deepcopy(response),
            copy.deepcopy(commitments),
            copy.deepcopy(facts),
        )

        planner_decision_bundles(
            (candidate,),
            strategy_mode_facts=facts,
            evaluations=(evaluation,),
            response_evaluations=(response,),
            commitment_options=(commitments,),
        )

        self.assertEqual(
            (candidate, evaluation, response, commitments, facts),
            before,
        )

    def test_bundle_composition_does_not_call_deferred_planner_or_simulator_logic(
        self,
    ) -> None:
        candidate = mission_candidate()
        evaluation = mission_evaluation(candidate)
        response = response_evaluation(evaluation)
        commitments = commitment_options(candidate)

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
            bundles = planner_decision_bundles(
                (candidate,),
                evaluations=(evaluation,),
                response_evaluations=(response,),
                commitment_options=(commitments,),
            )

        self.assertEqual(len(bundles), 1)
        self.assertEqual(bundles[0].notes, ())


if __name__ == "__main__":
    unittest.main()
