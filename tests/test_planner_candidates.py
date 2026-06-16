"""Tests for Mission Generation Cycle 0 planner candidate primitives."""

from __future__ import annotations

import copy
import importlib
import unittest
from dataclasses import FrozenInstanceError

from ow_planner import (
    CandidateGenerationConfig,
    CandidateOutcome,
    LaunchCandidate,
    MissionCandidate,
    MissionType,
    generate_candidates,
)
from ow_sim.state import Fleet, GameState, Planet


def state_with_objects() -> GameState:
    planet = Planet(
        planet_id=1,
        owner=0,
        x=10.0,
        y=20.0,
        radius=2.0,
        ships=12,
        production=1,
        raw=(1, 0, 10.0, 20.0, 2.0, 12, 1),
    )
    fleet = Fleet(
        fleet_id=2,
        owner=0,
        x=12.0,
        y=20.0,
        angle=0.0,
        from_planet_id=1,
        ships=3,
        raw=(2, 0, 12.0, 20.0, 0.0, 1, 3),
    )
    return GameState(
        tick=5,
        player_id=0,
        planets=(planet,),
        fleets=(fleet,),
        raw_observation={
            "step": 5,
            "planets": [list(planet.raw)],
            "fleets": [list(fleet.raw)],
        },
    )


class PlannerCandidateTests(unittest.TestCase):
    def test_planner_modules_import_cleanly(self) -> None:
        for module_name in ("ow_planner", "ow_planner.candidates"):
            with self.subTest(module=module_name):
                importlib.import_module(module_name)

    def test_candidate_enums_have_stable_string_values(self) -> None:
        self.assertEqual(MissionType.CAPTURE_NEUTRAL.value, "capture_neutral")
        self.assertEqual(MissionType.ATTACK_ENEMY.value, "attack_enemy")
        self.assertEqual(CandidateOutcome.UNTESTED.value, "untested")
        self.assertEqual(CandidateOutcome.REJECTED.value, "rejected")

    def test_candidate_types_are_constructible_and_frozen(self) -> None:
        launch = LaunchCandidate(
            source_planet_id=1,
            angle=0.25,
            ships=3,
            player_id=0,
        )
        mission = MissionCandidate(
            mission_type=MissionType.CAPTURE_NEUTRAL,
            target_planet_id=2,
            source_planet_ids=(1,),
            launches=(launch,),
            outcome=CandidateOutcome.UNTESTED,
            note="placeholder",
        )

        self.assertEqual(mission.launches, (launch,))
        self.assertEqual(mission.source_planet_ids, (1,))
        self.assertEqual(mission.target_planet_id, 2)
        with self.assertRaises(FrozenInstanceError):
            launch.ships = 4
        with self.assertRaises(FrozenInstanceError):
            mission.note = None

    def test_config_type_is_constructible_and_frozen(self) -> None:
        config = CandidateGenerationConfig(max_candidates=10)

        self.assertEqual(config.max_candidates, 10)
        with self.assertRaises(FrozenInstanceError):
            config.max_candidates = 5

    def test_generate_candidates_returns_empty_immutable_tuple(self) -> None:
        state = state_with_objects()

        candidates = generate_candidates(state)

        self.assertEqual(candidates, ())
        self.assertIsInstance(candidates, tuple)

    def test_generate_candidates_is_deterministic_with_or_without_config(self) -> None:
        state = state_with_objects()
        config = CandidateGenerationConfig(max_candidates=4)

        self.assertEqual(generate_candidates(state), generate_candidates(state))
        self.assertEqual(generate_candidates(state, config), ())

    def test_generate_candidates_does_not_mutate_simulator_state(self) -> None:
        state = state_with_objects()
        planets_before = state.planets
        fleets_before = state.fleets
        raw_before = copy.deepcopy(state.raw_observation)

        generate_candidates(state, CandidateGenerationConfig(max_candidates=3))

        self.assertEqual(state.planets, planets_before)
        self.assertEqual(state.fleets, fleets_before)
        self.assertEqual(state.raw_observation, raw_before)


if __name__ == "__main__":
    unittest.main()
