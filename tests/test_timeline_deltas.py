"""Tests for Cycle 10 one-tick state delta helpers."""

from __future__ import annotations

import copy
from dataclasses import FrozenInstanceError
import json
import math
import unittest
from pathlib import Path

from ow_sim.collision import FleetRemovalReason
from ow_sim.combat import PlanetCombatResult
from ow_sim.constants import GEOMETRY_ABS_TOL
from ow_sim.forecast import fleet_path_for_tick, planet_path_for_tick
from ow_sim.state import CometGroup, Fleet, GameState, Planet
from ow_sim.timeline import (
    FleetTickDelta,
    OneTickStateDelta,
    PlanetTickDelta,
    fleet_tick_deltas,
    one_tick_event_summary,
    one_tick_state_delta,
    planet_tick_deltas,
)


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def load_state(name: str) -> GameState:
    with (FIXTURE_DIR / name).open(encoding="utf-8") as fh:
        return GameState.from_obs(json.load(fh))


def fleet_at(
    fleet_id: int,
    x: float,
    y: float,
    *,
    owner: int = 0,
    angle: float = 0.0,
    ships: int = 1,
) -> Fleet:
    return Fleet(
        fleet_id=fleet_id,
        owner=owner,
        x=x,
        y=y,
        angle=angle,
        from_planet_id=0,
        ships=ships,
        raw=(fleet_id, owner, x, y, angle, 0, ships),
    )


def planet_at(
    planet_id: int,
    x: float,
    y: float,
    *,
    owner: int = -1,
    ships: int = 0,
    radius: float = 0.2,
    production: int = 1,
    is_comet: bool = False,
) -> Planet:
    return Planet(
        planet_id=planet_id,
        owner=owner,
        x=x,
        y=y,
        radius=radius,
        ships=ships,
        production=production,
        is_comet=is_comet,
        raw=(planet_id, owner, x, y, radius, ships, production),
    )


class TimelineDeltaTests(unittest.TestCase):
    def assertPointAlmostEqual(
        self,
        actual: tuple[float, float],
        expected: tuple[float, float],
    ) -> None:
        self.assertAlmostEqual(actual[0], expected[0], delta=GEOMETRY_ABS_TOL)
        self.assertAlmostEqual(actual[1], expected[1], delta=GEOMETRY_ABS_TOL)

    def test_no_fleets_still_produces_planet_movement_deltas(self) -> None:
        planet = planet_at(1, 0.5, 0.0)
        state = GameState(tick=0, planets=(planet,))

        delta = one_tick_state_delta(state)

        self.assertEqual(delta.fleet_deltas, ())
        self.assertEqual(len(delta.planet_deltas), 1)
        self.assertEqual(delta.planet_deltas[0].planet_id, planet.planet_id)
        self.assertEqual(delta.planet_deltas[0].old_position, planet.position)
        self.assertEqual(delta.planet_deltas[0].new_position, planet.position)
        self.assertFalse(delta.planet_deltas[0].has_arrivals)

    def test_fleet_without_removal_reports_path_and_active_status(self) -> None:
        fleet = fleet_at(10, 0.0, 0.0)
        state = GameState(tick=0, fleets=(fleet,))

        (delta,) = fleet_tick_deltas(state)

        self.assertEqual(delta.fleet_id, fleet.fleet_id)
        self.assertEqual((delta.old_position, delta.new_position), fleet_path_for_tick(fleet))
        self.assertFalse(delta.removed)
        self.assertIsNone(delta.removal_event)

    def test_planet_hit_fleet_delta_reports_planet_removal_event(self) -> None:
        target = planet_at(1, 0.5, 0.0, owner=-1, ships=0)
        fleet = fleet_at(10, 0.0, 0.0, owner=0)
        state = GameState(tick=0, planets=(target,), fleets=(fleet,))

        (delta,) = fleet_tick_deltas(state)

        self.assertTrue(delta.removed)
        self.assertIsNotNone(delta.removal_event)
        self.assertEqual(delta.removal_event.reason, FleetRemovalReason.PLANET)
        self.assertEqual(delta.removal_event.planet_id, target.planet_id)

    def test_bounds_and_sun_removals_are_reflected_in_fleet_deltas(self) -> None:
        bounds_fleet = fleet_at(20, 99.5, 0.0)
        sun_fleet = fleet_at(30, 49.0, 50.0)
        state = GameState(tick=0, fleets=(bounds_fleet, sun_fleet))

        deltas = fleet_tick_deltas(state)

        self.assertEqual(
            tuple(delta.removal_event.reason for delta in deltas),
            (FleetRemovalReason.BOUNDS, FleetRemovalReason.SUN),
        )
        self.assertEqual(tuple(delta.removed for delta in deltas), (True, True))

    def test_fleet_delta_order_follows_state_fleet_order(self) -> None:
        fleets = (
            fleet_at(2, 0.0, 0.0),
            fleet_at(1, 10.0, 0.0),
            fleet_at(3, 20.0, 0.0),
        )
        state = GameState(tick=0, fleets=fleets)

        self.assertEqual(
            tuple(delta.fleet_id for delta in fleet_tick_deltas(state)),
            (2, 1, 3),
        )

    def test_planet_delta_order_follows_state_planet_order(self) -> None:
        planets = (
            planet_at(2, 10.0, 0.0),
            planet_at(1, 20.0, 0.0),
            planet_at(3, 30.0, 0.0),
        )
        state = GameState(tick=0, planets=planets)

        self.assertEqual(
            tuple(delta.planet_id for delta in planet_tick_deltas(state)),
            (2, 1, 3),
        )

    def test_static_planet_delta_old_and_new_positions_are_stable(self) -> None:
        planet = planet_at(1, 0.5, 0.0)
        state = GameState(tick=0, planets=(planet,))

        (delta,) = planet_tick_deltas(state)

        self.assertEqual(delta.old_position, planet.position)
        self.assertEqual(delta.new_position, planet.position)

    def test_orbiting_planet_delta_uses_planet_path_helper(self) -> None:
        initial = planet_at(30, 60.0, 50.0, radius=0.5)
        current = planet_at(30, 60.0, 50.0, radius=0.5)
        state = GameState(
            tick=1,
            planets=(current,),
            initial_planets=(initial,),
            angular_velocity=math.pi / 2.0,
        )

        (delta,) = planet_tick_deltas(state)
        old_position, new_position = planet_path_for_tick(state, current.planet_id)

        self.assertPointAlmostEqual(delta.old_position, old_position)
        self.assertPointAlmostEqual(delta.new_position, new_position)

    def test_comet_planet_delta_uses_comet_path_semantics(self) -> None:
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

        (delta,) = planet_tick_deltas(state)

        self.assertEqual(delta.old_position, (0.0, 0.0))
        self.assertEqual(delta.new_position, (1.0, 0.0))

    def test_unprojectable_planet_path_sets_new_position_to_none(self) -> None:
        orbiting_without_initial = planet_at(40, 60.0, 50.0, radius=0.5)
        state = GameState(tick=0, planets=(orbiting_without_initial,))

        (delta,) = planet_tick_deltas(state)

        self.assertEqual(delta.old_position, orbiting_without_initial.position)
        self.assertIsNone(delta.new_position)

    def test_combat_result_is_attached_only_for_planet_arrivals(self) -> None:
        target = planet_at(1, 0.5, 0.0, owner=-1, ships=0)
        untouched = planet_at(2, 10.0, 0.0, owner=1, ships=5)
        fleet = fleet_at(10, 0.0, 0.0, owner=0, ships=1)
        state = GameState(tick=0, planets=(target, untouched), fleets=(fleet,))

        target_delta, untouched_delta = planet_tick_deltas(state)

        self.assertTrue(target_delta.has_arrivals)
        self.assertEqual(
            target_delta.combat_result,
            PlanetCombatResult(owner=0, ships=1, winner_owner=0, winner_ships=1),
        )
        self.assertFalse(untouched_delta.has_arrivals)
        self.assertIsNone(untouched_delta.combat_result)

    def test_one_tick_state_delta_reuses_event_summary_facts(self) -> None:
        target = planet_at(1, 0.5, 0.0, owner=-1, ships=0)
        fleet = fleet_at(10, 0.0, 0.0, owner=0)
        state = GameState(tick=0, planets=(target,), fleets=(fleet,))

        delta = one_tick_state_delta(state)

        self.assertEqual(delta.event_summary, one_tick_event_summary(state))
        self.assertIsInstance(delta, OneTickStateDelta)
        self.assertIsInstance(delta.fleet_deltas[0], FleetTickDelta)
        self.assertIsInstance(delta.planet_deltas[0], PlanetTickDelta)

    def test_invalid_dt_raises_value_error(self) -> None:
        state = GameState(
            tick=0,
            planets=(planet_at(1, 0.5, 0.0),),
            fleets=(fleet_at(10, 0.0, 0.0),),
        )

        with self.assertRaises(ValueError):
            fleet_tick_deltas(state, dt=0)
        with self.assertRaises(ValueError):
            planet_tick_deltas(state, dt=0)
        with self.assertRaises(ValueError):
            one_tick_state_delta(state, dt=0)

    def test_delta_result_types_are_frozen_value_objects(self) -> None:
        fleet = fleet_at(10, 0.0, 0.0)
        state = GameState(tick=0, fleets=(fleet,))

        delta = one_tick_state_delta(state)

        with self.assertRaises(FrozenInstanceError):
            delta.fleet_deltas = ()
        with self.assertRaises(FrozenInstanceError):
            delta.fleet_deltas[0].removed = True

    def test_delta_helpers_do_not_mutate_fixture_state(self) -> None:
        state = load_state("kaggle_seed7_2p_step1_fleet.json")
        planets_before = state.planets
        fleets_before = state.fleets
        comets_before = state.comets
        raw_before = copy.deepcopy(state.raw_observation)

        fleet_tick_deltas(state)
        planet_tick_deltas(state)
        one_tick_state_delta(state)

        self.assertEqual(state.planets, planets_before)
        self.assertEqual(state.fleets, fleets_before)
        self.assertEqual(state.comets, comets_before)
        self.assertEqual(state.raw_observation, raw_before)


if __name__ == "__main__":
    unittest.main()
