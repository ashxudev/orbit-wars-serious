"""Tests for Cycle 7 fleet collision and removal query helpers."""

from __future__ import annotations

import copy
import json
import math
import unittest
from pathlib import Path
from unittest.mock import patch

from ow_sim.collision import (
    FleetRemovalReason,
    first_planet_hit_for_fleet_tick,
    fleet_hits_planet_on_tick,
    fleet_hits_planet_path,
    fleet_hits_sun_on_tick,
    fleet_is_out_of_bounds_after_tick,
    fleet_removal_event_for_tick,
)
from ow_sim.forecast import planet_path_for_tick
from ow_sim.state import CometGroup, Fleet, GameState, Planet


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def load_state(name: str) -> GameState:
    with (FIXTURE_DIR / name).open(encoding="utf-8") as fh:
        return GameState.from_obs(json.load(fh))


def fleet_at(
    x: float,
    y: float,
    *,
    angle: float = 0.0,
    ships: int = 1,
    fleet_id: int = 7,
) -> Fleet:
    return Fleet(
        fleet_id=fleet_id,
        owner=0,
        x=x,
        y=y,
        angle=angle,
        from_planet_id=0,
        ships=ships,
    )


def planet_at(
    planet_id: int,
    x: float,
    y: float,
    *,
    radius: float,
    is_comet: bool = False,
) -> Planet:
    return Planet(
        planet_id=planet_id,
        owner=-1,
        x=x,
        y=y,
        radius=radius,
        ships=0,
        production=0,
        is_comet=is_comet,
    )


def state_with_planets(*planets: Planet) -> GameState:
    return GameState(tick=0, planets=tuple(planets))


class CollisionQueryTests(unittest.TestCase):
    def test_static_planet_hit_miss_and_tangent_touch(self) -> None:
        fleet = fleet_at(0.0, 0.0)

        hit_planet = planet_at(1, 0.5, 0.0, radius=0.1)
        miss_planet = planet_at(2, 0.5, 1.2, radius=0.1)
        tangent_planet = planet_at(3, 0.5, 1.0, radius=1.0)

        self.assertTrue(
            fleet_hits_planet_on_tick(state_with_planets(hit_planet), fleet, hit_planet)
        )
        self.assertFalse(
            fleet_hits_planet_on_tick(state_with_planets(miss_planet), fleet, miss_planet)
        )
        self.assertTrue(
            fleet_hits_planet_on_tick(
                state_with_planets(tangent_planet),
                fleet,
                tangent_planet,
            )
        )

    def test_direct_planet_path_hit_matches_swept_pair_semantics(self) -> None:
        self.assertTrue(
            fleet_hits_planet_path(
                fleet_old=(0.0, 0.0),
                fleet_new=(1.0, 0.0),
                planet_old=(0.5, 0.5),
                planet_new=(0.5, -0.5),
                planet_radius=0.1,
            )
        )
        self.assertFalse(
            fleet_hits_planet_path(
                fleet_old=(0.0, 0.0),
                fleet_new=(1.0, 0.0),
                planet_old=(0.5, 2.0),
                planet_new=(0.5, 3.0),
                planet_radius=0.1,
            )
        )

    def test_first_hit_uses_state_planet_order(self) -> None:
        fleet = fleet_at(0.0, 0.0)
        later_on_path = planet_at(20, 0.8, 0.0, radius=0.2)
        earlier_on_path = planet_at(10, 0.2, 0.0, radius=0.2)
        state = state_with_planets(later_on_path, earlier_on_path)

        self.assertEqual(first_planet_hit_for_fleet_tick(state, fleet), 20)

    def test_moving_orbiting_planet_collision_uses_planet_path(self) -> None:
        initial = planet_at(30, 60.0, 50.0, radius=0.5)
        current = planet_at(30, 60.0, 50.0, radius=0.5)
        state = GameState(
            tick=1,
            planets=(current,),
            initial_planets=(initial,),
            angular_velocity=math.pi / 2.0,
        )
        fleet = fleet_at(49.0, 60.0)

        planet_old, planet_new = planet_path_for_tick(state, current.planet_id)

        self.assertEqual(planet_old, current.position)
        self.assertEqual(planet_new, (50.0, 60.0))
        self.assertFalse(
            fleet_hits_planet_path(
                (49.0, 60.0),
                (50.0, 60.0),
                current.position,
                current.position,
                current.radius,
            )
        )
        self.assertTrue(fleet_hits_planet_on_tick(state, fleet, current))

    def test_active_comet_collision_interval_can_hit(self) -> None:
        comet = planet_at(24, 0.0, 0.0, radius=0.2, is_comet=True)
        state = GameState(
            tick=50,
            planets=(comet,),
            comet_planet_ids=frozenset({24}),
            comets=(
                CometGroup(
                    planet_ids=(24,),
                    paths=(((0.0, 0.0), (1.0, 0.0)),),
                    path_index=0,
                ),
            ),
        )

        self.assertTrue(fleet_hits_planet_on_tick(state, fleet_at(0.0, 0.0), comet))
        self.assertEqual(first_planet_hit_for_fleet_tick(state, fleet_at(0.0, 0.0)), 24)

    def test_first_placement_comet_collision_check_false_skips_hit(self) -> None:
        comet = planet_at(24, -99.0, -99.0, radius=0.2, is_comet=True)
        state = GameState(
            tick=50,
            planets=(comet,),
            comet_planet_ids=frozenset({24}),
            comets=(
                CometGroup(
                    planet_ids=(24,),
                    paths=(((0.0, 0.0), (1.0, 0.0)),),
                    path_index=-1,
                ),
            ),
        )

        self.assertFalse(fleet_hits_planet_on_tick(state, fleet_at(0.0, 0.0), comet))
        self.assertIsNone(first_planet_hit_for_fleet_tick(state, fleet_at(0.0, 0.0)))

    def test_missing_comet_path_returns_no_invented_hit(self) -> None:
        comet = planet_at(24, 0.0, 0.0, radius=0.2, is_comet=True)
        state = GameState(
            tick=50,
            planets=(comet,),
            comet_planet_ids=frozenset({24}),
            comets=(),
        )

        self.assertFalse(fleet_hits_planet_on_tick(state, fleet_at(0.0, 0.0), comet))
        self.assertIsNone(first_planet_hit_for_fleet_tick(state, fleet_at(0.0, 0.0)))

    def test_out_of_bounds_uses_new_position_and_inclusive_boundary(self) -> None:
        self.assertTrue(fleet_is_out_of_bounds_after_tick(fleet_at(99.5, 50.0)))
        self.assertFalse(fleet_is_out_of_bounds_after_tick(fleet_at(99.0, 50.0)))

    def test_sun_hit_uses_strict_radius(self) -> None:
        self.assertTrue(fleet_hits_sun_on_tick(fleet_at(49.0, 50.0)))
        self.assertFalse(fleet_hits_sun_on_tick(fleet_at(49.0, 40.0)))

    def test_planet_hit_takes_priority_over_sun(self) -> None:
        planet = planet_at(1, 49.5, 50.0, radius=0.1)
        state = GameState(
            tick=0,
            planets=(planet,),
            initial_planets=(planet,),
            angular_velocity=0.0,
        )
        event = fleet_removal_event_for_tick(state, fleet_at(49.0, 50.0))

        self.assertIsNotNone(event)
        self.assertEqual(event.reason, FleetRemovalReason.PLANET)
        self.assertEqual(event.planet_id, planet.planet_id)

    def test_planet_hit_takes_priority_over_bounds(self) -> None:
        planet = planet_at(1, 100.0, 50.0, radius=0.1)
        state = state_with_planets(planet)
        event = fleet_removal_event_for_tick(state, fleet_at(99.5, 50.0))

        self.assertIsNotNone(event)
        self.assertEqual(event.reason, FleetRemovalReason.PLANET)
        self.assertEqual(event.planet_id, planet.planet_id)

    def test_bounds_takes_priority_before_sun_check(self) -> None:
        state = GameState(tick=0)

        with patch(
            "ow_sim.collision.segment_hits_sun",
            side_effect=AssertionError("sun check should not run after bounds"),
        ):
            event = fleet_removal_event_for_tick(state, fleet_at(99.5, 50.0))

        self.assertIsNotNone(event)
        self.assertEqual(event.reason, FleetRemovalReason.BOUNDS)
        self.assertIsNone(event.planet_id)

    def test_sun_event_reports_segment_when_no_planet_or_bounds_hit(self) -> None:
        event = fleet_removal_event_for_tick(GameState(tick=0), fleet_at(49.0, 50.0))

        self.assertIsNotNone(event)
        self.assertEqual(event.reason, FleetRemovalReason.SUN)
        self.assertIsNone(event.planet_id)
        self.assertEqual(event.old_position, (49.0, 50.0))
        self.assertEqual(event.new_position, (50.0, 50.0))

    def test_invalid_dt_values_raise_value_error(self) -> None:
        planet = planet_at(1, 0.5, 0.0, radius=0.1)
        state = state_with_planets(planet)
        fleet = fleet_at(0.0, 0.0)

        with self.assertRaises(ValueError):
            fleet_hits_planet_on_tick(state, fleet, planet, dt=0)
        with self.assertRaises(ValueError):
            first_planet_hit_for_fleet_tick(state, fleet, dt=0)
        with self.assertRaises(ValueError):
            fleet_is_out_of_bounds_after_tick(fleet, dt=0)
        with self.assertRaises(ValueError):
            fleet_hits_sun_on_tick(fleet, dt=0)
        with self.assertRaises(ValueError):
            fleet_removal_event_for_tick(state, fleet, dt=0)

    def test_collision_queries_do_not_mutate_fixture_state(self) -> None:
        state = load_state("kaggle_seed7_2p_step1_fleet.json")
        fleet = state.fleets[0]
        planets_before = state.planets
        fleets_before = state.fleets
        raw_before = copy.deepcopy(state.raw_observation)

        fleet_removal_event_for_tick(state, fleet)
        first_planet_hit_for_fleet_tick(state, fleet)
        fleet_is_out_of_bounds_after_tick(fleet)
        fleet_hits_sun_on_tick(fleet)

        self.assertEqual(state.planets, planets_before)
        self.assertEqual(state.fleets, fleets_before)
        self.assertEqual(state.raw_observation, raw_before)


if __name__ == "__main__":
    unittest.main()
