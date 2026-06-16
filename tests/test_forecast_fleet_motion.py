"""Tests for Cycle 5 fleet speed and straight-line movement helpers."""

from __future__ import annotations

import json
import math
import unittest
from pathlib import Path

from ow_sim.constants import DEFAULT_MAX_FLEET_SPEED, GEOMETRY_ABS_TOL
from ow_sim.forecast import (
    fleet_path_for_tick,
    fleet_position_after_ticks,
    fleet_speed,
    fleet_step_delta,
)
from ow_sim.state import Fleet, GameState


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def load_state(name: str) -> GameState:
    with (FIXTURE_DIR / name).open(encoding="utf-8") as fh:
        return GameState.from_obs(json.load(fh))


class ForecastFleetMotionTests(unittest.TestCase):
    def assertPointAlmostEqual(
        self,
        actual: tuple[float, float],
        expected: tuple[float, float],
    ) -> None:
        self.assertAlmostEqual(actual[0], expected[0], delta=GEOMETRY_ABS_TOL)
        self.assertAlmostEqual(actual[1], expected[1], delta=GEOMETRY_ABS_TOL)

    def test_speed_formula_known_values(self) -> None:
        expected = {
            1: 1.0,
            3: 1.3171255752804119,
            10: 1.9622504486493764,
            100: 3.7216552697590872,
            500: 5.266632225007871,
            1000: DEFAULT_MAX_FLEET_SPEED,
        }

        for ships, speed in expected.items():
            with self.subTest(ships=ships):
                self.assertAlmostEqual(fleet_speed(ships), speed)

    def test_single_ship_speed_is_one(self) -> None:
        self.assertEqual(fleet_speed(1), 1.0)

    def test_large_fleet_speed_is_capped(self) -> None:
        self.assertEqual(fleet_speed(10_000), DEFAULT_MAX_FLEET_SPEED)

    def test_speed_is_monotonic_for_representative_ship_counts(self) -> None:
        ship_counts = (1, 2, 3, 10, 50, 100, 500, 1000, 5000)
        speeds = [fleet_speed(ships) for ships in ship_counts]

        self.assertEqual(speeds, sorted(speeds))

    def test_invalid_ship_counts_raise_value_error(self) -> None:
        for ships in (0, -1, 1.5, True):
            with self.subTest(ships=ships):
                with self.assertRaises(ValueError):
                    fleet_speed(ships)

    def test_cardinal_angle_step_deltas(self) -> None:
        cases = (
            (0.0, (1.0, 0.0)),
            (-math.pi / 2.0, (0.0, -1.0)),
            (math.pi, (-1.0, 0.0)),
            (math.pi / 2.0, (0.0, 1.0)),
        )

        for angle, expected in cases:
            with self.subTest(angle=angle):
                self.assertPointAlmostEqual(fleet_step_delta(angle, 1), expected)

    def test_position_after_ticks_uses_current_position_speed_and_direction(self) -> None:
        fleet = Fleet(
            fleet_id=10,
            owner=0,
            x=12.5,
            y=20.0,
            angle=math.pi / 2.0,
            from_planet_id=3,
            ships=100,
        )
        speed = fleet_speed(fleet.ships)

        self.assertPointAlmostEqual(
            fleet_position_after_ticks(fleet, 3),
            (fleet.x, fleet.y + 3 * speed),
        )

    def test_path_for_tick_returns_dt_one_interval(self) -> None:
        fleet = Fleet(
            fleet_id=11,
            owner=0,
            x=10.0,
            y=10.0,
            angle=0.0,
            from_planet_id=3,
            ships=1,
        )

        self.assertEqual(
            fleet_path_for_tick(fleet),
            ((10.0, 10.0), (11.0, 10.0)),
        )

    def test_path_for_tick_returns_later_interval(self) -> None:
        fleet = Fleet(
            fleet_id=12,
            owner=0,
            x=10.0,
            y=10.0,
            angle=0.0,
            from_planet_id=3,
            ships=1,
        )

        self.assertEqual(
            fleet_path_for_tick(fleet, dt=3),
            ((12.0, 10.0), (13.0, 10.0)),
        )

    def test_official_step1_fleet_moves_to_step2_position(self) -> None:
        step1 = load_state("kaggle_seed7_2p_step1_fleet.json")
        step2 = load_state("kaggle_seed7_2p_step2_fleet.json")
        fleet = step1.fleets[0]
        observed_next = step2.fleets[0]

        self.assertPointAlmostEqual(
            fleet_position_after_ticks(fleet, 1),
            observed_next.position,
        )
        self.assertPointAlmostEqual(
            fleet_path_for_tick(fleet)[1],
            observed_next.position,
        )

    def test_helpers_do_not_mutate_fleet(self) -> None:
        state = load_state("kaggle_seed7_2p_step1_fleet.json")
        fleet = state.fleets[0]
        original = (
            fleet.fleet_id,
            fleet.owner,
            fleet.x,
            fleet.y,
            fleet.angle,
            fleet.from_planet_id,
            fleet.ships,
            fleet.raw,
        )

        fleet_speed(fleet.ships)
        fleet_step_delta(fleet.angle, fleet.ships)
        fleet_position_after_ticks(fleet, 2)
        fleet_path_for_tick(fleet, 2)

        self.assertEqual(
            original,
            (
                fleet.fleet_id,
                fleet.owner,
                fleet.x,
                fleet.y,
                fleet.angle,
                fleet.from_planet_id,
                fleet.ships,
                fleet.raw,
            ),
        )
        self.assertEqual(state.fleets[0], fleet)


if __name__ == "__main__":
    unittest.main()
