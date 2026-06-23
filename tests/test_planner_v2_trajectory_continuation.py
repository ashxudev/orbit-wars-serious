"""Tests for Planner V2 trajectory-continuation preservation behavior."""

from __future__ import annotations

import unittest

from ow_planner import LaunchCandidate
from ow_planner_v2 import (
    ActionSetPlan,
    MissionFamily,
    MissionPlan,
    PlannerV2Config,
    PlannerV2Mode,
    ScenarioEvaluation,
    ScenarioOutcome,
    TrajectoryDiagnosis,
    TrajectoryObjective,
    TrajectoryPhase,
    diagnose_board,
    diagnose_trajectory,
    evaluate_action_set_scenarios,
    generate_mission_plans,
    generate_surface_candidates,
    score_action_set_plans,
)
from ow_planner_v2.missions import mission_family_for_candidate
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
    )


def continuation_state(*, enemy_production: int = 6) -> GameState:
    return GameState(
        tick=40,
        player_id=0,
        planets=(
            planet(1, 0, 0.0, 0.0, 12, 3),
            planet(2, 0, 10.0, 0.0, 1, 2),
            planet(3, 0, 5.0, 5.0, 8, 0),
            planet(4, 1, 50.0, 0.0, 30, enemy_production),
            planet(5, 2, 60.0, 0.0, 20, 3),
            planet(6, 3, 70.0, 0.0, 20, 3),
        ),
    )


def board_diagnosis():
    return diagnose_board(continuation_state())


def trajectory() -> TrajectoryDiagnosis:
    return diagnose_trajectory(continuation_state())


def action_set(
    plan_id: str,
    family: MissionFamily,
    *,
    objectives: tuple[TrajectoryObjective, ...] = (),
    trajectory_targets: tuple[int, ...] = (),
    target_id: int = 2,
) -> ActionSetPlan:
    return ActionSetPlan(
        plan_id=plan_id,
        missions=(
            MissionPlan(
                mission_id=f"{plan_id}-mission",
                family=family,
                target_planet_id=target_id,
                source_planet_ids=(1,),
                trajectory_objectives=objectives,
                trajectory_target_planet_ids=trajectory_targets,
            ),
        ),
        launches=(
            LaunchCandidate(source_planet_id=1, angle=0.0, ships=2, player_id=0),
        ),
    )


def scenario(
    plan_id: str,
    *,
    score: float = 0.0,
    preservation_loss: bool = False,
) -> ScenarioEvaluation:
    return ScenarioEvaluation(
        plan_id=plan_id,
        valid=True,
        outcomes=(
            ScenarioOutcome(
                horizon=10,
                valid=True,
                score=score,
                preservation_target_lost_ids=(2,) if preservation_loss else (),
                preservation_target_lost_production=2 if preservation_loss else 0,
            ),
        ),
    )


class PlannerV2TrajectoryContinuationTests(unittest.TestCase):
    def test_drained_second_source_is_a_preservation_target(self) -> None:
        facts = trajectory()

        self.assertTrue(facts.second_source_secured)
        self.assertTrue(facts.source_drain_risk)
        self.assertFalse(facts.denial_unlocked)
        self.assertEqual(facts.preservation_target_planet_ids, (2,))
        self.assertIn(TrajectoryObjective.PRESERVE_PRIMARY_SOURCE, facts.recommended_objectives)
        self.assertIn(TrajectoryObjective.HOLD_RECENT_CAPTURE, facts.recommended_objectives)

    def test_preservation_surface_creates_reinforce_candidate(self) -> None:
        state = continuation_state()

        candidates = generate_surface_candidates(
            state,
            (),
            PlannerV2Config(max_surface_candidates=8),
        )

        preservation = tuple(
            candidate
            for candidate in candidates
            if candidate.note == "planner_v2_surface:trajectory_preserve_source"
        )
        self.assertEqual(len(preservation), 1)
        self.assertEqual(preservation[0].target_planet_id, 2)
        self.assertEqual(preservation[0].source_planet_ids, (3,))
        self.assertGreater(preservation[0].launches[0].ships, 0)

    def test_preservation_surface_is_config_gated(self) -> None:
        state = continuation_state()

        candidates = generate_surface_candidates(
            state,
            (),
            PlannerV2Config(
                max_surface_candidates=8,
                enable_trajectory_continuation=False,
            ),
        )

        self.assertFalse(
            any(
                candidate.note == "planner_v2_surface:trajectory_preserve_source"
                for candidate in candidates
            )
        )

    def test_preservation_candidate_maps_to_hold_objectives(self) -> None:
        state = continuation_state()
        facts = diagnose_trajectory(state)
        candidates = generate_surface_candidates(
            state,
            (),
            PlannerV2Config(max_surface_candidates=8),
        )
        candidate = next(
            candidate
            for candidate in candidates
            if candidate.note == "planner_v2_surface:trajectory_preserve_source"
        )

        self.assertEqual(
            mission_family_for_candidate(candidate, diagnose_board(state)),
            MissionFamily.HOLD_CAPTURE,
        )
        missions = generate_mission_plans(
            diagnose_board(state),
            (candidate,),
            config=PlannerV2Config(),
            trajectory_diagnosis=facts,
        )

        self.assertEqual(missions[0].family, MissionFamily.HOLD_CAPTURE)
        self.assertEqual(missions[0].trajectory_target_planet_ids, (2,))
        self.assertEqual(
            missions[0].trajectory_objectives,
            (
                TrajectoryObjective.PRESERVE_PRIMARY_SOURCE,
                TrajectoryObjective.HOLD_RECENT_CAPTURE,
            ),
        )

    def test_scenario_eval_tracks_preservation_target_loss(self) -> None:
        board = GameState(
            tick=0,
            player_id=0,
            planets=(
                planet(1, 0, 0.0, 10.0, 10, 3),
                planet(2, 0, 0.0, 0.0, 1, 2),
                planet(3, 1, 50.0, 0.0, 20, 5),
            ),
            fleets=(Fleet(99, 1, -1.0, 0.0, 0.0, 5, 10),),
            initial_planets=(
                planet(1, 0, 0.0, 10.0, 10, 3),
                planet(2, 0, 0.0, 0.0, 1, 2),
                planet(3, 1, 50.0, 0.0, 20, 5),
            ),
            next_fleet_id=100,
        )
        facts = TrajectoryDiagnosis(
            turn=0,
            phase=TrajectoryPhase.OPENING,
            player_id=0,
            owned_planet_count=2,
            owned_production=5,
            owned_ships=11,
            owned_fleet_ships=0,
            best_neutral_production_available=0,
            second_source_secured=True,
            source_drain_risk=True,
            preservation_target_planet_ids=(2,),
            recommended_objectives=(TrajectoryObjective.PRESERVE_PRIMARY_SOURCE,),
        )

        evaluation = evaluate_action_set_scenarios(
            board,
            (
                action_set(
                    "ignore-preservation",
                    MissionFamily.ENEMY_PRODUCTION_DENIAL,
                    target_id=3,
                ),
            ),
            diagnose_board(board),
            PlannerV2Config(horizons=(10,)),
            trajectory_diagnosis=facts,
        )[0]

        outcome = evaluation.outcomes[0]
        self.assertEqual(outcome.preservation_target_lost_ids, (2,))
        self.assertEqual(outcome.preservation_target_lost_production, 2)
        self.assertIn("preservation_target_lost", outcome.notes)

    def test_scoring_prefers_preservation_until_denial_is_unlocked(self) -> None:
        preserve = action_set(
            "preserve",
            MissionFamily.HOLD_CAPTURE,
            objectives=(
                TrajectoryObjective.PRESERVE_PRIMARY_SOURCE,
                TrajectoryObjective.HOLD_RECENT_CAPTURE,
            ),
            trajectory_targets=(2,),
        )
        denial = action_set("denial", MissionFamily.ENEMY_PRODUCTION_DENIAL, target_id=4)

        evaluated = score_action_set_plans(
            (denial, preserve),
            board_diagnosis(),
            scenario_evaluations=(
                scenario("denial", score=20.0),
                scenario("preserve", score=0.0),
            ),
            trajectory_diagnosis=trajectory(),
        )

        self.assertEqual(evaluated[0].plan.plan_id, "preserve")
        self.assertIn(
            ("trajectory_preservation_bonus", 100.0),
            evaluated[0].score_components,
        )
        self.assertIn(
            ("trajectory_denial_locked_guard", -80.0),
            evaluated[1].score_components,
        )

    def test_scoring_allows_denial_after_stabilization(self) -> None:
        stable = TrajectoryDiagnosis(
            turn=55,
            phase=TrajectoryPhase.EARLY_BASE,
            player_id=0,
            owned_planet_count=2,
            owned_production=5,
            owned_ships=30,
            owned_fleet_ships=0,
            best_neutral_production_available=0,
            second_source_secured=True,
            source_drain_risk=False,
            denial_unlocked=True,
            recommended_objectives=(TrajectoryObjective.DENY_AFTER_STABILIZING,),
        )
        preserve = action_set(
            "preserve",
            MissionFamily.HOLD_CAPTURE,
            objectives=(TrajectoryObjective.PRESERVE_PRIMARY_SOURCE,),
            trajectory_targets=(2,),
        )
        denial = action_set("denial", MissionFamily.ENEMY_PRODUCTION_DENIAL, target_id=4)

        evaluated = score_action_set_plans(
            (preserve, denial),
            board_diagnosis(),
            scenario_evaluations=(
                scenario("preserve", score=0.0),
                scenario("denial", score=20.0),
            ),
            trajectory_diagnosis=stable,
        )

        self.assertEqual(evaluated[0].plan.plan_id, "denial")
        self.assertNotIn(
            ("trajectory_denial_locked_guard", -80.0),
            evaluated[0].score_components,
        )


if __name__ == "__main__":
    unittest.main()
