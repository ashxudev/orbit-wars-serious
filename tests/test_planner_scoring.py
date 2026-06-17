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
    MissionTimingFacts,
    MissionType,
    MissionValueFacts,
    ScoreComponent,
    score_evaluations,
    score_mission_outcome_facts,
    score_mission_timing_facts,
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


def retained_control_value_facts() -> MissionValueFacts:
    return MissionValueFacts(
        target_owner_before=0,
        target_owner_baseline=0,
        target_owner_mission=0,
        target_captured_by_player=False,
        target_retained_by_player=True,
        target_lost_by_player=False,
        target_production_before=2,
        target_production_baseline_controlled_by_player=2,
        target_production_mission_controlled_by_player=2,
        production_delta_vs_baseline=0,
        target_ship_delta_vs_baseline=1,
        total_source_ship_delta_vs_baseline=0,
        total_source_ship_delta_vs_before=0,
        ships_spent=0,
        mission_valid_for_value=True,
    )


def lost_target_value_facts() -> MissionValueFacts:
    return MissionValueFacts(
        target_owner_before=0,
        target_owner_baseline=0,
        target_owner_mission=1,
        target_captured_by_player=False,
        target_retained_by_player=False,
        target_lost_by_player=True,
        target_production_before=2,
        target_production_baseline_controlled_by_player=2,
        target_production_mission_controlled_by_player=0,
        production_delta_vs_baseline=-2,
        target_ship_delta_vs_baseline=-4,
        total_source_ship_delta_vs_baseline=0,
        total_source_ship_delta_vs_before=0,
        ships_spent=0,
        mission_valid_for_value=True,
    )


def mission_evaluation(
    value_facts: MissionValueFacts,
    timing_facts: MissionTimingFacts = MissionTimingFacts(timing_complete=True),
) -> MissionEvaluation:
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
        timing_facts=timing_facts,
    )
    return MissionEvaluation(candidate=candidate, facts=facts)


class PlannerScoringTests(unittest.TestCase):
    def test_scoring_exports_are_available(self) -> None:
        self.assertIs(MissionScoringConfig, MissionScoringConfig)
        self.assertIsNotNone(score_mission_value_facts)
        self.assertIsNotNone(score_mission_timing_facts)
        self.assertIsNotNone(score_mission_outcome_facts)
        self.assertIsNotNone(score_evaluations)

    def test_scoring_config_is_frozen_and_validates_weights(self) -> None:
        config = MissionScoringConfig(
            production_delta_weight=12.0,
            arrival_tick_weight=-0.25,
        )

        self.assertEqual(config.production_delta_weight, 12.0)
        self.assertEqual(config.arrival_tick_weight, -0.25)
        with self.assertRaises(FrozenInstanceError):
            config.production_delta_weight = 7.0
        for field_name in (
            "production_delta_weight",
            "arrival_tick_weight",
            "incomplete_timing_penalty",
            "capture_success_weight",
            "retain_control_weight",
            "target_loss_penalty",
        ):
            for value in (True, float("inf"), "1.0"):
                with self.subTest(field_name=field_name, value=value):
                    with self.assertRaises(ValueError):
                        MissionScoringConfig(**{field_name: value})

    def test_complete_timing_scores_max_arrival_ticks(self) -> None:
        components, total = score_mission_timing_facts(
            MissionTimingFacts(
                launch_arrival_ticks=(3, 7),
                min_arrival_ticks=3,
                max_arrival_ticks=7,
                timing_complete=True,
            )
        )

        self.assertEqual(
            components,
            (ScoreComponent("max_arrival_ticks", 7.0, -0.05),),
        )
        self.assertAlmostEqual(total, -0.35)

    def test_no_launch_complete_timing_scores_zero_without_component(self) -> None:
        components, total = score_mission_timing_facts(
            MissionTimingFacts(timing_complete=True)
        )

        self.assertEqual(components, ())
        self.assertEqual(total, 0.0)

    def test_incomplete_timing_scores_explicit_penalty(self) -> None:
        components, total = score_mission_timing_facts(
            MissionTimingFacts(
                launch_arrival_ticks=(None,),
                timing_complete=False,
            )
        )

        self.assertEqual(
            components,
            (ScoreComponent("incomplete_timing_penalty", 1.0, -25.0),),
        )
        self.assertEqual(total, -25.0)

    def test_custom_timing_weights_are_applied(self) -> None:
        config = MissionScoringConfig(
            arrival_tick_weight=-2.0,
            incomplete_timing_penalty=-9.0,
        )

        complete_components, complete_total = score_mission_timing_facts(
            MissionTimingFacts(
                launch_arrival_ticks=(4,),
                min_arrival_ticks=4,
                max_arrival_ticks=4,
                timing_complete=True,
            ),
            config,
        )
        incomplete_components, incomplete_total = score_mission_timing_facts(
            MissionTimingFacts(launch_arrival_ticks=(None,), timing_complete=False),
            config,
        )

        self.assertEqual(
            complete_components,
            (ScoreComponent("max_arrival_ticks", 4.0, -2.0),),
        )
        self.assertEqual(complete_total, -8.0)
        self.assertEqual(
            incomplete_components,
            (ScoreComponent("incomplete_timing_penalty", 1.0, -9.0),),
        )
        self.assertEqual(incomplete_total, -9.0)

    def test_capture_outcome_scores_successful_capture(self) -> None:
        components, total = score_mission_outcome_facts(neutral_capture_value_facts())

        self.assertEqual(
            components,
            (ScoreComponent("target_captured_by_player", 1.0, 5.0),),
        )
        self.assertEqual(total, 5.0)

    def test_capture_outcome_scores_retained_control(self) -> None:
        components, total = score_mission_outcome_facts(retained_control_value_facts())

        self.assertEqual(
            components,
            (ScoreComponent("target_retained_by_player", 1.0, 2.0),),
        )
        self.assertEqual(total, 2.0)

    def test_capture_outcome_scores_target_loss_penalty(self) -> None:
        components, total = score_mission_outcome_facts(lost_target_value_facts())

        self.assertEqual(
            components,
            (ScoreComponent("target_lost_by_player", 1.0, -10.0),),
        )
        self.assertEqual(total, -10.0)

    def test_capture_outcome_scores_no_components_for_false_or_none_flags(self) -> None:
        false_components, false_total = score_mission_outcome_facts(no_launch_value_facts())
        none_components, none_total = score_mission_outcome_facts(
            MissionValueFacts(mission_valid_for_value=True)
        )

        self.assertEqual(false_components, ())
        self.assertEqual(false_total, 0.0)
        self.assertEqual(none_components, ())
        self.assertEqual(none_total, 0.0)

    def test_capture_outcome_scores_nothing_for_invalid_missions(self) -> None:
        components, total = score_mission_outcome_facts(
            MissionValueFacts(
                target_captured_by_player=True,
                mission_valid_for_value=False,
            )
        )

        self.assertEqual(components, ())
        self.assertEqual(total, 0.0)

    def test_custom_outcome_weights_are_applied(self) -> None:
        config = MissionScoringConfig(
            capture_success_weight=11.0,
            retain_control_weight=7.0,
            target_loss_penalty=-13.0,
        )

        capture_components, capture_total = score_mission_outcome_facts(
            neutral_capture_value_facts(),
            config,
        )
        retain_components, retain_total = score_mission_outcome_facts(
            retained_control_value_facts(),
            config,
        )
        loss_components, loss_total = score_mission_outcome_facts(
            lost_target_value_facts(),
            config,
        )

        self.assertEqual(
            capture_components,
            (ScoreComponent("target_captured_by_player", 1.0, 11.0),),
        )
        self.assertEqual(capture_total, 11.0)
        self.assertEqual(
            retain_components,
            (ScoreComponent("target_retained_by_player", 1.0, 7.0),),
        )
        self.assertEqual(retain_total, 7.0)
        self.assertEqual(
            loss_components,
            (ScoreComponent("target_lost_by_player", 1.0, -13.0),),
        )
        self.assertEqual(loss_total, -13.0)

    def test_value_scoring_remains_value_only(self) -> None:
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
        self.assertEqual(total, 29.75)

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
        self.assertEqual(scored[0].total_score, 34.75)
        self.assertEqual(scored[1].total_score, 0.0)
        self.assertEqual(first.score_components, ())
        self.assertIsNone(first.total_score)

    def test_score_evaluations_appends_timing_then_outcome_components(self) -> None:
        evaluation = mission_evaluation(
            neutral_capture_value_facts(),
            MissionTimingFacts(
                launch_arrival_ticks=(3,),
                min_arrival_ticks=3,
                max_arrival_ticks=3,
                timing_complete=True,
            ),
        )

        (scored,) = score_evaluations((evaluation,))

        self.assertEqual(
            tuple(component.name for component in scored.score_components),
            (
                "production_delta_vs_baseline",
                "target_ship_delta_vs_baseline",
                "source_ship_delta_vs_baseline",
                "ships_spent",
                "max_arrival_ticks",
                "target_captured_by_player",
            ),
        )
        self.assertEqual(
            scored.score_components[-2],
            ScoreComponent("max_arrival_ticks", 3.0, -0.05),
        )
        self.assertEqual(
            scored.score_components[-1],
            ScoreComponent("target_captured_by_player", 1.0, 5.0),
        )
        self.assertAlmostEqual(scored.total_score, 34.6)

    def test_score_evaluations_penalizes_incomplete_timing_for_valid_missions(self) -> None:
        evaluation = mission_evaluation(
            neutral_capture_value_facts(),
            MissionTimingFacts(launch_arrival_ticks=(None,), timing_complete=False),
        )

        (scored,) = score_evaluations((evaluation,))

        self.assertEqual(
            scored.score_components[-2],
            ScoreComponent("incomplete_timing_penalty", 1.0, -25.0),
        )
        self.assertEqual(
            scored.score_components[-1],
            ScoreComponent("target_captured_by_player", 1.0, 5.0),
        )
        self.assertEqual(scored.total_score, 9.75)

    def test_score_evaluations_appends_retain_and_loss_outcome_components(self) -> None:
        retained = mission_evaluation(retained_control_value_facts())
        lost = mission_evaluation(lost_target_value_facts())

        retained_scored, lost_scored = score_evaluations((retained, lost))

        self.assertEqual(
            retained_scored.score_components[-1],
            ScoreComponent("target_retained_by_player", 1.0, 2.0),
        )
        self.assertEqual(retained_scored.total_score, 3.0)
        self.assertEqual(
            lost_scored.score_components[-1],
            ScoreComponent("target_lost_by_player", 1.0, -10.0),
        )
        self.assertEqual(lost_scored.total_score, -34.0)

    def test_score_evaluations_does_not_add_timing_or_outcome_to_invalid_missions(self) -> None:
        evaluation = mission_evaluation(
            MissionValueFacts(
                target_captured_by_player=True,
                ships_spent=3,
                mission_valid_for_value=False,
            ),
            MissionTimingFacts(
                launch_arrival_ticks=(3,),
                min_arrival_ticks=3,
                max_arrival_ticks=3,
                timing_complete=True,
            ),
        )

        (scored,) = score_evaluations((evaluation,))

        self.assertEqual(
            scored.score_components,
            (ScoreComponent("invalid_mission_penalty", 1.0, -1000.0),),
        )
        self.assertEqual(scored.total_score, -1000.0)

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
