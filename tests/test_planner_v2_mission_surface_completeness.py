"""Tests for Planner V2 mission-surface completeness."""

from __future__ import annotations

import unittest

from agents.runtime_planner import (
    PLANNER_VERSION_V2,
    RuntimePlannerConfig,
    run_planner_pipeline,
)
from ow_planner import MissionType
from ow_planner_v2 import (
    MissionFamily,
    PlannerV2Config,
    diagnose_board,
    generate_surface_candidates,
    generate_mission_plans,
)
from ow_sim.state import Fleet, GameState, Planet


def two_player_pressure_state() -> GameState:
    return GameState(
        tick=60,
        player_id=0,
        planets=(
            Planet(1, 0, 0.0, 0.0, 1.0, 18, 4),
            Planet(2, 0, 10.0, 0.0, 1.0, 4, 3),
            Planet(3, 1, 30.0, 0.0, 1.0, 20, 5),
            Planet(4, -1, 6.0, 15.0, 1.0, 5, 4),
        ),
        fleets=(Fleet(10, 1, 4.0, 0.0, 0.0, 99, 9),),
    )


def four_player_rank_state() -> GameState:
    return GameState(
        tick=150,
        player_id=3,
        planets=(
            Planet(1, 3, 0.0, 0.0, 1.0, 20, 2),
            Planet(2, 0, 20.0, 0.0, 1.0, 14, 5),
            Planet(3, 1, 0.0, 20.0, 1.0, 8, 3),
            Planet(4, 2, 20.0, 20.0, 1.0, 8, 3),
            Planet(5, -1, 8.0, 0.0, 1.0, 3, 3),
        ),
    )


class PlannerV2MissionSurfaceCompletenessTests(unittest.TestCase):
    def test_surface_candidates_include_urgent_defense_under_pressure(self) -> None:
        state = two_player_pressure_state()
        diagnosis = diagnose_board(state)

        candidates = generate_surface_candidates(state, (), diagnosis=diagnosis)

        self.assertTrue(candidates)
        self.assertIn(MissionType.REINFORCE, {candidate.mission_type for candidate in candidates})
        self.assertTrue(
            any("urgent_defense" in (candidate.note or "") for candidate in candidates)
        )

    def test_surface_candidates_include_enemy_denial_and_safe_continuation(self) -> None:
        state = two_player_pressure_state()

        candidates = generate_surface_candidates(state, ())

        notes = "|".join(candidate.note or "" for candidate in candidates)
        self.assertIn("enemy_denial", notes)
        self.assertIn(
            MissionType.ATTACK_ENEMY,
            {candidate.mission_type for candidate in candidates},
        )

    def test_four_player_surface_candidates_include_leader_pressure_target(self) -> None:
        state = four_player_rank_state()

        candidates = generate_surface_candidates(state, ())
        missions = generate_mission_plans(
            diagnose_board(state),
            candidates,
        )

        self.assertTrue(candidates)
        self.assertIn(
            MissionFamily.LEADER_PRESSURE,
            {mission.family for mission in missions},
        )

    def test_surface_candidate_cap_is_enforced(self) -> None:
        candidates = generate_surface_candidates(
            two_player_pressure_state(),
            (),
            PlannerV2Config(max_surface_candidates=1),
        )

        self.assertEqual(len(candidates), 1)

    def test_runtime_v2_uses_surface_candidates_without_changing_v1_default(self) -> None:
        state = two_player_pressure_state()

        v1_result = run_planner_pipeline(state)
        v2_result = run_planner_pipeline(
            state,
            RuntimePlannerConfig(
                planner_version=PLANNER_VERSION_V2,
                planner_v2_config=PlannerV2Config(max_surface_candidates=4),
            ),
        )

        self.assertIsNone(v1_result.v2_result)
        self.assertIsNotNone(v2_result.v2_result)
        self.assertGreaterEqual(len(v2_result.candidates), len(v1_result.candidates))
        self.assertTrue(
            any(
                (candidate.note or "").startswith("planner_v2_surface:")
                for candidate in v2_result.candidates
            )
        )


if __name__ == "__main__":
    unittest.main()
