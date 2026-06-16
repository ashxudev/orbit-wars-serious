"""Tests for Mission Generation Cycle 1 planner action conversion."""

from __future__ import annotations

import copy
import math
import unittest

from ow_planner import (
    LaunchCandidate,
    MissionCandidate,
    MissionType,
    generate_candidates,
    launch_candidate_to_action,
    launch_candidate_to_order,
    mission_candidate_to_actions,
    mission_candidate_to_orders,
)
from ow_sim.state import CometGroup, Fleet, GameState, Planet
from ow_sim.whatif import LaunchOrder


def planet(
    planet_id: int,
    owner: int,
    ships: int,
    *,
    x: float = 10.0,
    y: float = 20.0,
) -> Planet:
    return Planet(
        planet_id=planet_id,
        owner=owner,
        x=x,
        y=y,
        radius=2.0,
        ships=ships,
        production=1,
        raw=(planet_id, owner, x, y, 2.0, ships, 1),
    )


def fleet() -> Fleet:
    return Fleet(
        fleet_id=10,
        owner=0,
        x=13.0,
        y=20.0,
        angle=0.0,
        from_planet_id=1,
        ships=2,
        raw=(10, 0, 13.0, 20.0, 0.0, 1, 2),
    )


def state_with_planets(*planets: Planet, player_id: int | None = 0) -> GameState:
    comet = CometGroup(
        planet_ids=(99,),
        paths=(((1.0, 1.0), (2.0, 2.0)),),
        path_index=0,
        raw={
            "planet_ids": [99],
            "paths": [[[1.0, 1.0], [2.0, 2.0]]],
            "path_index": 0,
        },
    )
    return GameState(
        tick=5,
        player_id=player_id,
        planets=tuple(planets),
        fleets=(fleet(),),
        angular_velocity=0.01,
        initial_planets=tuple(planets),
        next_fleet_id=11,
        comet_planet_ids=frozenset({99}),
        comets=(comet,),
        remaining_overage_time=60.0,
        raw_observation={
            "step": 5,
            "player": player_id,
            "planets": [list(row.raw) for row in planets],
            "fleets": [list(fleet().raw)],
            "comets": [copy.deepcopy(comet.raw)],
        },
    )


class PlannerActionConversionTests(unittest.TestCase):
    def test_valid_single_launch_converts_to_launch_order(self) -> None:
        state = state_with_planets(planet(1, owner=0, ships=8))
        launch = LaunchCandidate(source_planet_id=1, angle=0.25, ships=3)

        order = launch_candidate_to_order(state, launch)

        self.assertEqual(order, LaunchOrder(1, 0.25, 3, 0))

    def test_valid_single_launch_converts_to_kaggle_action_row(self) -> None:
        state = state_with_planets(planet(1, owner=0, ships=8))
        launch = LaunchCandidate(source_planet_id=1, angle=0.25, ships=3)

        action = launch_candidate_to_action(state, launch)

        self.assertEqual(action, [1, 0.25, 3])

    def test_valid_mission_with_multiple_launches_preserves_order(self) -> None:
        state = state_with_planets(
            planet(1, owner=0, ships=8),
            planet(2, owner=0, ships=7, x=15.0),
        )
        mission = MissionCandidate(
            mission_type=MissionType.REINFORCE,
            launches=(
                LaunchCandidate(source_planet_id=2, angle=0.5, ships=2),
                LaunchCandidate(source_planet_id=1, angle=0.25, ships=3),
            ),
        )

        orders = mission_candidate_to_orders(state, mission)
        actions = mission_candidate_to_actions(state, mission)

        self.assertEqual(
            orders,
            (
                LaunchOrder(2, 0.5, 2, 0),
                LaunchOrder(1, 0.25, 3, 0),
            ),
        )
        self.assertEqual(actions, [[2, 0.5, 2], [1, 0.25, 3]])

    def test_effective_player_id_falls_back_in_documented_order(self) -> None:
        state_from_state_player = state_with_planets(planet(1, owner=0, ships=8))
        state_without_player = state_with_planets(planet(1, owner=0, ships=8), player_id=None)
        state_with_explicit_override = state_with_planets(planet(1, owner=0, ships=8), player_id=1)

        self.assertEqual(
            launch_candidate_to_order(
                state_from_state_player,
                LaunchCandidate(source_planet_id=1, angle=0.0, ships=1),
            ).player_id,
            0,
        )
        self.assertEqual(
            launch_candidate_to_order(
                state_without_player,
                LaunchCandidate(source_planet_id=1, angle=0.0, ships=1),
                player_id=0,
            ).player_id,
            0,
        )
        self.assertEqual(
            launch_candidate_to_order(
                state_with_explicit_override,
                LaunchCandidate(source_planet_id=1, angle=0.0, ships=1, player_id=0),
                player_id=1,
            ).player_id,
            0,
        )

    def test_missing_player_id_rejects(self) -> None:
        state = state_with_planets(planet(1, owner=0, ships=8), player_id=None)

        with self.assertRaises(ValueError):
            launch_candidate_to_order(
                state,
                LaunchCandidate(source_planet_id=1, angle=0.0, ships=1),
            )

    def test_source_ownership_mismatch_rejects(self) -> None:
        state = state_with_planets(planet(1, owner=1, ships=8), player_id=0)

        with self.assertRaises(ValueError):
            launch_candidate_to_order(
                state,
                LaunchCandidate(source_planet_id=1, angle=0.0, ships=1),
            )

    def test_missing_source_rejects(self) -> None:
        state = state_with_planets(planet(1, owner=0, ships=8))

        with self.assertRaises(ValueError):
            launch_candidate_to_order(
                state,
                LaunchCandidate(source_planet_id=2, angle=0.0, ships=1),
            )

    def test_insufficient_ships_rejects(self) -> None:
        state = state_with_planets(planet(1, owner=0, ships=2))

        with self.assertRaises(ValueError):
            launch_candidate_to_order(
                state,
                LaunchCandidate(source_planet_id=1, angle=0.0, ships=3),
            )

    def test_cumulative_same_source_overspend_rejects(self) -> None:
        state = state_with_planets(planet(1, owner=0, ships=5))
        mission = MissionCandidate(
            mission_type=MissionType.ATTACK_ENEMY,
            launches=(
                LaunchCandidate(source_planet_id=1, angle=0.0, ships=3),
                LaunchCandidate(source_planet_id=1, angle=0.1, ships=3),
            ),
        )

        with self.assertRaises(ValueError):
            mission_candidate_to_orders(state, mission)

    def test_zero_negative_bool_and_non_int_ships_reject(self) -> None:
        state = state_with_planets(planet(1, owner=0, ships=8))

        for ships in (0, -1, True, 1.5, "3"):
            with self.subTest(ships=ships):
                with self.assertRaises(ValueError):
                    launch_candidate_to_order(
                        state,
                        LaunchCandidate(source_planet_id=1, angle=0.0, ships=ships),
                    )

    def test_non_finite_non_real_and_bool_angles_reject(self) -> None:
        state = state_with_planets(planet(1, owner=0, ships=8))

        for angle in (math.inf, -math.inf, math.nan, True, "0"):
            with self.subTest(angle=angle):
                with self.assertRaises(ValueError):
                    launch_candidate_to_order(
                        state,
                        LaunchCandidate(source_planet_id=1, angle=angle, ships=1),
                    )

    def test_bool_and_non_int_source_planet_ids_reject(self) -> None:
        state = state_with_planets(planet(1, owner=0, ships=8))

        for source_planet_id in (True, 1.0, "1"):
            with self.subTest(source_planet_id=source_planet_id):
                with self.assertRaises(ValueError):
                    launch_candidate_to_order(
                        state,
                        LaunchCandidate(
                            source_planet_id=source_planet_id,
                            angle=0.0,
                            ships=1,
                        ),
                    )

    def test_empty_mission_converts_to_empty_outputs(self) -> None:
        state = state_with_planets(planet(1, owner=0, ships=8))
        mission = MissionCandidate(mission_type=MissionType.DEFEND_OWN)

        self.assertEqual(mission_candidate_to_orders(state, mission), ())
        self.assertEqual(mission_candidate_to_actions(state, mission), [])

    def test_conversion_does_not_mutate_simulator_state_or_candidates(self) -> None:
        state = state_with_planets(
            planet(1, owner=0, ships=8),
            planet(2, owner=0, ships=7, x=15.0),
        )
        mission = MissionCandidate(
            mission_type=MissionType.REINFORCE,
            launches=(
                LaunchCandidate(source_planet_id=1, angle=0.25, ships=3),
                LaunchCandidate(source_planet_id=2, angle=0.5, ships=2),
            ),
        )
        state_before = copy.deepcopy(state)
        mission_before = copy.deepcopy(mission)

        mission_candidate_to_actions(state, mission)

        self.assertEqual(state, state_before)
        self.assertEqual(state.planets, state_before.planets)
        self.assertEqual(state.fleets, state_before.fleets)
        self.assertEqual(state.comets, state_before.comets)
        self.assertEqual(state.raw_observation, state_before.raw_observation)
        self.assertEqual(mission, mission_before)

    def test_generate_candidates_placeholder_remains_deterministic_and_empty(self) -> None:
        state = state_with_planets(planet(1, owner=0, ships=8))

        self.assertEqual(generate_candidates(state), ())
        self.assertEqual(generate_candidates(state), generate_candidates(state))


if __name__ == "__main__":
    unittest.main()
