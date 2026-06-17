"""Tests for Strategy Modes Cycle 3 two-player direct-advantage facts."""

from __future__ import annotations

import copy
import importlib
import unittest
from dataclasses import FrozenInstanceError
from unittest.mock import patch

from ow_planner import (
    CandidateOutcome,
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
    TwoPlayerAdvantageFacts,
    two_player_advantage_facts,
    two_player_advantage_facts_for_bundles,
)


def mission_candidate(
    target_planet_id: int = 2,
    *,
    source_planet_id: int = 1,
) -> MissionCandidate:
    launch = LaunchCandidate(
        source_planet_id=source_planet_id,
        angle=0.25,
        ships=5,
        player_id=0,
    )
    return MissionCandidate(
        mission_type=MissionType.ATTACK_ENEMY,
        target_planet_id=target_planet_id,
        source_planet_ids=(source_planet_id,),
        launches=(launch,),
        outcome=CandidateOutcome.VALIDATED,
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


def evaluation_facts(
    value_facts: MissionValueFacts,
    *,
    candidate: MissionCandidate | None = None,
) -> MissionEvaluationFacts:
    effective_candidate = candidate or mission_candidate()
    return MissionEvaluationFacts(
        mission_type=effective_candidate.mission_type,
        target_planet_id=effective_candidate.target_planet_id,
        source_planet_ids=effective_candidate.source_planet_ids,
        launch_count=len(effective_candidate.launches),
        ships_spent=sum(launch.ships for launch in effective_candidate.launches),
        launch_angles=tuple(launch.angle for launch in effective_candidate.launches),
        candidate_outcome=effective_candidate.outcome,
        value_facts=value_facts,
    )


def mission_evaluation(
    candidate: MissionCandidate,
    value_facts: MissionValueFacts | None,
    *,
    total_score: float | None = 11.5,
) -> MissionEvaluation:
    facts = None if value_facts is None else evaluation_facts(value_facts, candidate=candidate)
    return MissionEvaluation(
        candidate=candidate,
        facts=facts,
        total_score=total_score,
    )


def response_evaluation(
    evaluation: MissionEvaluation,
    *,
    labels: tuple[str, ...] = (),
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
                source_counterattack_risk=source_counterattack_risk,
            ),
        ),
    )


def bundle_for(
    value_facts: MissionValueFacts | None,
    *,
    strategy_mode_facts: StrategyModeFacts | None = None,
    response_labels: tuple[str, ...] = (),
    source_counterattack_risk: bool = False,
    response_missing: bool = False,
    response_facts_missing: bool = False,
    total_score: float | None = 11.5,
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
        strategy_mode_facts=strategy_mode_facts,
        evaluation=evaluation,
        response_evaluation=(
            None
            if response_missing
            else response_evaluation(
                evaluation,
                labels=response_labels,
                source_counterattack_risk=source_counterattack_risk,
                facts_missing=response_facts_missing,
            )
        ),
    )


def opponent_capture_value_facts() -> MissionValueFacts:
    return MissionValueFacts(
        target_owner_before=1,
        target_owner_baseline=1,
        target_owner_mission=0,
        target_captured_by_player=True,
        target_production_before=4,
        production_delta_vs_baseline=4,
        target_ship_delta_vs_baseline=3,
        total_source_ship_delta_vs_baseline=-5,
        ships_spent=5,
        mission_valid_for_value=True,
    )


class PlannerTwoPlayerStrategyTests(unittest.TestCase):
    def test_two_player_strategy_module_imports_and_exports_are_available(self) -> None:
        importlib.import_module("ow_planner.two_player_strategy")

        self.assertIs(TwoPlayerAdvantageFacts, TwoPlayerAdvantageFacts)
        self.assertIsNotNone(two_player_advantage_facts)
        self.assertIsNotNone(two_player_advantage_facts_for_bundles)

    def test_two_player_advantage_facts_are_constructible_frozen_and_slotted(self) -> None:
        bundle = bundle_for(
            opponent_capture_value_facts(),
            strategy_mode_facts=strategy_facts(),
        )
        facts = TwoPlayerAdvantageFacts(bundle=bundle)

        self.assertIs(facts.bundle, bundle)
        self.assertFalse(facts.is_two_player_mode)
        self.assertEqual(facts.response_labels, ())
        self.assertTrue(hasattr(TwoPlayerAdvantageFacts, "__slots__"))
        with self.assertRaises(FrozenInstanceError):
            facts.ships_spent = 1

    def test_opponent_capture_extracts_direct_advantage_facts(self) -> None:
        bundle = bundle_for(
            opponent_capture_value_facts(),
            strategy_mode_facts=strategy_facts(),
            response_labels=("source_counterattack_risk", "target_race_risk"),
            source_counterattack_risk=True,
            total_score=12.25,
        )

        facts = two_player_advantage_facts(bundle)

        self.assertIs(facts.bundle, bundle)
        self.assertTrue(facts.is_two_player_mode)
        self.assertEqual(facts.player_id, 0)
        self.assertEqual(facts.opponent_player_id, 1)
        self.assertEqual(facts.target_owner_before, 1)
        self.assertEqual(facts.target_owner_baseline, 1)
        self.assertEqual(facts.target_owner_mission, 0)
        self.assertTrue(facts.target_was_opponent_owned)
        self.assertTrue(facts.target_taken_from_opponent)
        self.assertTrue(facts.target_captured_by_player)
        self.assertEqual(facts.production_delta_vs_baseline, 4)
        self.assertEqual(facts.opponent_production_denied, 4)
        self.assertEqual(facts.target_ship_delta_vs_baseline, 3)
        self.assertEqual(facts.total_source_ship_delta_vs_baseline, -5)
        self.assertEqual(facts.net_ship_delta_vs_baseline, -2)
        self.assertEqual(facts.ships_spent, 5)
        self.assertTrue(facts.source_counterattack_risk)
        self.assertEqual(
            facts.response_labels,
            ("source_counterattack_risk", "target_race_risk"),
        )
        self.assertEqual(facts.evaluation_total_score, 12.25)
        self.assertEqual(facts.notes, ())

    def test_neutral_target_is_not_counted_as_opponent_production_denied(self) -> None:
        value_facts = MissionValueFacts(
            target_owner_before=-1,
            target_owner_baseline=-1,
            target_owner_mission=0,
            target_captured_by_player=True,
            target_production_before=2,
            production_delta_vs_baseline=2,
            target_ship_delta_vs_baseline=1,
            total_source_ship_delta_vs_baseline=-3,
            ships_spent=3,
            mission_valid_for_value=True,
        )
        bundle = bundle_for(value_facts, strategy_mode_facts=strategy_facts())

        facts = two_player_advantage_facts(bundle)

        self.assertFalse(facts.target_was_opponent_owned)
        self.assertFalse(facts.target_taken_from_opponent)
        self.assertEqual(facts.opponent_production_denied, 0)
        self.assertEqual(facts.net_ship_delta_vs_baseline, -2)
        self.assertEqual(facts.notes, ())

    def test_missing_strategy_mode_facts_adds_note_without_crashing(self) -> None:
        bundle = bundle_for(opponent_capture_value_facts())

        facts = two_player_advantage_facts(bundle)

        self.assertFalse(facts.is_two_player_mode)
        self.assertIsNone(facts.player_id)
        self.assertIsNone(facts.opponent_player_id)
        self.assertIn("missing strategy mode facts", facts.notes)

    def test_non_two_player_mode_adds_deterministic_notes(self) -> None:
        bundle = bundle_for(
            opponent_capture_value_facts(),
            strategy_mode_facts=strategy_facts(
                mode=StrategyMode.FOUR_PLAYER,
                player_id=0,
                opponent_player_ids=(1, 2, 3),
            ),
        )

        facts = two_player_advantage_facts(bundle)

        self.assertFalse(facts.is_two_player_mode)
        self.assertEqual(facts.player_id, 0)
        self.assertIsNone(facts.opponent_player_id)
        self.assertIn("not two-player mode", facts.notes)
        self.assertIn("missing opponent player id", facts.notes)

    def test_missing_player_and_opponent_ids_are_reported(self) -> None:
        bundle = bundle_for(
            opponent_capture_value_facts(),
            strategy_mode_facts=strategy_facts(
                mode=StrategyMode.TWO_PLAYER,
                player_id=None,
                opponent_player_ids=(),
            ),
        )

        facts = two_player_advantage_facts(bundle)

        self.assertTrue(facts.is_two_player_mode)
        self.assertIn("missing player id", facts.notes)
        self.assertIn("missing opponent player id", facts.notes)

    def test_missing_evaluation_and_evaluation_facts_are_reported(self) -> None:
        candidate = mission_candidate()
        no_evaluation_bundle = PlannerDecisionBundle(
            candidate=candidate,
            strategy_mode_facts=strategy_facts(),
        )
        missing_facts_bundle = bundle_for(
            None,
            strategy_mode_facts=strategy_facts(),
            response_missing=True,
            candidate=candidate,
        )

        no_evaluation_facts = two_player_advantage_facts(no_evaluation_bundle)
        missing_facts = two_player_advantage_facts(missing_facts_bundle)

        self.assertIn("missing evaluation", no_evaluation_facts.notes)
        self.assertIn("missing response evaluation", no_evaluation_facts.notes)
        self.assertIn("missing evaluation facts", missing_facts.notes)
        self.assertIn("missing response evaluation", missing_facts.notes)

    def test_missing_response_evaluation_and_facts_are_reported(self) -> None:
        missing_response_bundle = bundle_for(
            opponent_capture_value_facts(),
            strategy_mode_facts=strategy_facts(),
            response_missing=True,
        )
        missing_response_facts_bundle = bundle_for(
            opponent_capture_value_facts(),
            strategy_mode_facts=strategy_facts(),
            response_facts_missing=True,
        )

        missing_response = two_player_advantage_facts(missing_response_bundle)
        missing_response_facts = two_player_advantage_facts(
            missing_response_facts_bundle
        )

        self.assertIn("missing response evaluation", missing_response.notes)
        self.assertIsNone(missing_response.source_counterattack_risk)
        self.assertEqual(missing_response.response_labels, ())
        self.assertIn("missing response facts", missing_response_facts.notes)
        self.assertIsNone(missing_response_facts.source_counterattack_risk)
        self.assertEqual(missing_response_facts.response_labels, ())

    def test_batch_helper_preserves_bundle_order(self) -> None:
        first = bundle_for(
            opponent_capture_value_facts(),
            strategy_mode_facts=strategy_facts(),
            candidate=mission_candidate(2, source_planet_id=1),
        )
        second = bundle_for(
            MissionValueFacts(
                target_owner_baseline=-1,
                target_owner_mission=0,
                target_production_before=1,
                target_ship_delta_vs_baseline=0,
                total_source_ship_delta_vs_baseline=0,
                ships_spent=0,
            ),
            strategy_mode_facts=strategy_facts(),
            candidate=mission_candidate(3, source_planet_id=4),
        )

        facts = two_player_advantage_facts_for_bundles((first, second))

        self.assertEqual(tuple(item.bundle for item in facts), (first, second))

    def test_two_player_advantage_extraction_does_not_mutate_inputs(self) -> None:
        bundle = bundle_for(
            opponent_capture_value_facts(),
            strategy_mode_facts=strategy_facts(),
            response_labels=("source_counterattack_risk",),
            source_counterattack_risk=True,
        )
        before = copy.deepcopy(bundle)

        two_player_advantage_facts(bundle)
        two_player_advantage_facts_for_bundles((bundle,))

        self.assertEqual(bundle, before)

    def test_two_player_advantage_extraction_does_not_call_deferred_logic(self) -> None:
        bundle = bundle_for(
            opponent_capture_value_facts(),
            strategy_mode_facts=strategy_facts(),
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
            facts = two_player_advantage_facts(bundle)
            batch_facts = two_player_advantage_facts_for_bundles((bundle,))

        self.assertIs(facts.bundle, bundle)
        self.assertEqual(batch_facts[0].notes, ())


if __name__ == "__main__":
    unittest.main()
