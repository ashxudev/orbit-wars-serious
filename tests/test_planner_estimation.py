"""Tests for Mission Generation Cycle 4 ship estimation."""

from __future__ import annotations

import math
import unittest
from dataclasses import FrozenInstanceError
from unittest.mock import patch

from ow_planner import (
    DEFAULT_CAPTURE_BUFFER_SHIPS,
    EstimatedPair,
    LaunchCandidate,
    ShipEstimate,
    ShipEstimateStatus,
    SourceTargetPair,
    TargetCategory,
    estimate_required_ships_for_pair,
    estimate_source_target_pairs,
    generate_candidates,
    launch_candidate_from_pair,
)
from ow_sim.forecast import angle_to_point
from ow_sim.state import GameState


def pair(
    *,
    source_planet_id: int = 1,
    target_planet_id: int = 2,
    target_owner: int = -1,
    target_category: TargetCategory = TargetCategory.NEUTRAL,
    source_ships: int = 20,
    target_ships: int = 5,
    target_production: int = 0,
    source_position: tuple[float, float] = (0.0, 0.0),
    target_position: tuple[float, float] = (3.0, 4.0),
    distance: float = 5.0,
    rough_travel_ticks: int = 5,
    source_affordable_ships: int = 20,
    target_is_comet: bool = False,
) -> SourceTargetPair:
    return SourceTargetPair(
        source_planet_id=source_planet_id,
        target_planet_id=target_planet_id,
        target_owner=target_owner,
        target_category=target_category,
        source_ships=source_ships,
        target_ships=target_ships,
        target_production=target_production,
        source_position=source_position,
        target_position=target_position,
        distance=distance,
        rough_travel_ticks=rough_travel_ticks,
        source_affordable_ships=source_affordable_ships,
        target_is_comet=target_is_comet,
    )


class PlannerShipEstimationTests(unittest.TestCase):
    def test_estimation_exports_and_types_are_available(self) -> None:
        self.assertEqual(DEFAULT_CAPTURE_BUFFER_SHIPS, 1)
        self.assertEqual(ShipEstimateStatus.AFFORDABLE.value, "affordable")
        self.assertEqual(
            ShipEstimateStatus.INSUFFICIENT_SOURCE_SHIPS.value,
            "insufficient_source_ships",
        )
        self.assertEqual(ShipEstimateStatus.INVALID_TARGET.value, "invalid_target")
        self.assertIsNotNone(estimate_required_ships_for_pair)
        self.assertIsNotNone(launch_candidate_from_pair)
        self.assertIsNotNone(estimate_source_target_pairs)

    def test_estimate_type_is_frozen(self) -> None:
        estimate = ShipEstimate(
            target_category=TargetCategory.NEUTRAL,
            required_ships=6,
            source_available_ships=20,
            target_projected_ships=5,
            production_added=0,
            buffer_ships=1,
            status=ShipEstimateStatus.AFFORDABLE,
        )

        with self.assertRaises(FrozenInstanceError):
            estimate.required_ships = 7

    def test_neutral_target_uses_target_ships_plus_buffer_only(self) -> None:
        estimate = estimate_required_ships_for_pair(
            pair(target_category=TargetCategory.NEUTRAL, target_ships=5, target_production=9)
        )

        self.assertEqual(estimate.target_category, TargetCategory.NEUTRAL)
        self.assertEqual(estimate.production_added, 0)
        self.assertEqual(estimate.target_projected_ships, 5)
        self.assertEqual(estimate.buffer_ships, DEFAULT_CAPTURE_BUFFER_SHIPS)
        self.assertEqual(estimate.required_ships, 6)
        self.assertEqual(estimate.status, ShipEstimateStatus.AFFORDABLE)

    def test_enemy_target_includes_production_over_rough_travel_ticks(self) -> None:
        estimate = estimate_required_ships_for_pair(
            pair(
                target_owner=2,
                target_category=TargetCategory.ENEMY,
                target_ships=5,
                target_production=2,
                rough_travel_ticks=4,
            )
        )

        self.assertEqual(estimate.production_added, 8)
        self.assertEqual(estimate.target_projected_ships, 13)
        self.assertEqual(estimate.required_ships, 14)

    def test_own_target_uses_one_ship_reinforcement_estimate(self) -> None:
        source_pair = pair(
            target_owner=0,
            target_category=TargetCategory.OWN,
            target_ships=50,
            target_production=5,
            rough_travel_ticks=6,
            source_affordable_ships=3,
        )

        estimate = estimate_required_ships_for_pair(source_pair)
        launch = launch_candidate_from_pair(source_pair)

        self.assertEqual(estimate.target_category, TargetCategory.OWN)
        self.assertEqual(estimate.production_added, 0)
        self.assertEqual(estimate.target_projected_ships, 50)
        self.assertEqual(estimate.required_ships, 1)
        self.assertEqual(estimate.status, ShipEstimateStatus.AFFORDABLE)
        self.assertEqual(launch.ships, 1)

    def test_exact_zero_capture_is_not_treated_as_sufficient(self) -> None:
        source_exactly_equal_to_defenders = pair(
            target_ships=5,
            source_ships=5,
            source_affordable_ships=5,
        )

        estimate = estimate_required_ships_for_pair(source_exactly_equal_to_defenders)

        self.assertEqual(estimate.required_ships, 6)
        self.assertEqual(estimate.status, ShipEstimateStatus.INSUFFICIENT_SOURCE_SHIPS)
        self.assertIsNone(launch_candidate_from_pair(source_exactly_equal_to_defenders))

    def test_affordable_estimate_emits_launch_candidate(self) -> None:
        source_pair = pair(source_planet_id=7, target_ships=3, source_affordable_ships=10)

        launch = launch_candidate_from_pair(source_pair)

        self.assertEqual(
            launch,
            LaunchCandidate(
                source_planet_id=7,
                angle=angle_to_point(source_pair.source_position, source_pair.target_position),
                ships=4,
                player_id=None,
            ),
        )

    def test_insufficient_source_ships_returns_no_launch(self) -> None:
        source_pair = pair(target_ships=10, source_affordable_ships=10)

        estimate = estimate_required_ships_for_pair(source_pair)

        self.assertEqual(estimate.required_ships, 11)
        self.assertEqual(estimate.status, ShipEstimateStatus.INSUFFICIENT_SOURCE_SHIPS)
        self.assertIsNone(launch_candidate_from_pair(source_pair))

    def test_launch_angle_uses_existing_forecast_angle_helper(self) -> None:
        source_pair = pair(source_position=(0.0, 0.0), target_position=(0.0, 5.0))

        launch = launch_candidate_from_pair(source_pair)

        self.assertIsNotNone(launch)
        self.assertAlmostEqual(launch.angle, math.pi / 2.0)

    def test_batch_helper_preserves_input_order(self) -> None:
        first = pair(source_planet_id=3, target_planet_id=20, target_ships=1)
        second = pair(source_planet_id=1, target_planet_id=10, target_ships=2)

        estimated = estimate_source_target_pairs((first, second))

        self.assertEqual(tuple(item.pair for item in estimated), (first, second))
        self.assertEqual(tuple(item.launch.source_planet_id for item in estimated), (3, 1))
        self.assertTrue(all(isinstance(item, EstimatedPair) for item in estimated))

    def test_zero_target_ships_requires_positive_launch(self) -> None:
        estimate = estimate_required_ships_for_pair(pair(target_ships=0))

        self.assertEqual(estimate.target_projected_ships, 0)
        self.assertEqual(estimate.required_ships, 1)
        self.assertEqual(launch_candidate_from_pair(pair(target_ships=0)).ships, 1)

    def test_negative_target_or_source_edge_cases_are_invalid(self) -> None:
        invalid_pairs = (
            pair(target_ships=-1),
            pair(target_production=-1),
            pair(rough_travel_ticks=-1),
            pair(source_affordable_ships=-1),
        )

        for source_pair in invalid_pairs:
            with self.subTest(source_pair=source_pair):
                estimate = estimate_required_ships_for_pair(source_pair)
                self.assertEqual(estimate.status, ShipEstimateStatus.INVALID_TARGET)
                self.assertEqual(estimate.required_ships, 0)
                self.assertIsNone(launch_candidate_from_pair(source_pair))

    def test_invalid_target_category_is_reported_without_launch(self) -> None:
        source_pair = pair(target_category="invalid")  # type: ignore[arg-type]

        estimate = estimate_required_ships_for_pair(source_pair)

        self.assertEqual(estimate.status, ShipEstimateStatus.INVALID_TARGET)
        self.assertIsNone(launch_candidate_from_pair(source_pair))

    def test_comet_target_metadata_does_not_change_estimation_semantics(self) -> None:
        ordinary = estimate_required_ships_for_pair(pair(target_ships=4, target_is_comet=False))
        comet = estimate_required_ships_for_pair(pair(target_ships=4, target_is_comet=True))

        self.assertEqual(comet, ordinary)

    def test_estimation_does_not_mutate_pair(self) -> None:
        source_pair = pair(target_category=TargetCategory.ENEMY, target_production=1)
        before = source_pair

        estimate_required_ships_for_pair(source_pair)
        launch_candidate_from_pair(source_pair)
        estimate_source_target_pairs((source_pair,))

        self.assertEqual(source_pair, before)

    def test_no_simulator_rollout_is_called(self) -> None:
        with patch("ow_sim.whatif.simulate_launch_orders") as simulate_launch_orders:
            estimate_required_ships_for_pair(pair())
            launch_candidate_from_pair(pair())
            estimate_source_target_pairs((pair(),))

        simulate_launch_orders.assert_not_called()

    def test_generate_candidates_returns_empty_for_empty_state(self) -> None:
        state = GameState(player_id=0)

        self.assertEqual(generate_candidates(state), ())
        self.assertEqual(generate_candidates(state), generate_candidates(state))


if __name__ == "__main__":
    unittest.main()
