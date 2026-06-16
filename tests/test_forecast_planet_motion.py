"""Tests for Cycle 3 non-comet planet motion helpers."""

from __future__ import annotations

import json
import math
import unittest
from pathlib import Path

from ow_sim.constants import GEOMETRY_ABS_TOL, ROTATION_RADIUS_LIMIT, SUN_CENTER
from ow_sim.forecast import (
    comet_position_after_ticks,
    is_orbiting_planet,
    planet_initial_angle,
    planet_orbit_radius,
    planet_path_for_tick,
    planet_position_after_ticks,
    planet_position_at_step,
)
from ow_sim.geometry import distance
from ow_sim.state import GameState, Planet


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
STATIC_PLANET_ID = 0
ORBITING_PLANET_ID = 12
COMET_PLANET_ID = 24


def load_state(name: str) -> GameState:
    with (FIXTURE_DIR / name).open(encoding="utf-8") as fh:
        return GameState.from_obs(json.load(fh))


def planet_by_id(state: GameState, planet_id: int) -> Planet:
    for planet in state.planets:
        if planet.planet_id == planet_id:
            return planet
    raise AssertionError(f"missing planet {planet_id}")


def initial_planet_by_id(state: GameState, planet_id: int) -> Planet:
    for planet in state.initial_planets:
        if planet.planet_id == planet_id:
            return planet
    raise AssertionError(f"missing initial planet {planet_id}")


def official_observation_position(
    initial_planet: Planet,
    angular_velocity: float,
    observation_step: int,
) -> tuple[float, float]:
    orbit_radius = planet_orbit_radius(initial_planet)
    initial_angle = planet_initial_angle(initial_planet)
    official_step_index = max(0, observation_step - 1)
    angle = initial_angle + angular_velocity * official_step_index
    return (
        SUN_CENTER[0] + orbit_radius * math.cos(angle),
        SUN_CENTER[1] + orbit_radius * math.sin(angle),
    )


class ForecastPlanetMotionTests(unittest.TestCase):
    def assertPointAlmostEqual(
        self,
        actual: tuple[float, float],
        expected: tuple[float, float],
    ) -> None:
        self.assertAlmostEqual(actual[0], expected[0], delta=GEOMETRY_ABS_TOL)
        self.assertAlmostEqual(actual[1], expected[1], delta=GEOMETRY_ABS_TOL)

    def test_static_planet_position_remains_unchanged(self) -> None:
        state = load_state("kaggle_seed7_2p_step0.json")
        planet = planet_by_id(state, STATIC_PLANET_ID)

        self.assertFalse(is_orbiting_planet(planet))
        self.assertPointAlmostEqual(
            planet_position_at_step(state, STATIC_PLANET_ID, 0),
            planet.position,
        )
        self.assertPointAlmostEqual(
            planet_position_at_step(state, STATIC_PLANET_ID, 80),
            planet.position,
        )

    def test_orbiting_planet_step_zero_equals_initial_position(self) -> None:
        state = load_state("kaggle_seed7_2p_step0.json")
        initial = initial_planet_by_id(state, ORBITING_PLANET_ID)

        self.assertTrue(is_orbiting_planet(initial))
        self.assertPointAlmostEqual(
            planet_position_at_step(state, ORBITING_PLANET_ID, 0),
            initial.position,
        )

    def test_orbiting_planet_later_step_matches_official_fixture(self) -> None:
        state = load_state("kaggle_seed7_2p_step50_comet.json")
        observed = planet_by_id(state, ORBITING_PLANET_ID)

        self.assertPointAlmostEqual(
            planet_position_at_step(state, ORBITING_PLANET_ID, state.step),
            observed.position,
        )

    def test_orbit_radius_remains_constant_for_orbiting_planets(self) -> None:
        state = load_state("kaggle_seed7_2p_step50_comet.json")
        initial = initial_planet_by_id(state, ORBITING_PLANET_ID)
        projected = planet_position_at_step(state, ORBITING_PLANET_ID, state.step)

        self.assertIsNotNone(projected)
        self.assertAlmostEqual(
            planet_orbit_radius(initial),
            distance(projected, SUN_CENTER),
            delta=GEOMETRY_ABS_TOL,
        )

    def test_boundary_classification_uses_strict_rotation_threshold(self) -> None:
        inside = Planet(
            planet_id=100,
            owner=-1,
            x=80.0,
            y=50.0,
            radius=ROTATION_RADIUS_LIMIT - 30.0 - 0.001,
            ships=0,
            production=0,
        )
        boundary = Planet(
            planet_id=101,
            owner=-1,
            x=80.0,
            y=50.0,
            radius=ROTATION_RADIUS_LIMIT - 30.0,
            ships=0,
            production=0,
        )

        self.assertTrue(is_orbiting_planet(inside))
        self.assertFalse(is_orbiting_planet(boundary))

    def test_position_after_ticks_uses_state_step_plus_dt(self) -> None:
        state = load_state("kaggle_seed7_2p_step50_comet.json")
        initial = initial_planet_by_id(state, ORBITING_PLANET_ID)
        expected = official_observation_position(
            initial,
            state.angular_velocity,
            state.step + 1,
        )

        self.assertPointAlmostEqual(
            planet_position_after_ticks(state, ORBITING_PLANET_ID, 1),
            expected,
        )

    def test_planet_path_for_tick_returns_one_tick_old_new_positions(self) -> None:
        state = load_state("kaggle_seed7_2p_step50_comet.json")
        observed = planet_by_id(state, ORBITING_PLANET_ID)
        initial = initial_planet_by_id(state, ORBITING_PLANET_ID)
        expected_new = official_observation_position(
            initial,
            state.angular_velocity,
            state.step + 1,
        )

        path = planet_path_for_tick(state, ORBITING_PLANET_ID)

        self.assertIsNotNone(path)
        old_position, new_position = path
        self.assertPointAlmostEqual(old_position, observed.position)
        self.assertPointAlmostEqual(new_position, expected_new)

    def test_comet_planets_use_path_projection(self) -> None:
        state = load_state("kaggle_seed7_2p_step50_comet.json")
        comet_position = comet_position_after_ticks(state, COMET_PLANET_ID, 0)

        self.assertIsNotNone(comet_position)
        self.assertPointAlmostEqual(
            planet_position_at_step(state, COMET_PLANET_ID, state.step),
            comet_position,
        )
        self.assertPointAlmostEqual(
            planet_position_after_ticks(state, COMET_PLANET_ID, 0),
            comet_position,
        )

    def test_missing_initial_planets_does_not_crash(self) -> None:
        with (FIXTURE_DIR / "kaggle_seed7_2p_step0.json").open(encoding="utf-8") as fh:
            obs = json.load(fh)
        obs.pop("initial_planets")
        state = GameState.from_obs(obs)
        static_planet = planet_by_id(state, STATIC_PLANET_ID)

        self.assertPointAlmostEqual(
            planet_position_at_step(state, STATIC_PLANET_ID, 80),
            static_planet.position,
        )
        self.assertIsNone(planet_position_at_step(state, ORBITING_PLANET_ID, 80))
