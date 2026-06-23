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
    ScenarioEvaluation,
    ScenarioOutcome,
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


def evaluated(
    plan_id: str,
    family: MissionFamily,
    score: float,
    *,
    scenario_valid: bool | None = None,
    eliminated: bool = False,
) -> EvaluatedPlan:
    plan = ActionSetPlan(
        plan_id=plan_id,
        missions=(MissionPlan(mission_id=f"{plan_id}-mission", family=family),),
        launches=(LaunchCandidate(source_planet_id=1, angle=0.0, ships=1, player_id=0),),
    )
    scenario = None
    if scenario_valid is not None:
        scenario = ScenarioEvaluation(
            plan_id=plan_id,
            valid=scenario_valid,
            outcomes=(
                ScenarioOutcome(
                    horizon=10,
                    valid=scenario_valid,
                    score=score,
                    eliminated=eliminated,
                    notes=("eliminated",) if eliminated else (),
                ),
            ),
        )
    return EvaluatedPlan(plan=plan, score=score, scenario_evaluation=scenario)


class PlannerV2FallbackTests(unittest.TestCase):
    def test_scenario_score_beats_static_family_ladder(self) -> None:
        selected, reason, notes = select_evaluated_plan(
            (
                evaluated("rank", MissionFamily.RANK_SWING, 100.0),
                evaluated("expand", MissionFamily.SAFE_EXPAND, 50.0),
            ),
            diagnosis(),
        )

        self.assertIsNotNone(selected)
        self.assertEqual(selected.plan.plan_id, "rank")
        self.assertIsNone(reason)
        self.assertIn("fallback ladder selected plan", notes)

    def test_no_owned_planets_is_explicit_no_action_reason(self) -> None:
        selected, reason, _notes = select_evaluated_plan((), diagnosis(owned_planets=0))

        self.assertIsNone(selected)
        self.assertEqual(reason, "source_less_no_owned_planets")

    def test_family_ladder_breaks_only_close_scores(self) -> None:
        selected, reason, _notes = select_evaluated_plan(
            (
                evaluated("expand", MissionFamily.SAFE_EXPAND, 100.0),
                evaluated("denial", MissionFamily.ENEMY_PRODUCTION_DENIAL, 99.9),
            ),
            diagnosis(mode=PlannerV2Mode.TWO_PLAYER),
        )

        self.assertIsNone(reason)
        self.assertIsNotNone(selected)
        self.assertEqual(selected.plan.plan_id, "denial")

    def test_invalid_scenario_plans_are_skipped_when_valid_alternative_exists(self) -> None:
        selected, reason, _notes = select_evaluated_plan(
            (
                evaluated("invalid", MissionFamily.ENEMY_PRODUCTION_DENIAL, 500.0, scenario_valid=False),
                evaluated("expand", MissionFamily.SAFE_EXPAND, 10.0, scenario_valid=True),
            ),
            diagnosis(mode=PlannerV2Mode.TWO_PLAYER),
        )

        self.assertIsNone(reason)
        self.assertIsNotNone(selected)
        self.assertEqual(selected.plan.plan_id, "expand")

    def test_eliminating_scenario_plans_are_skipped_when_viable_alternative_exists(self) -> None:
        selected, reason, _notes = select_evaluated_plan(
            (
                evaluated(
                    "collapse",
                    MissionFamily.ENEMY_PRODUCTION_DENIAL,
                    500.0,
                    scenario_valid=True,
                    eliminated=True,
                ),
                evaluated("expand", MissionFamily.SAFE_EXPAND, 10.0, scenario_valid=True),
            ),
            diagnosis(mode=PlannerV2Mode.TWO_PLAYER),
        )

        self.assertIsNone(reason)
        self.assertIsNotNone(selected)
        self.assertEqual(selected.plan.plan_id, "expand")


if __name__ == "__main__":
    unittest.main()
