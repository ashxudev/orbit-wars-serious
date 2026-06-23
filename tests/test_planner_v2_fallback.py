"""Tests for Planner V2 fallback selection."""

from __future__ import annotations

import unittest

from ow_planner import LaunchCandidate
from ow_planner_v2 import (
    ActionSetPlan,
    BoardDiagnosis,
    EvaluatedPlan,
    MissionFamily,
    MissionPlan,
    PlannerV2Mode,
    select_evaluated_plan,
)


def diagnosis(*, owned_planets: int = 1, mode: PlannerV2Mode = PlannerV2Mode.FOUR_PLAYER) -> BoardDiagnosis:
    return BoardDiagnosis(
        mode=mode,
        player_id=0,
        active_player_ids=(0, 1, 2, 3),
        opponent_player_ids=(1, 2, 3),
        owned_planet_count=owned_planets,
        owned_production=3 if owned_planets else 0,
        owned_planet_ships=20 if owned_planets else 0,
        owned_fleet_ships=0,
        opponent_production=9,
        opponent_planet_ships=90,
        neutral_production=4,
    )


def evaluated(plan_id: str, family: MissionFamily, score: float) -> EvaluatedPlan:
    plan = ActionSetPlan(
        plan_id=plan_id,
        missions=(MissionPlan(mission_id=f"{plan_id}-mission", family=family),),
        launches=(LaunchCandidate(source_planet_id=1, angle=0.0, ships=1, player_id=0),),
    )
    return EvaluatedPlan(plan=plan, score=score)


class PlannerV2FallbackTests(unittest.TestCase):
    def test_selects_safe_expansion_before_lower_ladder_rank(self) -> None:
        selected, reason, notes = select_evaluated_plan(
            (
                evaluated("rank", MissionFamily.RANK_SWING, 100.0),
                evaluated("expand", MissionFamily.SAFE_EXPAND, 50.0),
            ),
            diagnosis(),
        )

        self.assertIsNotNone(selected)
        self.assertEqual(selected.plan.plan_id, "expand")
        self.assertIsNone(reason)
        self.assertIn("fallback ladder selected plan", notes)

    def test_no_owned_planets_is_explicit_no_action_reason(self) -> None:
        selected, reason, _notes = select_evaluated_plan((), diagnosis(owned_planets=0))

        self.assertIsNone(selected)
        self.assertEqual(reason, "source_less_no_owned_planets")

    def test_two_player_denial_is_preferred_before_safe_expansion(self) -> None:
        selected, reason, _notes = select_evaluated_plan(
            (
                evaluated("expand", MissionFamily.SAFE_EXPAND, 100.0),
                evaluated("denial", MissionFamily.ENEMY_PRODUCTION_DENIAL, 20.0),
            ),
            diagnosis(mode=PlannerV2Mode.TWO_PLAYER),
        )

        self.assertIsNone(reason)
        self.assertIsNotNone(selected)
        self.assertEqual(selected.plan.plan_id, "denial")


if __name__ == "__main__":
    unittest.main()
