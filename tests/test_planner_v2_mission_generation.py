"""Tests for Planner V2 mission generation."""

from __future__ import annotations

import unittest

from ow_planner import CandidateOutcome, LaunchCandidate, MissionCandidate, MissionType
from ow_planner_v2 import MissionFamily, PlannerV2Config, diagnose_board, generate_mission_plans
from ow_sim.state import Fleet, GameState, Planet


def state() -> GameState:
    return GameState(
        tick=12,
        player_id=0,
        planets=(
            Planet(1, 0, 0.0, 0.0, 1.0, 20, 2),
            Planet(2, -1, 5.0, 0.0, 1.0, 0, 3),
            Planet(3, 1, 20.0, 0.0, 1.0, 30, 4),
        ),
    )


def candidate(mission_type: MissionType, target: int) -> MissionCandidate:
    launch = LaunchCandidate(source_planet_id=1, angle=0.0, ships=5, player_id=0)
    return MissionCandidate(
        mission_type=mission_type,
        target_planet_id=target,
        source_planet_ids=(1,),
        launches=(launch,),
        outcome=CandidateOutcome.VALIDATED,
    )


class PlannerV2MissionGenerationTests(unittest.TestCase):
    def test_generates_bounded_missions_from_candidates(self) -> None:
        diagnosis = diagnose_board(state())
        candidates = (
            candidate(MissionType.CAPTURE_NEUTRAL, 2),
            candidate(MissionType.ATTACK_ENEMY, 3),
        )

        missions = generate_mission_plans(
            diagnosis,
            candidates,
            config=PlannerV2Config(max_missions=1),
        )

        self.assertEqual(len(missions), 1)
        self.assertEqual(missions[0].candidate, candidates[0])
        self.assertIn(missions[0].family, {MissionFamily.SAFE_EXPAND, MissionFamily.HOLD_CAPTURE})
        self.assertGreater(missions[0].priority, 0.0)

    def test_empty_candidates_can_emit_diagnostic_mission_under_pressure(self) -> None:
        threatened = GameState(
            tick=20,
            player_id=0,
            planets=(
                Planet(1, 0, 0.0, 0.0, 1.0, 2, 3),
                Planet(2, 1, 20.0, 0.0, 1.0, 30, 3),
            ),
            fleets=(Fleet(10, 1, -5.0, 0.0, 0.0, 2, 10),),
        )

        missions = generate_mission_plans(diagnose_board(threatened), ())

        self.assertEqual(len(missions), 1)
        self.assertEqual(missions[0].family, MissionFamily.URGENT_DEFEND)
        self.assertIn("diagnostic_only", missions[0].labels)


if __name__ == "__main__":
    unittest.main()
