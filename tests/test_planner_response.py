"""Tests for the planner opponent-response API boundary."""

from __future__ import annotations

import copy
import importlib
import unittest
from dataclasses import FrozenInstanceError
from unittest.mock import patch

from ow_planner import (
    CandidateOutcome,
    MissionCandidate,
    MissionEvaluation,
    MissionEvaluationFacts,
    MissionEvaluationStatus,
    MissionResponseEvaluation,
    MissionResponseFacts,
    MissionType,
    ResponseConfig,
    ResponseEvaluationStatus,
    evaluate_responses,
)
from ow_sim.state import GameState


def response_state() -> GameState:
    return GameState(
        tick=7,
        player_id=0,
        raw_observation={"step": 7, "player": 0},
    )


def mission_candidate(target_planet_id: int = 2) -> MissionCandidate:
    return MissionCandidate(
        mission_type=MissionType.CAPTURE_NEUTRAL,
        target_planet_id=target_planet_id,
        source_planet_ids=(1,),
        outcome=CandidateOutcome.UNTESTED,
    )


def mission_evaluation(target_planet_id: int = 2) -> MissionEvaluation:
    candidate = mission_candidate(target_planet_id)
    facts = MissionEvaluationFacts(
        mission_type=candidate.mission_type,
        target_planet_id=candidate.target_planet_id,
        source_planet_ids=candidate.source_planet_ids,
        launch_count=0,
        ships_spent=0,
        launch_angles=(),
        candidate_outcome=candidate.outcome,
    )
    return MissionEvaluation(
        candidate=candidate,
        status=MissionEvaluationStatus.EVALUATED,
        facts=facts,
    )


class PlannerResponseTests(unittest.TestCase):
    def test_response_module_imports_and_exports_are_available(self) -> None:
        importlib.import_module("ow_planner.response")

        self.assertIs(ResponseConfig, ResponseConfig)
        self.assertIs(ResponseEvaluationStatus, ResponseEvaluationStatus)
        self.assertIs(MissionResponseFacts, MissionResponseFacts)
        self.assertIs(MissionResponseEvaluation, MissionResponseEvaluation)
        self.assertIsNotNone(evaluate_responses)

    def test_response_status_enum_values_are_stable(self) -> None:
        self.assertEqual(ResponseEvaluationStatus.UNEVALUATED.value, "unevaluated")
        self.assertEqual(ResponseEvaluationStatus.EVALUATED.value, "evaluated")
        self.assertEqual(ResponseEvaluationStatus.INCOMPLETE.value, "incomplete")

    def test_response_dataclasses_are_constructible_and_frozen(self) -> None:
        evaluation = mission_evaluation()
        config = ResponseConfig(response_window_ticks=3)
        facts = MissionResponseFacts(
            response_labels=("placeholder",),
            notes=("structural",),
        )
        response = MissionResponseEvaluation(
            evaluation=evaluation,
            status=ResponseEvaluationStatus.EVALUATED,
            facts=facts,
            note="ok",
        )

        self.assertEqual(config.response_window_ticks, 3)
        self.assertEqual(facts.response_labels, ("placeholder",))
        self.assertIs(response.evaluation, evaluation)
        with self.assertRaises(FrozenInstanceError):
            config.response_window_ticks = 1
        with self.assertRaises(FrozenInstanceError):
            facts.notes = ()
        with self.assertRaises(FrozenInstanceError):
            response.note = None

    def test_response_config_rejects_invalid_window_ticks(self) -> None:
        for response_window_ticks in (-1, True, 1.5, "3", None):
            with self.subTest(response_window_ticks=response_window_ticks):
                with self.assertRaises(ValueError):
                    ResponseConfig(response_window_ticks=response_window_ticks)

    def test_evaluate_responses_returns_empty_tuple_for_empty_input(self) -> None:
        self.assertEqual(evaluate_responses(response_state(), ()), ())

    def test_evaluate_responses_preserves_order_and_wraps_original_evaluations(self) -> None:
        first = mission_evaluation(2)
        second = mission_evaluation(3)

        responses = evaluate_responses(response_state(), (first, second))

        self.assertEqual(
            tuple(response.evaluation for response in responses),
            (first, second),
        )
        self.assertIs(responses[0].evaluation, first)
        self.assertIs(responses[1].evaluation, second)
        self.assertEqual(
            tuple(response.status for response in responses),
            (
                ResponseEvaluationStatus.EVALUATED,
                ResponseEvaluationStatus.EVALUATED,
            ),
        )
        self.assertEqual(
            tuple(response.facts for response in responses),
            (MissionResponseFacts(), MissionResponseFacts()),
        )
        self.assertEqual(tuple(response.note for response in responses), (None, None))

    def test_evaluate_responses_marks_missing_facts_incomplete(self) -> None:
        evaluation = MissionEvaluation(candidate=mission_candidate(), facts=None)

        (response,) = evaluate_responses(response_state(), (evaluation,))

        self.assertIs(response.evaluation, evaluation)
        self.assertEqual(response.status, ResponseEvaluationStatus.INCOMPLETE)
        self.assertEqual(
            response.facts,
            MissionResponseFacts(notes=("mission facts are missing",)),
        )
        self.assertEqual(response.note, "mission facts are missing")

    def test_evaluate_responses_does_not_mutate_state_or_evaluations(self) -> None:
        state = response_state()
        evaluation = mission_evaluation()
        state_before = copy.deepcopy(state)
        evaluation_before = copy.deepcopy(evaluation)

        evaluate_responses(
            state,
            (evaluation,),
            config=ResponseConfig(response_window_ticks=5),
        )

        self.assertEqual(state, state_before)
        self.assertEqual(evaluation, evaluation_before)

    def test_evaluate_responses_does_not_call_deferred_logic(self) -> None:
        with (
            patch("ow_planner.candidates.generate_candidates") as generate,
            patch("ow_sim.timeline.simulate_ticks") as simulate_ticks,
            patch("ow_sim.whatif.simulate_launch_orders") as simulate_launch_orders,
        ):
            evaluate_responses(response_state(), (mission_evaluation(),))

        generate.assert_not_called()
        simulate_ticks.assert_not_called()
        simulate_launch_orders.assert_not_called()

    def test_response_boundary_adds_no_ranking_or_selection_fields(self) -> None:
        (response,) = evaluate_responses(response_state(), (mission_evaluation(),))

        self.assertFalse(hasattr(response, "rank"))
        self.assertFalse(hasattr(response, "selected"))
        self.assertFalse(hasattr(response, "score_components"))
        self.assertFalse(hasattr(response, "total_score"))


if __name__ == "__main__":
    unittest.main()
