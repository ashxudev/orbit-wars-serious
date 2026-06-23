"""Tests for Planner V2 scenario evaluation."""

from __future__ import annotations

import unittest

from ow_planner import LaunchCandidate
from ow_planner_v2 import (
    ActionSetPlan,
    MissionFamily,
    MissionPlan,
    PlannerV2Config,
    PlannerV2Mode,
    diagnose_board,
    evaluate_action_set_scenarios,
)
from ow_sim.state import Fleet, GameState, Planet


def planet(
    planet_id: int,
    owner: int,
    x: float,
    y: float,
    ships: int,
    production: int,
) -> Planet:
    return Planet(
        planet_id=planet_id,
        owner=owner,
        x=x,
        y=y,
        radius=1.0,
        ships=ships,
        production=production,
        raw=(planet_id, owner, x, y, 1.0, ships, production),
    )


def state(*planets: Planet, fleets: tuple[Fleet, ...] = ()) -> GameState:
    return GameState(
        tick=0,
        player_id=0,
        planets=tuple(planets),
        fleets=fleets,
        initial_planets=tuple(planets),
        next_fleet_id=100,
    )


def action_set(
    plan_id: str,
    family: MissionFamily,
    *,
    source_id: int = 1,
    target_id: int = 2,
    ships: int = 3,
) -> ActionSetPlan:
    return ActionSetPlan(
        plan_id=plan_id,
        missions=(
            MissionPlan(
                mission_id=f"{plan_id}-mission",
                family=family,
                target_planet_id=target_id,
                source_planet_ids=(source_id,),
            ),
        ),
        launches=(
            LaunchCandidate(
                source_planet_id=source_id,
                angle=0.0,
                ships=ships,
                player_id=0,
            ),
        ),
    )


class PlannerV2ScenarioEvaluationTests(unittest.TestCase):
    def test_safe_neutral_expansion_improves_own_production_vs_idle(self) -> None:
        board = state(
            planet(1, 0, 0.0, 0.0, 20, 1),
            planet(2, -1, 5.0, 0.0, 1, 4),
            planet(3, 1, 30.0, 0.0, 10, 2),
        )

        evaluation = evaluate_action_set_scenarios(
            board,
            (action_set("expand", MissionFamily.SAFE_EXPAND, ships=3),),
            diagnose_board(board),
            PlannerV2Config(horizons=(10,)),
        )[0]

        self.assertTrue(evaluation.valid)
        self.assertEqual(len(evaluation.outcomes), 1)
        self.assertGreater(evaluation.outcomes[0].own_production_delta, 0)
        self.assertIn("own_production_gain", evaluation.outcomes[0].notes)

    def test_bad_enemy_pressure_can_drain_source_and_lose_production(self) -> None:
        hostile_fleet = Fleet(
            fleet_id=9,
            owner=1,
            x=-1.0,
            y=0.0,
            angle=0.0,
            from_planet_id=99,
            ships=8,
        )
        board = state(
            planet(1, 0, 0.0, 0.0, 9, 4),
            planet(2, 1, 30.0, 0.0, 1, 4),
            fleets=(hostile_fleet,),
        )

        evaluation = evaluate_action_set_scenarios(
            board,
            (action_set("denial", MissionFamily.ENEMY_PRODUCTION_DENIAL, ships=8),),
            diagnose_board(board),
            PlannerV2Config(horizons=(10,)),
        )[0]

        outcome = evaluation.outcomes[0]
        self.assertTrue(outcome.valid)
        self.assertIn(1, outcome.source_planet_lost_ids)
        self.assertLess(outcome.own_production_delta, 0)
        self.assertIn("source_planet_lost", outcome.notes)

    def test_invalid_launch_returns_invalid_outcome(self) -> None:
        board = state(
            planet(1, 0, 0.0, 0.0, 2, 1),
            planet(2, -1, 5.0, 0.0, 1, 4),
        )

        evaluation = evaluate_action_set_scenarios(
            board,
            (action_set("too-many", MissionFamily.SAFE_EXPAND, ships=5),),
            diagnose_board(board),
            PlannerV2Config(horizons=(10,)),
        )[0]

        self.assertFalse(evaluation.valid)
        self.assertFalse(evaluation.outcomes[0].valid)
        self.assertRegex("|".join(evaluation.outcomes[0].notes), "invalid_launch")

    def test_no_launch_action_set_is_invalid(self) -> None:
        board = state(planet(1, 0, 0.0, 0.0, 20, 1))
        plan = ActionSetPlan(
            plan_id="empty",
            missions=(MissionPlan(mission_id="empty-mission", family=MissionFamily.SAFE_EXPAND),),
            launches=(),
        )

        evaluation = evaluate_action_set_scenarios(
            board,
            (plan,),
            diagnose_board(board),
            PlannerV2Config(horizons=(10,)),
        )[0]

        self.assertFalse(evaluation.valid)
        self.assertEqual(evaluation.outcomes[0].notes, ("no_launches",))

    def test_multi_horizon_evaluation_returns_one_outcome_per_horizon(self) -> None:
        board = state(
            planet(1, 0, 0.0, 0.0, 20, 1),
            planet(2, -1, 5.0, 0.0, 1, 4),
            planet(3, 1, 30.0, 0.0, 10, 1),
        )

        evaluation = evaluate_action_set_scenarios(
            board,
            (action_set("expand", MissionFamily.SAFE_EXPAND, ships=3),),
            diagnose_board(board),
            PlannerV2Config(horizons=(10, 25, 50)),
        )[0]

        self.assertEqual(
            tuple(outcome.horizon for outcome in evaluation.outcomes),
            (10, 25, 50),
        )


if __name__ == "__main__":
    unittest.main()
