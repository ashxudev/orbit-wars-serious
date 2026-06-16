"""Tests for Cycle 11 one-tick next-state construction."""

from __future__ import annotations

import copy
import json
import math
import unittest
from pathlib import Path

from ow_sim.combat import PlanetCombatResult
from ow_sim.constants import GEOMETRY_ABS_TOL
from ow_sim.forecast import fleet_path_for_tick, planet_path_for_tick
from ow_sim.state import CometGroup, Fleet, GameState, Planet
from ow_sim.timeline import (
    advance_comet_groups,
    apply_planet_combat_result,
    apply_planet_position,
    next_game_state_after_tick,
    produce_planet,
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


class TimelineNextStateTests(unittest.TestCase):
    def assertPointAlmostEqual(
        self,
        actual: tuple[float, float],
        expected: tuple[float, float],
    ) -> None:
        self.assertAlmostEqual(actual[0], expected[0], delta=GEOMETRY_ABS_TOL)
        self.assertAlmostEqual(actual[1], expected[1], delta=GEOMETRY_ABS_TOL)

    def test_empty_state_returns_new_game_state_without_mutating_input(self) -> None:
        state = GameState(
            tick=None,
            player_id=1,
            angular_velocity=0.03,
            next_fleet_id=7,
            remaining_overage_time=12.5,
            raw_observation={"planets": [], "fleets": []},
        )
        raw_before = copy.deepcopy(state.raw_observation)

        next_state = next_game_state_after_tick(state)

        self.assertIsNot(next_state, state)
        self.assertIsNone(next_state.tick)
        self.assertEqual(next_state.player_id, state.player_id)
        self.assertEqual(next_state.angular_velocity, state.angular_velocity)
        self.assertEqual(next_state.next_fleet_id, state.next_fleet_id)
        self.assertEqual(next_state.remaining_overage_time, state.remaining_overage_time)
        self.assertEqual(next_state.planets, ())
        self.assertEqual(next_state.fleets, ())
        self.assertIsNone(next_state.raw_observation)
        self.assertEqual(state.raw_observation, raw_before)

    def test_tick_increments_when_known(self) -> None:
        state = GameState(tick=4)

        self.assertEqual(next_game_state_after_tick(state).tick, 5)

    def test_owned_planet_production_is_applied(self) -> None:
        planet = planet_at(1, 0.5, 0.0, owner=0, ships=5, production=2)
        state = GameState(tick=0, planets=(planet,))

        next_planet = next_game_state_after_tick(state).planets[0]

        self.assertEqual(next_planet.ships, 7)
        self.assertEqual(next_planet.raw, (1, 0, 0.5, 0.0, 0.2, 7, 2))

    def test_neutral_planet_production_is_not_applied(self) -> None:
        planet = planet_at(1, 0.5, 0.0, owner=-1, ships=5, production=2)
        state = GameState(tick=0, planets=(planet,))

        next_planet = next_game_state_after_tick(state).planets[0]

        self.assertEqual(next_planet.ships, 5)

    def test_static_planet_position_is_preserved(self) -> None:
        planet = planet_at(1, 0.5, 0.0)
        state = GameState(tick=0, planets=(planet,))

        next_planet = next_game_state_after_tick(state).planets[0]

        self.assertEqual(next_planet.position, planet.position)

    def test_orbiting_planet_position_is_advanced(self) -> None:
        initial = planet_at(30, 60.0, 50.0, radius=0.5)
        current = planet_at(30, 60.0, 50.0, radius=0.5)
        state = GameState(
            tick=1,
            planets=(current,),
            initial_planets=(initial,),
            angular_velocity=math.pi / 2.0,
        )

        next_planet = next_game_state_after_tick(state).planets[0]
        _, expected_position = planet_path_for_tick(state, current.planet_id)

        self.assertPointAlmostEqual(next_planet.position, expected_position)

    def test_active_fleet_is_moved_and_retained(self) -> None:
        fleet = fleet_at(10, 0.0, 0.0)
        state = GameState(tick=0, fleets=(fleet,))

        next_state = next_game_state_after_tick(state)

        self.assertEqual(len(next_state.fleets), 1)
        self.assertIsNot(next_state.fleets[0], fleet)
        self.assertPointAlmostEqual(next_state.fleets[0].position, fleet_path_for_tick(fleet)[1])
        self.assertEqual(
            next_state.fleets[0].raw,
            (
                fleet.fleet_id,
                fleet.owner,
                next_state.fleets[0].x,
                next_state.fleets[0].y,
                fleet.angle,
                fleet.from_planet_id,
                fleet.ships,
            ),
        )

    def test_planet_hit_fleet_is_removed(self) -> None:
        target = planet_at(1, 0.5, 0.0, owner=-1, ships=0)
        fleet = fleet_at(10, 0.0, 0.0)
        state = GameState(tick=0, planets=(target,), fleets=(fleet,))

        self.assertEqual(next_game_state_after_tick(state).fleets, ())

    def test_bounds_removed_fleet_is_removed(self) -> None:
        state = GameState(tick=0, fleets=(fleet_at(20, 99.5, 0.0),))

        self.assertEqual(next_game_state_after_tick(state).fleets, ())

    def test_sun_removed_fleet_is_removed(self) -> None:
        state = GameState(tick=0, fleets=(fleet_at(30, 49.0, 50.0),))

        self.assertEqual(next_game_state_after_tick(state).fleets, ())

    def test_combat_capture_changes_returned_planet_owner_and_ships(self) -> None:
        target = planet_at(1, 0.5, 0.0, owner=-1, ships=0)
        fleet = fleet_at(10, 0.0, 0.0, owner=0, ships=1)
        state = GameState(tick=0, planets=(target,), fleets=(fleet,))

        next_planet = next_game_state_after_tick(state).planets[0]

        self.assertEqual(next_planet.owner, 0)
        self.assertEqual(next_planet.ships, 1)

    def test_same_owner_arrival_reinforces_after_production(self) -> None:
        target = planet_at(1, 0.5, 0.0, owner=0, ships=5, production=2)
        fleet = fleet_at(10, 0.0, 0.0, owner=0, ships=3)
        state = GameState(tick=0, planets=(target,), fleets=(fleet,))

        next_planet = next_game_state_after_tick(state).planets[0]

        self.assertEqual(next_planet.owner, 0)
        self.assertEqual(next_planet.ships, 10)

    def test_exact_zero_combat_preserves_owner_after_production(self) -> None:
        target = planet_at(1, 0.5, 0.0, owner=1, ships=1, production=1)
        fleet = fleet_at(10, 0.0, 0.0, owner=0, ships=2)
        state = GameState(tick=0, planets=(target,), fleets=(fleet,))

        next_planet = next_game_state_after_tick(state).planets[0]

        self.assertEqual(next_planet.owner, 1)
        self.assertEqual(next_planet.ships, 0)

    def test_tied_attackers_leave_produced_planet_unchanged(self) -> None:
        target = planet_at(1, 0.5, 0.0, owner=2, ships=4, production=1)
        first = fleet_at(10, 0.0, 0.0, owner=0, ships=3)
        second = fleet_at(11, 1.0, 0.0, owner=1, angle=math.pi, ships=3)
        state = GameState(tick=0, planets=(target,), fleets=(first, second))

        next_planet = next_game_state_after_tick(state).planets[0]

        self.assertEqual(next_planet.owner, 2)
        self.assertEqual(next_planet.ships, 5)

    def test_expired_comet_is_removed_from_planets_and_metadata_before_combat(self) -> None:
        comet = planet_at(24, 1.0, 0.0, radius=0.2, is_comet=True)
        fleet = fleet_at(10, 1.0, 0.0, owner=0)
        state = GameState(
            tick=50,
            planets=(comet,),
            fleets=(fleet,),
            initial_planets=(comet,),
            comet_planet_ids=frozenset({24}),
            comets=(
                CometGroup(
                    planet_ids=(24,),
                    paths=(((0.0, 0.0), (1.0, 0.0)),),
                    path_index=1,
                ),
            ),
        )

        next_state = next_game_state_after_tick(state)

        self.assertEqual(next_state.planets, ())
        self.assertEqual(next_state.initial_planets, ())
        self.assertEqual(next_state.comet_planet_ids, frozenset())
        self.assertEqual(next_state.comets, ())
        self.assertEqual(next_state.fleets, ())

    def test_first_placement_comet_advances_metadata_and_remains_present(self) -> None:
        comet = planet_at(24, -99.0, -99.0, radius=0.2, is_comet=True)
        group = CometGroup(
            planet_ids=(24,),
            paths=(((0.0, 0.0), (1.0, 0.0)),),
            path_index=-1,
        )
        state = GameState(
            tick=49,
            planets=(comet,),
            initial_planets=(comet,),
            comet_planet_ids=frozenset({24}),
            comets=(group,),
        )

        next_state = next_game_state_after_tick(state)

        self.assertEqual(tuple(planet.planet_id for planet in next_state.planets), (24,))
        self.assertPointAlmostEqual(next_state.planets[0].position, (0.0, 0.0))
        self.assertEqual(next_state.comet_planet_ids, frozenset({24}))
        self.assertEqual(next_state.comets[0].path_index, 0)
        self.assertEqual(next_state.comets[0].planet_ids, (24,))

    def test_changed_planets_are_new_instances(self) -> None:
        planet = planet_at(1, 0.5, 0.0, owner=0, ships=5, production=2)
        state = GameState(tick=0, planets=(planet,))

        next_planet = next_game_state_after_tick(state).planets[0]

        self.assertIsNot(next_planet, planet)
        self.assertEqual(next_planet.ships, 7)

    def test_input_state_and_fixture_data_are_not_mutated(self) -> None:
        state = load_state("kaggle_seed7_2p_step1_fleet.json")
        planets_before = state.planets
        fleets_before = state.fleets
        comets_before = state.comets
        raw_before = copy.deepcopy(state.raw_observation)

        next_game_state_after_tick(state)

        self.assertEqual(state.planets, planets_before)
        self.assertEqual(state.fleets, fleets_before)
        self.assertEqual(state.comets, comets_before)
        self.assertEqual(state.raw_observation, raw_before)

    def test_official_step1_to_step2_idle_fixture_matches_next_state(self) -> None:
        state = load_state("kaggle_seed7_2p_step1_fleet.json")
        expected = load_state("kaggle_seed7_2p_step2_fleet.json")

        actual = next_game_state_after_tick(state)

        self.assertEqual(actual.tick, expected.tick)
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

    def test_unsupported_dt_values_raise_value_error(self) -> None:
        state = GameState(tick=0)

        with self.assertRaises(ValueError):
            next_game_state_after_tick(state, dt=0)
        with self.assertRaises(ValueError):
            next_game_state_after_tick(state, dt=2)

    def test_public_planet_mutation_helpers_preserve_row_shape(self) -> None:
        planet = planet_at(1, 0.5, 0.0, owner=0, ships=5, production=2)

        produced = produce_planet(planet)
        moved = apply_planet_position(produced, (1.5, 2.5))
        resolved = apply_planet_combat_result(
            moved,
            PlanetCombatResult(owner=1, ships=3),
        )

        self.assertEqual(produced.raw, (1, 0, 0.5, 0.0, 0.2, 7, 2))
        self.assertEqual(moved.raw, (1, 0, 1.5, 2.5, 0.2, 7, 2))
        self.assertEqual(resolved.raw, (1, 1, 1.5, 2.5, 0.2, 3, 2))

    def test_advance_comet_groups_increments_and_filters_expired_ids(self) -> None:
        state = GameState(
            tick=50,
            comets=(
                CometGroup(
                    planet_ids=(24, 25),
                    paths=(
                        ((0.0, 0.0), (1.0, 0.0)),
                        ((0.0, 1.0), (1.0, 1.0)),
                    ),
                    path_index=0,
                ),
            ),
        )

        (group,) = advance_comet_groups(state, frozenset({24}))

        self.assertEqual(group.path_index, 1)
        self.assertEqual(group.planet_ids, (25,))
        self.assertEqual(group.paths, (((0.0, 1.0), (1.0, 1.0)),))


if __name__ == "__main__":
    unittest.main()
