"""Tests for Cycle 14 launch insertion plus rollout composition."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from ow_sim.constants import GEOMETRY_ABS_TOL
from ow_sim.state import CometGroup, Fleet, GameState, Planet
from ow_sim.timeline import next_game_state_after_tick, simulate_ticks
from ow_sim.whatif import LaunchOrder, apply_launch_orders, simulate_launch_orders


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def load_state(name: str) -> GameState:
    with (FIXTURE_DIR / name).open(encoding="utf-8") as fh:
        return GameState.from_obs(json.load(fh))


def planet_at(
    planet_id: int,
    *,
    owner: int,
    ships: int,
    x: float = 10.0,
    y: float = 20.0,
    radius: float = 2.0,
    production: int = 1,
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


def fleet_at(fleet_id: int) -> Fleet:
    return Fleet(
        fleet_id=fleet_id,
        owner=0,
        x=0.0,
        y=0.0,
        angle=0.0,
        from_planet_id=99,
        ships=1,
        raw=(fleet_id, 0, 0.0, 0.0, 0.0, 99, 1),
    )


class WhatIfCompositionTests(unittest.TestCase):
    def assertPointAlmostEqual(
        self,
        actual: tuple[float, float],
        expected: tuple[float, float],
    ) -> None:
        self.assertAlmostEqual(actual[0], expected[0], delta=GEOMETRY_ABS_TOL)
        self.assertAlmostEqual(actual[1], expected[1], delta=GEOMETRY_ABS_TOL)

    def assertSemanticStateMatchesFixture(
        self,
        actual: GameState,
        expected: GameState,
    ) -> None:
        self.assertEqual(actual.tick, expected.tick)
        self.assertEqual(actual.player_id, expected.player_id)
        self.assertEqual(actual.next_fleet_id, expected.next_fleet_id)
        self.assertEqual(len(actual.planets), len(expected.planets))
        self.assertEqual(len(actual.fleets), len(expected.fleets))

        for actual_planet, expected_planet in zip(actual.planets, expected.planets):
            self.assertEqual(actual_planet.planet_id, expected_planet.planet_id)
            self.assertEqual(actual_planet.owner, expected_planet.owner)
            self.assertPointAlmostEqual(actual_planet.position, expected_planet.position)
            self.assertEqual(actual_planet.radius, expected_planet.radius)
            self.assertEqual(actual_planet.ships, expected_planet.ships)
            self.assertEqual(actual_planet.production, expected_planet.production)

        for actual_fleet, expected_fleet in zip(actual.fleets, expected.fleets):
            self.assertEqual(actual_fleet.fleet_id, expected_fleet.fleet_id)
            self.assertEqual(actual_fleet.owner, expected_fleet.owner)
            self.assertPointAlmostEqual(actual_fleet.position, expected_fleet.position)
            self.assertEqual(actual_fleet.angle, expected_fleet.angle)
            self.assertEqual(actual_fleet.from_planet_id, expected_fleet.from_planet_id)
            self.assertEqual(actual_fleet.ships, expected_fleet.ships)

    def test_ticks_zero_matches_apply_launch_orders(self) -> None:
        state = GameState(
            player_id=0,
            planets=(planet_at(1, owner=0, ships=5),),
            next_fleet_id=10,
        )
        orders = (LaunchOrder(source_planet_id=1, angle=0.0, ships=2),)

        self.assertEqual(
            simulate_launch_orders(state, orders, ticks=0),
            apply_launch_orders(state, orders),
        )

    def test_ticks_one_matches_launch_then_next_tick(self) -> None:
        state = GameState(
            player_id=0,
            planets=(planet_at(1, owner=0, ships=5),),
            next_fleet_id=10,
        )
        orders = (LaunchOrder(source_planet_id=1, angle=0.0, ships=2),)

        self.assertEqual(
            simulate_launch_orders(state, orders, ticks=1),
            next_game_state_after_tick(apply_launch_orders(state, orders)),
        )

    def test_multiple_ticks_match_launch_then_simulate_ticks(self) -> None:
        state = GameState(
            player_id=0,
            planets=(planet_at(1, owner=0, ships=5),),
            next_fleet_id=10,
        )
        orders = (LaunchOrder(source_planet_id=1, angle=0.0, ships=2),)

        self.assertEqual(
            simulate_launch_orders(state, orders, ticks=3),
            simulate_ticks(apply_launch_orders(state, orders), 3),
        )

    def test_empty_orders_match_explicit_composition(self) -> None:
        state = GameState(
            tick=4,
            player_id=0,
            planets=(planet_at(1, owner=0, ships=5),),
            fleets=(fleet_at(3),),
            next_fleet_id=10,
        )

        self.assertEqual(
            simulate_launch_orders(state, (), ticks=2),
            simulate_ticks(apply_launch_orders(state, ()), 2),
        )

    def test_invalid_tick_values_raise_value_error(self) -> None:
        state = GameState(player_id=0, planets=(planet_at(1, owner=0, ships=5),), next_fleet_id=1)
        orders = (LaunchOrder(source_planet_id=1, angle=0.0, ships=1),)

        for ticks in (-1, True, False, 1.5, "2", None):
            with self.subTest(ticks=ticks):
                with self.assertRaises(ValueError):
                    simulate_launch_orders(state, orders, ticks=ticks)

    def test_invalid_launch_orders_raise_through_underlying_validation(self) -> None:
        state = GameState(player_id=0, planets=(planet_at(1, owner=0, ships=5),), next_fleet_id=1)

        with self.assertRaises(ValueError):
            simulate_launch_orders(
                state,
                (LaunchOrder(source_planet_id=1, angle=0.0, ships=6),),
                ticks=1,
            )

    def test_official_fixture_launch_plus_one_tick_matches_step1(self) -> None:
        step0 = load_state("kaggle_seed7_2p_step0.json")
        expected_step1 = load_state("kaggle_seed7_2p_step1_fleet.json")
        observed_fleet = expected_step1.fleets[0]
        order = LaunchOrder(
            source_planet_id=observed_fleet.from_planet_id,
            angle=observed_fleet.angle,
            ships=observed_fleet.ships,
            player_id=observed_fleet.owner,
        )

        actual_step1 = simulate_launch_orders(step0, (order,), ticks=1)

        self.assertSemanticStateMatchesFixture(actual_step1, expected_step1)

    def test_input_state_planets_fleets_comets_and_raw_are_not_mutated(self) -> None:
        source = planet_at(1, owner=0, ships=5)
        existing_fleet = fleet_at(3)
        comet_group = CometGroup(
            planet_ids=(24,),
            paths=(((0.0, 0.0), (1.0, 0.0)),),
            path_index=0,
        )
        state = GameState(
            tick=0,
            player_id=0,
            planets=(source,),
            fleets=(existing_fleet,),
            next_fleet_id=10,
            comet_planet_ids=frozenset({24}),
            comets=(comet_group,),
            raw_observation={"planets": [list(source.raw)]},
        )
        planets_before = state.planets
        fleets_before = state.fleets
        comets_before = state.comets
        raw_before = copy.deepcopy(state.raw_observation)

        simulate_launch_orders(
            state,
            (LaunchOrder(source_planet_id=1, angle=0.0, ships=1),),
            ticks=2,
        )

        self.assertEqual(state.planets, planets_before)
        self.assertEqual(state.fleets, fleets_before)
        self.assertEqual(state.comets, comets_before)
        self.assertEqual(state.raw_observation, raw_before)


if __name__ == "__main__":
    unittest.main()
