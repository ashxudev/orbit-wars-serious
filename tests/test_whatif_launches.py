"""Tests for Cycle 13 hypothetical launch insertion."""

from __future__ import annotations

import copy
import json
import math
import unittest
from pathlib import Path

from ow_sim.constants import GEOMETRY_ABS_TOL
from ow_sim.state import CometGroup, Fleet, GameState, Planet
from ow_sim.timeline import next_game_state_after_tick
from ow_sim.whatif import LaunchOrder, apply_launch_orders


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


def planet_by_id(state: GameState, planet_id: int) -> Planet:
    for planet in state.planets:
        if planet.planet_id == planet_id:
            return planet
    raise AssertionError(f"missing planet {planet_id}")


class WhatIfLaunchTests(unittest.TestCase):
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

    def test_single_valid_launch_deducts_source_appends_fleet_and_increments_id(self) -> None:
        source = planet_at(1, owner=0, ships=10)
        other = planet_at(2, owner=1, ships=7, x=30.0, y=40.0)
        existing_fleet = fleet_at(4)
        state = GameState(
            tick=8,
            player_id=0,
            planets=(source, other),
            fleets=(existing_fleet,),
            next_fleet_id=5,
        )

        result = apply_launch_orders(
            state,
            (LaunchOrder(source_planet_id=1, angle=0.0, ships=3),),
        )

        self.assertIsNot(result, state)
        self.assertEqual(result.tick, state.tick)
        self.assertEqual(result.next_fleet_id, 6)
        self.assertEqual(result.planets[0].ships, 7)
        self.assertEqual(result.planets[1], other)
        self.assertEqual(result.fleets[0], existing_fleet)
        self.assertEqual(result.fleets[1].fleet_id, 5)
        self.assertEqual(result.fleets[1].owner, 0)
        self.assertEqual(result.fleets[1].from_planet_id, 1)
        self.assertEqual(result.fleets[1].ships, 3)
        self.assertPointAlmostEqual(result.fleets[1].position, (12.1, 20.0))
        self.assertIsNone(result.raw_observation)

    def test_multiple_launches_same_source_apply_sequentially(self) -> None:
        source = planet_at(1, owner=0, ships=5)
        state = GameState(player_id=0, planets=(source,), next_fleet_id=10)

        result = apply_launch_orders(
            state,
            (
                LaunchOrder(source_planet_id=1, angle=0.0, ships=3),
                LaunchOrder(source_planet_id=1, angle=math.pi, ships=2),
            ),
        )

        self.assertEqual(result.planets[0].ships, 0)
        self.assertEqual(tuple(fleet.fleet_id for fleet in result.fleets), (10, 11))
        self.assertEqual(tuple(fleet.ships for fleet in result.fleets), (3, 2))

    def test_multiple_launches_same_source_fail_when_cumulative_ships_exceed_available(self) -> None:
        source = planet_at(1, owner=0, ships=5)
        state = GameState(player_id=0, planets=(source,), next_fleet_id=10)

        with self.assertRaises(ValueError):
            apply_launch_orders(
                state,
                (
                    LaunchOrder(source_planet_id=1, angle=0.0, ships=3),
                    LaunchOrder(source_planet_id=1, angle=0.0, ships=3),
                ),
            )
        self.assertEqual(state.planets[0].ships, 5)
        self.assertEqual(state.fleets, ())

    def test_multiple_launches_different_sources_preserve_order_and_ids(self) -> None:
        first = planet_at(1, owner=0, ships=5)
        second = planet_at(2, owner=1, ships=6, x=30.0, y=40.0)
        state = GameState(planets=(first, second), next_fleet_id=20)

        result = apply_launch_orders(
            state,
            (
                LaunchOrder(source_planet_id=2, angle=0.0, ships=2, player_id=1),
                LaunchOrder(source_planet_id=1, angle=0.0, ships=3, player_id=0),
            ),
        )

        self.assertEqual(tuple(fleet.fleet_id for fleet in result.fleets), (20, 21))
        self.assertEqual(tuple(fleet.from_planet_id for fleet in result.fleets), (2, 1))
        self.assertEqual(tuple(planet.ships for planet in result.planets), (2, 4))

    def test_invalid_launch_inputs_raise_value_error(self) -> None:
        source = planet_at(1, owner=0, ships=5)
        state = GameState(player_id=0, planets=(source,), next_fleet_id=1)

        cases = (
            LaunchOrder(source_planet_id=99, angle=0.0, ships=1),
            LaunchOrder(source_planet_id=1, angle=0.0, ships=1, player_id=1),
            LaunchOrder(source_planet_id=1, angle=0.0, ships=6),
            LaunchOrder(source_planet_id=1, angle=0.0, ships=0),
            LaunchOrder(source_planet_id=1, angle=0.0, ships=-1),
            LaunchOrder(source_planet_id=1, angle=0.0, ships=True),
            LaunchOrder(source_planet_id=1, angle=0.0, ships=1.5),
        )

        for order in cases:
            with self.subTest(order=order):
                with self.assertRaises(ValueError):
                    apply_launch_orders(state, (order,))

    def test_missing_player_id_raises_when_order_default_and_state_do_not_supply_one(self) -> None:
        source = planet_at(1, owner=0, ships=5)
        state = GameState(planets=(source,), next_fleet_id=1)

        with self.assertRaises(ValueError):
            apply_launch_orders(
                state,
                (LaunchOrder(source_planet_id=1, angle=0.0, ships=1),),
            )

    def test_missing_next_fleet_id_raises_for_non_empty_orders(self) -> None:
        source = planet_at(1, owner=0, ships=5)
        state = GameState(player_id=0, planets=(source,), next_fleet_id=None)

        with self.assertRaises(ValueError):
            apply_launch_orders(
                state,
                (LaunchOrder(source_planet_id=1, angle=0.0, ships=1),),
            )

    def test_empty_launch_orders_return_input_state_without_mutation(self) -> None:
        state = load_state("kaggle_seed7_2p_step0.json")
        raw_before = copy.deepcopy(state.raw_observation)

        result = apply_launch_orders(state, ())

        self.assertIs(result, state)
        self.assertEqual(state.raw_observation, raw_before)

    def test_input_state_planets_fleets_comets_and_raw_are_not_mutated(self) -> None:
        source = planet_at(1, owner=0, ships=5)
        existing_fleet = fleet_at(4)
        comet_group = CometGroup(
            planet_ids=(24,),
            paths=(((0.0, 0.0), (1.0, 0.0)),),
            path_index=0,
        )
        state = GameState(
            player_id=0,
            planets=(source,),
            fleets=(existing_fleet,),
            next_fleet_id=5,
            comet_planet_ids=frozenset({24}),
            comets=(comet_group,),
            raw_observation={"planets": [list(source.raw)]},
        )
        planets_before = state.planets
        fleets_before = state.fleets
        comets_before = state.comets
        raw_before = copy.deepcopy(state.raw_observation)

        apply_launch_orders(
            state,
            (LaunchOrder(source_planet_id=1, angle=0.0, ships=1),),
        )

        self.assertEqual(state.planets, planets_before)
        self.assertEqual(state.fleets, fleets_before)
        self.assertEqual(state.comets, comets_before)
        self.assertEqual(state.raw_observation, raw_before)

    def test_fixture_launch_plus_one_tick_matches_official_step1(self) -> None:
        step0 = load_state("kaggle_seed7_2p_step0.json")
        expected_step1 = load_state("kaggle_seed7_2p_step1_fleet.json")
        observed_fleet = expected_step1.fleets[0]

        with_launch = apply_launch_orders(
            step0,
            (
                LaunchOrder(
                    source_planet_id=observed_fleet.from_planet_id,
                    angle=observed_fleet.angle,
                    ships=observed_fleet.ships,
                    player_id=observed_fleet.owner,
                ),
            ),
        )
        actual_step1 = next_game_state_after_tick(with_launch)

        self.assertSemanticStateMatchesFixture(actual_step1, expected_step1)
        source_after_launch = planet_by_id(with_launch, observed_fleet.from_planet_id)
        source_before = planet_by_id(step0, observed_fleet.from_planet_id)
        self.assertEqual(source_after_launch.ships, source_before.ships - observed_fleet.ships)
        self.assertEqual(with_launch.next_fleet_id, step0.next_fleet_id + 1)


if __name__ == "__main__":
    unittest.main()
