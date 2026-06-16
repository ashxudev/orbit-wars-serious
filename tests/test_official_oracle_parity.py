"""Whole-simulator parity tests against the official Orbit Wars interpreter."""

from __future__ import annotations

import copy
import io
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from ow_sim.forecast import angle_to_point
from ow_sim.state import GameState, Planet
from ow_sim.whatif import LaunchOrder, simulate_launch_orders


ORACLE_ABS_TOL = 1e-7
PRE_COMET_HORIZON = 20


def make_official_env(seed: int = 7, players: int = 2):
    """Return a local official Orbit Wars environment reset for ``players``."""

    repo_root = Path(__file__).resolve().parents[1]
    site_packages = next(
        (repo_root / ".venv" / "lib").glob("python*/site-packages"),
        None,
    )
    if site_packages is None:
        raise RuntimeError("Could not find local .venv site-packages")

    site_path = str(site_packages)
    if site_path not in sys.path:
        sys.path.insert(0, site_path)

    # The package import emits optional-environment warnings on some platforms.
    # They are unrelated to Orbit Wars and make test output noisy.
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        from kaggle_environments import make

        env = make("orbit_wars", configuration={"seed": seed}, debug=True)
        env.reset(players)
    return env


def official_player_zero_state(env) -> GameState:
    return GameState.from_obs(copy.deepcopy(dict(env.state[0].observation)))


def planet_by_id(state: GameState, planet_id: int) -> Planet:
    for planet in state.planets:
        if planet.planet_id == planet_id:
            return planet
    raise AssertionError(f"missing planet {planet_id}")


class OfficialOracleParityTests(unittest.TestCase):
    def assertPointAlmostEqual(
        self,
        actual: tuple[float, float],
        expected: tuple[float, float],
    ) -> None:
        self.assertAlmostEqual(actual[0], expected[0], delta=ORACLE_ABS_TOL)
        self.assertAlmostEqual(actual[1], expected[1], delta=ORACLE_ABS_TOL)

    def assertStateMatchesOfficial(
        self,
        actual: GameState,
        expected: GameState,
        *,
        label: str,
    ) -> None:
        with self.subTest(label=label, field="metadata"):
            self.assertEqual(actual.tick, expected.tick)
            self.assertEqual(actual.player_id, expected.player_id)
            self.assertEqual(actual.next_fleet_id, expected.next_fleet_id)
            self.assertEqual(actual.angular_velocity, expected.angular_velocity)
            self.assertEqual(actual.comet_planet_ids, expected.comet_planet_ids)
            self.assertEqual(len(actual.comets), len(expected.comets))
            self.assertEqual(len(actual.planets), len(expected.planets))
            self.assertEqual(len(actual.fleets), len(expected.fleets))

        for index, (actual_planet, expected_planet) in enumerate(
            zip(actual.planets, expected.planets)
        ):
            with self.subTest(label=label, planet_index=index):
                self.assertEqual(actual_planet.planet_id, expected_planet.planet_id)
                self.assertEqual(actual_planet.owner, expected_planet.owner)
                self.assertPointAlmostEqual(
                    actual_planet.position,
                    expected_planet.position,
                )
                self.assertEqual(actual_planet.radius, expected_planet.radius)
                self.assertEqual(actual_planet.ships, expected_planet.ships)
                self.assertEqual(actual_planet.production, expected_planet.production)

        for index, (actual_fleet, expected_fleet) in enumerate(
            zip(actual.fleets, expected.fleets)
        ):
            with self.subTest(label=label, fleet_index=index):
                self.assertEqual(actual_fleet.fleet_id, expected_fleet.fleet_id)
                self.assertEqual(actual_fleet.owner, expected_fleet.owner)
                self.assertPointAlmostEqual(
                    actual_fleet.position,
                    expected_fleet.position,
                )
                self.assertEqual(actual_fleet.angle, expected_fleet.angle)
                self.assertEqual(
                    actual_fleet.from_planet_id,
                    expected_fleet.from_planet_id,
                )
                self.assertEqual(actual_fleet.ships, expected_fleet.ships)

    def test_launch_then_idle_matches_official_for_twenty_pre_comet_ticks(self) -> None:
        env = make_official_env()
        initial_state = official_player_zero_state(env)
        order = LaunchOrder(source_planet_id=0, angle=0.0, ships=3, player_id=0)

        for tick in range(1, PRE_COMET_HORIZON + 1):
            action = [[[0, 0.0, 3]], []] if tick == 1 else [[], []]
            env.step(action)
            expected = official_player_zero_state(env)
            actual = simulate_launch_orders(initial_state, (order,), ticks=tick)

            self.assertStateMatchesOfficial(
                actual,
                expected,
                label=f"launch-idle tick {tick}",
            )

        self.assertEqual(expected.tick, PRE_COMET_HORIZON)
        self.assertEqual(expected.fleets, ())

    def test_scripted_neutral_capture_matches_official_until_combat_resolution(self) -> None:
        env = make_official_env()
        initial_state = official_player_zero_state(env)
        source = initial_state.planets[0]
        target = initial_state.planets[4]
        launch_angle = angle_to_point(source.position, target.position)
        order = LaunchOrder(
            source_planet_id=source.planet_id,
            angle=launch_angle,
            ships=10,
            player_id=0,
        )

        expected = initial_state
        actual = initial_state
        for tick in range(1, 6):
            action = (
                [[[source.planet_id, launch_angle, 10]], []]
                if tick == 1
                else [[], []]
            )
            env.step(action)
            expected = official_player_zero_state(env)
            actual = simulate_launch_orders(initial_state, (order,), ticks=tick)

            self.assertStateMatchesOfficial(
                actual,
                expected,
                label=f"capture tick {tick}",
            )

        expected_target = planet_by_id(expected, target.planet_id)
        actual_target = planet_by_id(actual, target.planet_id)
        self.assertEqual(expected_target.owner, 0)
        self.assertEqual(actual_target.owner, 0)
        self.assertEqual(expected_target.ships, 1)
        self.assertEqual(actual_target.ships, 1)
        self.assertEqual(expected.fleets, ())
        self.assertEqual(actual.fleets, ())


if __name__ == "__main__":
    unittest.main()
