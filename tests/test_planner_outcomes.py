"""Tests for Mission Generation Cycle 5 simulator-backed outcomes."""

from __future__ import annotations

import copy
import math
import unittest
from dataclasses import FrozenInstanceError
from unittest.mock import patch

from ow_planner import (
    CandidateOutcomeReport,
    CandidateValidationStatus,
    EstimatedPair,
    LaunchCandidate,
    ShipEstimate,
    ShipEstimateStatus,
    SourceTargetPair,
    TargetCategory,
    estimate_required_ships_for_pair,
    launch_candidate_from_pair,
    validate_estimated_pair_outcome,
    validate_estimated_pair_outcomes,
)
from ow_planner.actions import launch_candidate_to_order
from ow_sim.state import GameState, Planet
from ow_sim.whatif import LaunchOrder


def planet_at(
    planet_id: int,
    owner: int,
    x: float,
    y: float,
    ships: int,
    production: int = 0,
    radius: float = 0.0,
) -> Planet:
    return Planet(
        planet_id=planet_id,
        owner=owner,
        x=x,
        y=y,
        radius=radius,
        ships=ships,
        production=production,
        raw=(planet_id, owner, x, y, radius, ships, production),
    )


def simple_state(
    *,
    target_owner: int = -1,
    target_ships: int = 0,
    target_production: int = 0,
    source_ships: int = 10,
) -> GameState:
    source = planet_at(1, 0, 0.0, 0.0, source_ships)
    target = planet_at(2, target_owner, 1.0, 0.0, target_ships, target_production, radius=0.5)
    return GameState(
        tick=0,
        player_id=0,
        planets=(source, target),
        initial_planets=(source, target),
        next_fleet_id=100,
        raw_observation={
            "step": 0,
            "player": 0,
            "planets": [list(source.raw), list(target.raw)],
            "fleets": [],
            "next_fleet_id": 100,
        },
    )


def pair(
    *,
    target_owner: int = -1,
    target_category: TargetCategory = TargetCategory.NEUTRAL,
    target_ships: int = 0,
    target_production: int = 0,
    rough_travel_ticks: int = 1,
    source_affordable_ships: int = 10,
) -> SourceTargetPair:
    return SourceTargetPair(
        source_planet_id=1,
        target_planet_id=2,
        target_owner=target_owner,
        target_category=target_category,
        source_ships=source_affordable_ships,
        target_ships=target_ships,
        target_production=target_production,
        source_position=(0.0, 0.0),
        target_position=(1.0, 0.0),
        distance=1.0,
        rough_travel_ticks=rough_travel_ticks,
        source_affordable_ships=source_affordable_ships,
    )


def estimated_pair(source_pair: SourceTargetPair) -> EstimatedPair:
    estimate = estimate_required_ships_for_pair(source_pair)
    return EstimatedPair(
        pair=source_pair,
        estimate=estimate,
        launch=launch_candidate_from_pair(source_pair),
    )


class PlannerOutcomeValidationTests(unittest.TestCase):
    def test_outcome_exports_and_types_are_available(self) -> None:
        self.assertEqual(CandidateValidationStatus.VALIDATED.value, "validated")
        self.assertEqual(CandidateValidationStatus.NO_LAUNCH.value, "no_launch")
        self.assertEqual(
            CandidateValidationStatus.SIMULATION_REJECTED.value,
            "simulation_rejected",
        )
        self.assertIsNotNone(validate_estimated_pair_outcome)
        self.assertIsNotNone(validate_estimated_pair_outcomes)
        self.assertIs(CandidateOutcomeReport, CandidateOutcomeReport)

    def test_outcome_report_type_is_frozen(self) -> None:
        report = validate_estimated_pair_outcome(simple_state(), estimated_pair(pair()))

        with self.assertRaises(FrozenInstanceError):
            report.captured_target = False

    def test_affordable_neutral_capture_validates_and_captures_target(self) -> None:
        report = validate_estimated_pair_outcome(simple_state(), estimated_pair(pair()))

        self.assertEqual(report.status, CandidateValidationStatus.VALIDATED)
        self.assertEqual(report.launch, LaunchCandidate(1, 0.0, 1, None))
        self.assertEqual(report.launch_order, LaunchOrder(1, 0.0, 1, 0))
        self.assertEqual(report.rollout_ticks, 1)
        self.assertEqual(report.target_owner_after, 0)
        self.assertEqual(report.target_ships_after, 1)
        self.assertEqual(report.source_ships_after, 9)
        self.assertTrue(report.captured_target)
        self.assertEqual(report.error, None)

    def test_affordable_enemy_attack_returns_factual_owner_and_ships(self) -> None:
        source_pair = pair(
            target_owner=1,
            target_category=TargetCategory.ENEMY,
            target_ships=1,
            target_production=1,
            rough_travel_ticks=1,
            source_affordable_ships=10,
        )
        report = validate_estimated_pair_outcome(
            simple_state(target_owner=1, target_ships=1, target_production=1),
            estimated_pair(source_pair),
        )

        self.assertEqual(report.status, CandidateValidationStatus.VALIDATED)
        self.assertEqual(report.launch.ships, 3)
        self.assertEqual(report.target_owner_after, 0)
        self.assertEqual(report.target_ships_after, 1)
        self.assertEqual(report.source_ships_after, 7)
        self.assertTrue(report.captured_target)

    def test_no_launch_estimated_pair_returns_no_launch_without_simulating(self) -> None:
        source_pair = pair(target_ships=10, source_affordable_ships=10)
        no_launch_pair = EstimatedPair(
            pair=source_pair,
            estimate=ShipEstimate(
                target_category=TargetCategory.NEUTRAL,
                required_ships=11,
                source_available_ships=10,
                target_projected_ships=10,
                production_added=0,
                buffer_ships=1,
                status=ShipEstimateStatus.INSUFFICIENT_SOURCE_SHIPS,
            ),
            launch=None,
        )

        with patch("ow_planner.outcomes.simulate_launch_orders") as simulate:
            report = validate_estimated_pair_outcome(simple_state(), no_launch_pair)

        simulate.assert_not_called()
        self.assertEqual(report.status, CandidateValidationStatus.NO_LAUNCH)
        self.assertIsNone(report.launch)
        self.assertIsNone(report.launch_order)
        self.assertFalse(report.captured_target)

    def test_simulation_rejection_when_actual_source_no_longer_has_ships(self) -> None:
        source_pair = pair(target_ships=1, source_affordable_ships=10)

        report = validate_estimated_pair_outcome(
            simple_state(source_ships=1),
            estimated_pair(source_pair),
        )

        self.assertEqual(report.status, CandidateValidationStatus.SIMULATION_REJECTED)
        self.assertIn("enough ships", report.error)
        self.assertIsNone(report.launch_order)
        self.assertFalse(report.captured_target)

    def test_negative_rollout_ticks_rejects_without_simulating(self) -> None:
        source_pair = pair(rough_travel_ticks=-1)
        estimated = EstimatedPair(
            pair=source_pair,
            estimate=ShipEstimate(
                target_category=TargetCategory.NEUTRAL,
                required_ships=1,
                source_available_ships=10,
                target_projected_ships=0,
                production_added=0,
                buffer_ships=1,
                status=ShipEstimateStatus.AFFORDABLE,
            ),
            launch=LaunchCandidate(1, 0.0, 1),
        )

        with patch("ow_planner.outcomes.simulate_launch_orders") as simulate:
            report = validate_estimated_pair_outcome(simple_state(), estimated)

        simulate.assert_not_called()
        self.assertEqual(report.status, CandidateValidationStatus.SIMULATION_REJECTED)
        self.assertEqual(report.error, "rough_travel_ticks must be >= 0")

    def test_missing_target_after_rollout_reports_target_missing(self) -> None:
        state = simple_state()
        source_only = GameState(
            tick=1,
            player_id=0,
            planets=(state.planets[0],),
            initial_planets=(state.planets[0],),
            next_fleet_id=101,
        )

        with patch("ow_planner.outcomes.simulate_launch_orders", return_value=source_only):
            report = validate_estimated_pair_outcome(state, estimated_pair(pair()))

        self.assertEqual(report.status, CandidateValidationStatus.TARGET_MISSING)
        self.assertEqual(report.source_ships_after, 10)
        self.assertIsNone(report.target_owner_after)
        self.assertFalse(report.captured_target)

    def test_missing_source_after_rollout_reports_source_missing(self) -> None:
        state = simple_state()
        target_only = GameState(
            tick=1,
            player_id=0,
            planets=(state.planets[1],),
            initial_planets=(state.planets[1],),
            next_fleet_id=101,
        )

        with patch("ow_planner.outcomes.simulate_launch_orders", return_value=target_only):
            report = validate_estimated_pair_outcome(state, estimated_pair(pair()))

        self.assertEqual(report.status, CandidateValidationStatus.SOURCE_MISSING)
        self.assertEqual(report.target_owner_after, -1)
        self.assertIsNone(report.source_ships_after)
        self.assertFalse(report.captured_target)

    def test_rollout_ticks_use_pair_rough_travel_ticks(self) -> None:
        state = simple_state()
        source_pair = pair(rough_travel_ticks=3)

        with patch("ow_planner.outcomes.simulate_launch_orders", return_value=state) as simulate:
            report = validate_estimated_pair_outcome(state, estimated_pair(source_pair))

        self.assertEqual(report.rollout_ticks, 3)
        self.assertEqual(simulate.call_args.kwargs["ticks"], 3)

    def test_batch_helper_preserves_input_order(self) -> None:
        first = estimated_pair(pair(target_ships=0))
        second = estimated_pair(
            pair(
                target_owner=1,
                target_category=TargetCategory.ENEMY,
                target_ships=0,
                target_production=0,
            )
        )

        reports = validate_estimated_pair_outcomes(simple_state(), (first, second))

        self.assertEqual(tuple(report.estimated_pair for report in reports), (first, second))

    def test_launch_conversion_uses_existing_planner_action_boundary(self) -> None:
        with patch(
            "ow_planner.outcomes.launch_candidate_to_order",
            wraps=launch_candidate_to_order,
        ) as convert:
            validate_estimated_pair_outcome(simple_state(), estimated_pair(pair()))

        convert.assert_called_once()

    def test_outcome_validation_does_not_mutate_inputs(self) -> None:
        state = simple_state()
        estimated = estimated_pair(pair())
        state_before = copy.deepcopy(state)
        estimated_before = copy.deepcopy(estimated)

        validate_estimated_pair_outcome(state, estimated)

        self.assertEqual(state, state_before)
        self.assertEqual(estimated, estimated_before)
        self.assertEqual(state.raw_observation, state_before.raw_observation)

    def test_reports_do_not_include_scoring_or_selection_fields(self) -> None:
        report = validate_estimated_pair_outcome(simple_state(), estimated_pair(pair()))

        self.assertFalse(hasattr(report, "score"))
        self.assertFalse(hasattr(report, "rank"))
        self.assertFalse(hasattr(report, "selected"))

    def test_launch_angle_from_estimated_pair_is_still_factual(self) -> None:
        source_pair = pair()
        report = validate_estimated_pair_outcome(simple_state(), estimated_pair(source_pair))

        self.assertAlmostEqual(report.launch.angle, math.atan2(0.0, 1.0))


if __name__ == "__main__":
    unittest.main()
