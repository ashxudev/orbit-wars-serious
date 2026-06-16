"""Tests for Cycle 6 launch spawning, point aiming, and ETA helpers."""

from __future__ import annotations

import json
import math
import unittest
from pathlib import Path

from ow_sim.constants import GEOMETRY_ABS_TOL
from ow_sim.forecast import (
    angle_from_planet_to_point,
    angle_to_point,
    can_launch_from_planet,
    fleet_position_after_ticks,
    fleet_ticks_to_reach_circle,
    fleet_ticks_to_reach_distance,
    fleet_ticks_to_reach_point,
    launch_fleet,
    launch_spawn_position,
)
from ow_sim.state import GameState, Planet


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def load_state(name: str) -> GameState:
    with (FIXTURE_DIR / name).open(encoding="utf-8") as fh:
        return GameState.from_obs(json.load(fh))


def planet_by_id(state: GameState, planet_id: int) -> Planet:
    for planet in state.planets:
        if planet.planet_id == planet_id:
            return planet
    raise AssertionError(f"missing planet {planet_id}")


class ForecastLaunchArrivalTests(unittest.TestCase):
    def assertPointAlmostEqual(
        self,
        actual: tuple[float, float],
        expected: tuple[float, float],
    ) -> None:
        self.assertAlmostEqual(actual[0], expected[0], delta=GEOMETRY_ABS_TOL)
        self.assertAlmostEqual(actual[1], expected[1], delta=GEOMETRY_ABS_TOL)

    def test_launch_legality_core_rules(self) -> None:
        source = Planet(
            planet_id=3,
            owner=1,
            x=10.0,
            y=20.0,
            radius=2.0,
            ships=5,
            production=1,
        )

        self.assertTrue(can_launch_from_planet(source, player_id=1, ships=5))
        self.assertFalse(can_launch_from_planet(source, player_id=0, ships=3))
        self.assertFalse(can_launch_from_planet(source, player_id=1, ships=6))
        self.assertFalse(can_launch_from_planet(source, player_id=1, ships=0))
        self.assertFalse(can_launch_from_planet(source, player_id=1, ships=-1))

    def test_launch_legality_rejects_invalid_ship_values(self) -> None:
        source = Planet(
            planet_id=3,
            owner=1,
            x=10.0,
            y=20.0,
            radius=2.0,
            ships=5,
            production=1,
        )

        for ships in (1.5, True):
            with self.subTest(ships=ships):
                with self.assertRaises(ValueError):
                    can_launch_from_planet(source, player_id=1, ships=ships)

    def test_spawn_position_cardinal_angles(self) -> None:
        source = Planet(
            planet_id=3,
            owner=1,
            x=10.0,
            y=20.0,
            radius=2.0,
            ships=5,
            production=1,
        )

        self.assertPointAlmostEqual(launch_spawn_position(source, 0.0), (12.1, 20.0))
        self.assertPointAlmostEqual(
            launch_spawn_position(source, math.pi / 2.0),
            (10.0, 22.1),
        )
        self.assertPointAlmostEqual(
            launch_spawn_position(source, math.pi),
            (7.9, 20.0),
        )
        self.assertPointAlmostEqual(
            launch_spawn_position(source, -math.pi / 2.0),
            (10.0, 17.9),
        )

    def test_spawn_position_non_cardinal_angle(self) -> None:
        source = Planet(
            planet_id=3,
            owner=1,
            x=10.0,
            y=20.0,
            radius=2.0,
            ships=5,
            production=1,
        )
        offset = (source.radius + 0.1) / math.sqrt(2.0)

        self.assertPointAlmostEqual(
            launch_spawn_position(source, math.pi / 4.0),
            (source.x + offset, source.y + offset),
        )

    def test_launch_fleet_fields_raw_row_and_non_mutation(self) -> None:
        state = load_state("kaggle_seed7_2p_step0.json")
        source = planet_by_id(state, 0)
        source_before = (
            source.planet_id,
            source.owner,
            source.x,
            source.y,
            source.radius,
            source.ships,
            source.production,
            source.raw,
        )

        fleet = launch_fleet(
            next_fleet_id=state.next_fleet_id,
            player_id=source.owner,
            source=source,
            angle=0.25,
            ships=3,
        )

        self.assertEqual(fleet.fleet_id, state.next_fleet_id)
        self.assertEqual(fleet.owner, source.owner)
        self.assertEqual(fleet.angle, 0.25)
        self.assertEqual(fleet.from_planet_id, source.planet_id)
        self.assertEqual(fleet.ships, 3)
        self.assertPointAlmostEqual(fleet.position, launch_spawn_position(source, 0.25))
        self.assertEqual(
            fleet.raw,
            (
                fleet.fleet_id,
                fleet.owner,
                fleet.x,
                fleet.y,
                fleet.angle,
                fleet.from_planet_id,
                fleet.ships,
            ),
        )
        self.assertEqual(
            source_before,
            (
                source.planet_id,
                source.owner,
                source.x,
                source.y,
                source.radius,
                source.ships,
                source.production,
                source.raw,
            ),
        )
        self.assertEqual(state.fleets, ())

    def test_official_step0_launch_spawn_plus_one_tick_matches_step1_fleet(self) -> None:
        step0 = load_state("kaggle_seed7_2p_step0.json")
        step1 = load_state("kaggle_seed7_2p_step1_fleet.json")
        observed = step1.fleets[0]
        source = planet_by_id(step0, observed.from_planet_id)

        spawned = launch_fleet(
            next_fleet_id=step0.next_fleet_id,
            player_id=observed.owner,
            source=source,
            angle=observed.angle,
            ships=observed.ships,
        )

        self.assertPointAlmostEqual(
            spawned.position,
            launch_spawn_position(source, observed.angle),
        )
        self.assertPointAlmostEqual(
            fleet_position_after_ticks(spawned, 1),
            observed.position,
        )

    def test_angle_to_point_cardinal_and_quadrant_cases(self) -> None:
        origin = (10.0, 20.0)

        self.assertAlmostEqual(angle_to_point(origin, (11.0, 20.0)), 0.0)
        self.assertAlmostEqual(angle_to_point(origin, (10.0, 21.0)), math.pi / 2.0)
        self.assertAlmostEqual(angle_to_point(origin, (9.0, 20.0)), math.pi)
        self.assertAlmostEqual(angle_to_point(origin, (10.0, 19.0)), -math.pi / 2.0)
        self.assertAlmostEqual(angle_to_point(origin, (11.0, 21.0)), math.pi / 4.0)

    def test_angle_from_planet_to_point_uses_planet_center(self) -> None:
        source = Planet(
            planet_id=3,
            owner=1,
            x=10.0,
            y=20.0,
            radius=2.0,
            ships=5,
            production=1,
        )

        self.assertAlmostEqual(
            angle_from_planet_to_point(source, (11.0, 21.0)),
            math.pi / 4.0,
        )

    def test_same_point_aiming_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            angle_to_point((10.0, 20.0), (10.0, 20.0))

    def test_eta_distance_zero_exact_division_and_ceiling(self) -> None:
        self.assertEqual(fleet_ticks_to_reach_distance(0.0, ships=1), 0)
        self.assertEqual(fleet_ticks_to_reach_distance(5.0, ships=1), 5)
        self.assertEqual(fleet_ticks_to_reach_distance(5.1, ships=1), 6)

    def test_eta_to_point_uses_euclidean_distance(self) -> None:
        self.assertEqual(
            fleet_ticks_to_reach_point((0.0, 0.0), (3.0, 4.0), ships=1),
            5,
        )

    def test_eta_to_circle_uses_boundary_distance(self) -> None:
        self.assertEqual(
            fleet_ticks_to_reach_circle(
                start=(0.0, 0.0),
                center=(3.0, 4.0),
                radius=2.0,
                ships=1,
            ),
            3,
        )
        self.assertEqual(
            fleet_ticks_to_reach_circle(
                start=(0.0, 0.0),
                center=(3.0, 4.0),
                radius=10.0,
                ships=1,
            ),
            0,
        )

    def test_eta_helpers_reject_invalid_inputs(self) -> None:
        with self.assertRaises(ValueError):
            fleet_ticks_to_reach_distance(-0.1, ships=1)
        with self.assertRaises(ValueError):
            fleet_ticks_to_reach_distance(1.0, ships=0)
        with self.assertRaises(ValueError):
            fleet_ticks_to_reach_point((0.0, 0.0), (1.0, 0.0), ships=True)
        with self.assertRaises(ValueError):
            fleet_ticks_to_reach_circle(
                start=(0.0, 0.0),
                center=(1.0, 0.0),
                radius=-1.0,
                ships=1,
            )


if __name__ == "__main__":
    unittest.main()
