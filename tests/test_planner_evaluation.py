"""Tests for Mission Evaluation Cycle 0 contracts."""

from __future__ import annotations

import copy
import importlib
import unittest
from dataclasses import FrozenInstanceError
from unittest.mock import patch

from ow_planner import (
    EvaluationConfig,
    LaunchCandidate,
    MissionCandidate,
    MissionEvaluation,
    MissionEvaluationFacts,
    MissionEvaluationStatus,
    MissionType,
    ScoreComponent,
    evaluate_candidates,
)
from ow_sim.state import GameState, Planet


def planet() -> Planet:
    return Planet(
        planet_id=1,
        owner=0,
        x=0.0,
        y=0.0,
        radius=1.0,
        ships=5,
        production=1,
        raw=(1, 0, 0.0, 0.0, 1.0, 5, 1),
    )


def state_with_planet() -> GameState:
    source = planet()
    return GameState(
        tick=3,
        player_id=0,
        planets=(source,),
        initial_planets=(source,),
        next_fleet_id=10,
        raw_observation={
            "step": 3,
            "player": 0,
            "planets": [list(source.raw)],
        },
    )


def candidate(
    target_planet_id: int,
    mission_type: MissionType = MissionType.CAPTURE_NEUTRAL,
) -> MissionCandidate:
    return MissionCandidate(
        mission_type=mission_type,
        target_planet_id=target_planet_id,
        source_planet_ids=(1,),
        launches=(LaunchCandidate(source_planet_id=1, angle=0.0, ships=1),),
    )


class PlannerEvaluationTests(unittest.TestCase):
    def test_evaluation_module_imports_and_exports_are_available(self) -> None:
        importlib.import_module("ow_planner.evaluation")

        self.assertIsNotNone(evaluate_candidates)
        self.assertIs(MissionEvaluation, MissionEvaluation)
        self.assertIs(MissionEvaluationFacts, MissionEvaluationFacts)
        self.assertIs(ScoreComponent, ScoreComponent)
        self.assertIs(EvaluationConfig, EvaluationConfig)

    def test_enum_string_values_are_stable(self) -> None:
        self.assertEqual(MissionEvaluationStatus.UNEVALUATED.value, "unevaluated")
        self.assertEqual(MissionEvaluationStatus.EVALUATED.value, "evaluated")
        self.assertEqual(MissionEvaluationStatus.REJECTED.value, "rejected")

    def test_dataclasses_are_constructible_and_frozen(self) -> None:
        mission = candidate(2)
        config = EvaluationConfig(horizon_ticks=12)
        component = ScoreComponent(name="placeholder", value=2.5, weight=0.75)
        facts = MissionEvaluationFacts(notes=("structural",))
        evaluation = MissionEvaluation(
            candidate=mission,
            facts=facts,
            score_components=(component,),
            total_score=None,
        )

        self.assertEqual(config.horizon_ticks, 12)
        self.assertEqual(component.name, "placeholder")
        self.assertEqual(facts.notes, ("structural",))
        self.assertIs(evaluation.candidate, mission)
        with self.assertRaises(FrozenInstanceError):
            config.horizon_ticks = 1
        with self.assertRaises(FrozenInstanceError):
            component.value = 3.0
        with self.assertRaises(FrozenInstanceError):
            facts.notes = ()
        with self.assertRaises(FrozenInstanceError):
            evaluation.total_score = 1.0

    def test_evaluate_candidates_returns_empty_tuple_for_empty_input(self) -> None:
        self.assertEqual(evaluate_candidates(state_with_planet(), ()), ())

    def test_evaluate_candidates_preserves_candidate_input_order(self) -> None:
        first = candidate(2, MissionType.CAPTURE_NEUTRAL)
        second = candidate(3, MissionType.ATTACK_ENEMY)

        evaluations = evaluate_candidates(state_with_planet(), (first, second))

        self.assertEqual(tuple(evaluation.candidate for evaluation in evaluations), (first, second))
        self.assertIs(evaluations[0].candidate, first)
        self.assertIs(evaluations[1].candidate, second)

    def test_default_evaluations_are_unevaluated_structural_wrappers(self) -> None:
        mission = candidate(2)

        (evaluation,) = evaluate_candidates(state_with_planet(), (mission,))

        self.assertEqual(evaluation.status, MissionEvaluationStatus.UNEVALUATED)
        self.assertIsNone(evaluation.facts)
        self.assertEqual(evaluation.score_components, ())
        self.assertIsNone(evaluation.total_score)
        self.assertIsNone(evaluation.note)

    def test_config_rejects_invalid_horizon_ticks(self) -> None:
        for horizon_ticks in (-1, True, 1.5, "3"):
            with self.subTest(horizon_ticks=horizon_ticks):
                with self.assertRaises(ValueError):
                    EvaluationConfig(horizon_ticks=horizon_ticks)

    def test_evaluate_candidates_does_not_mutate_state_or_candidates(self) -> None:
        state = state_with_planet()
        first = candidate(2)
        second = candidate(3, MissionType.ATTACK_ENEMY)
        state_before = copy.deepcopy(state)
        candidates_before = copy.deepcopy((first, second))

        evaluate_candidates(state, (first, second), EvaluationConfig(horizon_ticks=5))

        self.assertEqual(state, state_before)
        self.assertEqual((first, second), candidates_before)
        self.assertEqual(state.raw_observation, state_before.raw_observation)

    def test_evaluate_candidates_does_not_call_generation_or_simulation_helpers(self) -> None:
        with (
            patch("ow_planner.candidates.generate_candidates") as generate,
            patch("ow_sim.timeline.simulate_ticks") as simulate_ticks,
            patch("ow_sim.whatif.simulate_launch_orders") as simulate_launch_orders,
        ):
            evaluate_candidates(state_with_planet(), (candidate(2),))

        generate.assert_not_called()
        simulate_ticks.assert_not_called()
        simulate_launch_orders.assert_not_called()

    def test_no_ranking_or_selection_behavior_is_introduced(self) -> None:
        evaluation = evaluate_candidates(state_with_planet(), (candidate(2),))[0]

        self.assertFalse(hasattr(evaluation, "rank"))
        self.assertFalse(hasattr(evaluation, "selected"))
        self.assertEqual(evaluation.score_components, ())
        self.assertIsNone(evaluation.total_score)


if __name__ == "__main__":
    unittest.main()
