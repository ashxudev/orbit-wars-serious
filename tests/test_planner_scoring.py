"""Tests for the isolated planner mission scoring policy."""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError
from unittest.mock import patch

from ow_planner import (
    CandidateOutcome,
    MissionCandidate,
    MissionEvaluation,
    MissionEvaluationFacts,
    MissionScoringConfig,
    MissionType,
    MissionValueFacts,
    ScoreComponent,
    score_evaluations,
    score_mission_value_facts,
)


def neutral_capture_value_facts() -> MissionValueFacts:
    return MissionValueFacts(
        target_owner_before=-1,
        target_owner_baseline=-1,
        target_owner_mission=0,
        target_captured_by_player=True,
        target_retained_by_player=False,
        target_lost_by_player=False,
        target_production_before=3,
        target_production_baseline_controlled_by_player=0,
        target_production_mission_controlled_by_player=3,
        production_delta_vs_baseline=3,
        target_ship_delta_vs_baseline=1,
        total_source_ship_delta_vs_baseline=-1,
        total_source_ship_delta_vs_before=-1,
        ships_spent=1,
        mission_valid_for_value=True,
    )


def enemy_capture_value_facts() -> MissionValueFacts:
    return MissionValueFacts(
        target_owner_before=1,
        target_owner_baseline=1,
        target_owner_mission=0,
        target_captured_by_player=True,
        target_retained_by_player=False,
        target_lost_by_player=False,
        target_production_before=4,
        target_production_baseline_controlled_by_player=0,
        target_production_mission_controlled_by_player=4,
        production_delta_vs_baseline=4,
        target_ship_delta_vs_baseline=-3,
        total_source_ship_delta_vs_baseline=-5,
        total_source_ship_delta_vs_before=-5,
        ships_spent=5,
        mission_valid_for_value=True,
    )


def no_launch_value_facts() -> MissionValueFacts:
    return MissionValueFacts(
        target_owner_before=-1,
        target_owner_baseline=-1,
        target_owner_mission=-1,
        target_captured_by_player=False,
        target_retained_by_player=False,
        target_lost_by_player=False,
        target_production_before=0,
        target_production_baseline_controlled_by_player=0,
        target_production_mission_controlled_by_player=0,
        production_delta_vs_baseline=0,
        target_ship_delta_vs_baseline=0,
        total_source_ship_delta_vs_baseline=0,
        total_source_ship_delta_vs_before=0,
        ships_spent=0,
        mission_valid_for_value=True,
    )


def mission_evaluation(value_facts: MissionValueFacts) -> MissionEvaluation:
    candidate = MissionCandidate(
        mission_type=MissionType.CAPTURE_NEUTRAL,
        target_planet_id=2,
        source_planet_ids=(1,),
        outcome=CandidateOutcome.UNTESTED,
    )
    facts = MissionEvaluationFacts(
        mission_type=MissionType.CAPTURE_NEUTRAL,
        target_planet_id=2,
        source_planet_ids=(1,),
        launch_count=0,
        ships_spent=value_facts.ships_spent,
        launch_angles=(),
        candidate_outcome=CandidateOutcome.UNTESTED,
        value_facts=value_facts,
    )
    return MissionEvaluation(candidate=candidate, facts=facts)


class PlannerScoringTests(unittest.TestCase):
    def test_scoring_exports_are_available(self) -> None:
        self.assertIs(MissionScoringConfig, MissionScoringConfig)
        self.assertIsNotNone(score_mission_value_facts)
        self.assertIsNotNone(score_evaluations)

    def test_scoring_config_is_frozen_and_validates_weights(self) -> None:
        config = MissionScoringConfig(production_delta_weight=12.0)

        self.assertEqual(config.production_delta_weight, 12.0)
        with self.assertRaises(FrozenInstanceError):
            config.production_delta_weight = 7.0
        for value in (True, float("inf"), "1.0"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    MissionScoringConfig(production_delta_weight=value)

    def test_neutral_capture_value_facts_score_components_and_total(self) -> None:
        components, total = score_mission_value_facts(neutral_capture_value_facts())

        self.assertEqual(
            tuple(component.name for component in components),
            (
                "production_delta_vs_baseline",
                "target_ship_delta_vs_baseline",
                "source_ship_delta_vs_baseline",
                "ships_spent",
            ),
        )
        self.assertEqual(
            components,
            (
                ScoreComponent("production_delta_vs_baseline", 3.0, 10.0),
                ScoreComponent("target_ship_delta_vs_baseline", 1.0, 1.0),
                ScoreComponent("source_ship_delta_vs_baseline", -1.0, 1.0),
                ScoreComponent("ships_spent", 1.0, -0.25),
            ),
        )
        self.assertEqual(total, 29.75)

    def test_enemy_capture_value_facts_score_with_source_costs(self) -> None:
        components, total = score_mission_value_facts(enemy_capture_value_facts())

        self.assertEqual(
            tuple(component.value for component in components),
            (4.0, -3.0, -5.0, 5.0),
        )
        self.assertEqual(total, 30.75)

    def test_no_launch_zero_delta_value_facts_score_zero(self) -> None:
        components, total = score_mission_value_facts(no_launch_value_facts())

        self.assertEqual(
            tuple(component.value for component in components),
            (0.0, 0.0, 0.0, 0.0),
        )
        self.assertEqual(total, 0.0)

    def test_invalid_mission_value_facts_return_penalty_component(self) -> None:
        components, total = score_mission_value_facts(
            MissionValueFacts(ships_spent=3, mission_valid_for_value=False)
        )

        self.assertEqual(
            components,
            (ScoreComponent("invalid_mission_penalty", 1.0, -1000.0),),
        )
        self.assertEqual(total, -1000.0)

    def test_custom_weights_are_applied_without_changing_component_values(self) -> None:
        value_facts = MissionValueFacts(
            production_delta_vs_baseline=2,
            target_ship_delta_vs_baseline=3,
            total_source_ship_delta_vs_baseline=-4,
            total_source_ship_delta_vs_before=-4,
            ships_spent=5,
            mission_valid_for_value=True,
        )
        config = MissionScoringConfig(
            production_delta_weight=2.0,
            target_ship_delta_weight=0.5,
            source_ship_delta_weight=1.5,
            ships_spent_weight=-1.0,
        )

        components, total = score_mission_value_facts(value_facts, config)

        self.assertEqual(
            tuple(component.value for component in components),
            (2.0, 3.0, -4.0, 5.0),
        )
        self.assertEqual(total, -5.5)

    def test_custom_invalid_penalty_is_applied(self) -> None:
        config = MissionScoringConfig(invalid_mission_penalty=-7.5)

        components, total = score_mission_value_facts(MissionValueFacts(), config)

        self.assertEqual(
            components,
            (ScoreComponent("invalid_mission_penalty", 1.0, -7.5),),
        )
        self.assertEqual(total, -7.5)

    def test_score_evaluations_preserves_order_and_does_not_mutate_inputs(self) -> None:
        first = mission_evaluation(neutral_capture_value_facts())
        second = mission_evaluation(no_launch_value_facts())

        scored = score_evaluations((first, second))

        self.assertEqual(tuple(evaluation.candidate for evaluation in scored), (first.candidate, second.candidate))
        self.assertIs(scored[0].candidate, first.candidate)
        self.assertIs(scored[1].candidate, second.candidate)
        self.assertEqual(scored[0].total_score, 29.75)
        self.assertEqual(scored[1].total_score, 0.0)
        self.assertEqual(first.score_components, ())
        self.assertIsNone(first.total_score)

    def test_score_evaluations_handles_missing_facts_as_invalid(self) -> None:
        candidate = MissionCandidate(
            mission_type=MissionType.CAPTURE_NEUTRAL,
            target_planet_id=2,
            source_planet_ids=(1,),
        )
        evaluation = MissionEvaluation(candidate=candidate, facts=None)

        (scored,) = score_evaluations((evaluation,))

        self.assertEqual(
            scored.score_components,
            (ScoreComponent("invalid_mission_penalty", 1.0, -1000.0),),
        )
        self.assertEqual(scored.total_score, -1000.0)

    def test_scoring_does_not_call_generation_or_simulation_helpers(self) -> None:
        with (
            patch("ow_planner.candidates.generate_candidates") as generate,
            patch("ow_sim.timeline.simulate_ticks") as simulate_ticks,
            patch("ow_sim.whatif.simulate_launch_orders") as simulate_launch_orders,
        ):
            score_mission_value_facts(neutral_capture_value_facts())

        generate.assert_not_called()
        simulate_ticks.assert_not_called()
        simulate_launch_orders.assert_not_called()

    def test_no_ranking_or_selection_behavior_is_introduced(self) -> None:
        scored = score_evaluations((mission_evaluation(neutral_capture_value_facts()),))[0]

        self.assertFalse(hasattr(scored, "rank"))
        self.assertFalse(hasattr(scored, "selected"))


if __name__ == "__main__":
    unittest.main()
