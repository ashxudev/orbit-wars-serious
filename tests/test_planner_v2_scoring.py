"""Tests for Planner V2 action-set scoring."""

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
    PlannerV2Config,
    ScenarioEvaluation,
    ScenarioOutcome,
    score_action_set_plans,
)


def diagnosis(*, threatened: bool = False) -> BoardDiagnosis:
    return BoardDiagnosis(
        mode=PlannerV2Mode.TWO_PLAYER,
        player_id=0,
        active_player_ids=(0, 1),
        opponent_player_ids=(1,),
        owned_planet_count=1,
        owned_production=3,
        owned_planet_ships=20,
        owned_fleet_ships=0,
        opponent_production=4,
        opponent_planet_ships=30,
        neutral_production=3,
        vulnerable_owned_planet_ids=(1,) if threatened else (),
    )


def action_set(plan_id: str, family: MissionFamily) -> ActionSetPlan:
    return ActionSetPlan(
        plan_id=plan_id,
        missions=(
            MissionPlan(
                mission_id=f"{plan_id}-mission",
                family=family,
                priority=20.0 if family is MissionFamily.URGENT_DEFEND else 80.0,
            ),
        ),
        launches=(LaunchCandidate(source_planet_id=1, angle=0.0, ships=2, player_id=0),),
        labels=(family.value,),
    )


def scenario(
    plan_id: str,
    *,
    score: float,
    valid: bool = True,
    eliminated: bool = False,
    source_loss: bool = False,
    source_loss_production: int = 0,
    source_counterattack_loss: bool = False,
    source_counterattack_loss_production: int = 0,
    target_hold_failure: bool = False,
    target_hold_failure_production: int = 0,
    vulnerable_loss: bool = False,
    vulnerable_loss_production: int = 0,
) -> ScenarioEvaluation:
    return ScenarioEvaluation(
        plan_id=plan_id,
        valid=valid,
        outcomes=(
            ScenarioOutcome(
                horizon=10,
                valid=valid,
                score=score,
                source_planet_lost_ids=(1,) if source_loss else (),
                source_planet_lost_production=source_loss_production,
                source_counterattack_lost_ids=(
                    (1,) if source_counterattack_loss else ()
                ),
                source_counterattack_lost_production=(
                    source_counterattack_loss_production
                ),
                target_hold_failure_ids=(2,) if target_hold_failure else (),
                target_hold_failure_production=target_hold_failure_production,
                vulnerable_planet_lost_ids=(1,) if vulnerable_loss else (),
                vulnerable_planet_lost_production=vulnerable_loss_production,
                eliminated=eliminated,
            ),
        ),
    )


class PlannerV2ScoringTests(unittest.TestCase):
    def test_urgent_defense_beats_expansion_under_threat(self) -> None:
        evaluated = score_action_set_plans(
            (
                action_set("expand", MissionFamily.SAFE_EXPAND),
                action_set("defend", MissionFamily.URGENT_DEFEND),
            ),
            diagnosis(threatened=True),
        )

        self.assertIsInstance(evaluated[0], EvaluatedPlan)
        self.assertEqual(evaluated[0].plan.plan_id, "defend")
        self.assertGreater(evaluated[0].score, evaluated[1].score)

    def test_scores_all_configured_horizons_and_endgame_horizon(self) -> None:
        endgame = BoardDiagnosis(
            mode=PlannerV2Mode.ENDGAME,
            player_id=0,
            active_player_ids=(0, 1),
            opponent_player_ids=(1,),
            owned_planet_count=1,
            owned_production=1,
            owned_planet_ships=5,
            owned_fleet_ships=0,
            opponent_production=2,
            opponent_planet_ships=12,
            neutral_production=0,
            labels=("late_game_state",),
        )

        evaluated = score_action_set_plans(
            (action_set("liquidate", MissionFamily.LATE_LIQUIDATION),),
            endgame,
            PlannerV2Config(horizons=(10, 25), endgame_horizon=80),
        )

        self.assertEqual(
            tuple(horizon for horizon, _score in evaluated[0].horizon_scores),
            (10, 25, 80),
        )
        self.assertEqual(evaluated[0].selected_horizon, 80)

    def test_scenario_safe_expansion_beats_static_enemy_denial_priority(self) -> None:
        plans = (
            action_set("denial", MissionFamily.ENEMY_PRODUCTION_DENIAL),
            action_set("expand", MissionFamily.SAFE_EXPAND),
        )

        evaluated = score_action_set_plans(
            plans,
            diagnosis(),
            scenario_evaluations=(
                scenario("denial", score=-200.0, source_loss=True),
                scenario("expand", score=40.0),
            ),
        )

        self.assertEqual(evaluated[0].plan.plan_id, "expand")
        self.assertGreater(evaluated[0].score, evaluated[1].score)
        self.assertIsNotNone(evaluated[0].scenario_evaluation)

    def test_elimination_penalty_dominates_family_priority(self) -> None:
        plans = (
            action_set("denial", MissionFamily.ENEMY_PRODUCTION_DENIAL),
            action_set("expand", MissionFamily.SAFE_EXPAND),
        )

        evaluated = score_action_set_plans(
            plans,
            diagnosis(),
            scenario_evaluations=(
                scenario("denial", score=100.0, eliminated=True),
                scenario("expand", score=20.0),
            ),
        )

        self.assertEqual(evaluated[0].plan.plan_id, "expand")

    def test_source_and_vulnerable_loss_penalties_dominate_small_denial_bonus(self) -> None:
        plans = (
            action_set("denial", MissionFamily.ENEMY_PRODUCTION_DENIAL),
            action_set("defend", MissionFamily.URGENT_DEFEND),
        )

        evaluated = score_action_set_plans(
            plans,
            diagnosis(threatened=True),
            scenario_evaluations=(
                scenario("denial", score=50.0, source_loss=True, vulnerable_loss=True),
                scenario("defend", score=10.0),
            ),
        )

        self.assertEqual(evaluated[0].plan.plan_id, "defend")

    def test_critical_source_production_loss_dominates_optimistic_best_horizon(self) -> None:
        plans = (
            action_set("denial", MissionFamily.ENEMY_PRODUCTION_DENIAL),
            action_set("expand", MissionFamily.SAFE_EXPAND),
        )

        evaluated = score_action_set_plans(
            plans,
            diagnosis(),
            scenario_evaluations=(
                scenario(
                    "denial",
                    score=500.0,
                    source_loss=True,
                    source_loss_production=3,
                ),
                scenario("expand", score=20.0),
            ),
        )

        self.assertEqual(evaluated[0].plan.plan_id, "expand")
        self.assertIn(
            ("critical_source_production_loss_guard", -540.0),
            evaluated[1].score_components,
        )

    def test_counterattack_and_hold_failure_guards_penalize_brittle_capture(self) -> None:
        plans = (
            action_set("thin-capture", MissionFamily.ENEMY_PRODUCTION_DENIAL),
            action_set("expand", MissionFamily.SAFE_EXPAND),
        )

        evaluated = score_action_set_plans(
            plans,
            diagnosis(),
            scenario_evaluations=(
                scenario(
                    "thin-capture",
                    score=450.0,
                    source_counterattack_loss=True,
                    source_counterattack_loss_production=3,
                    target_hold_failure=True,
                    target_hold_failure_production=4,
                ),
                scenario("expand", score=20.0),
            ),
        )

        self.assertEqual(evaluated[0].plan.plan_id, "expand")
        self.assertIn(
            ("source_counterattack_production_guard", -420.0),
            evaluated[1].score_components,
        )
        self.assertIn(
            ("target_hold_failure_production_guard", -320.0),
            evaluated[1].score_components,
        )

    def test_family_prior_only_breaks_close_scenario_scores(self) -> None:
        plans = (
            action_set("denial", MissionFamily.ENEMY_PRODUCTION_DENIAL),
            action_set("expand", MissionFamily.SAFE_EXPAND),
        )

        evaluated = score_action_set_plans(
            plans,
            diagnosis(),
            scenario_evaluations=(
                scenario("denial", score=20.0),
                scenario("expand", score=20.0),
            ),
        )

        self.assertEqual(evaluated[0].plan.plan_id, "expand")


if __name__ == "__main__":
    unittest.main()
