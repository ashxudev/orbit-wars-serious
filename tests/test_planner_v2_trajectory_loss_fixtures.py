"""Trajectory-loss fixtures for Planner V2 strategic-collapse diagnosis."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from agents.runtime_actions import planner_result_to_actions
from agents.orbit_wars_agent_v2_trajectory_off import (
    runtime_turn_config_for_observation as trajectory_off_runtime_config,
)
from agents.runtime_planner import (
    PLANNER_VERSION_V2,
    RuntimePlannerConfig,
    run_planner_pipeline,
)
from agents.runtime_state import observation_to_game_state
from ow_planner import CandidateGenerationConfig
from ow_planner_v2 import PlannerV2Config, diagnose_trajectory, generate_surface_candidates
from ow_planner_v2.diagnostics import planner_v2_diagnostics
from ow_sim.state import GameState, Planet


FIXTURE_DIR = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "planner_v2_trajectory_losses"
)

REQUIRED_CASE_IDS = {
    "two_p_trajectory_t000_p1",
    "two_p_trajectory_t005_p1",
    "two_p_trajectory_t010_p1",
    "two_p_trajectory_t015_p1",
    "two_p_trajectory_t020_p1",
    "two_p_trajectory_t030_p1",
    "two_p_trajectory_t040_p1",
    "two_p_trajectory_t054_p1",
    "four_p_trajectory_t000_p3",
    "four_p_trajectory_t005_p3",
    "four_p_trajectory_t010_p3",
    "four_p_trajectory_t015_p3",
    "four_p_trajectory_t020_p3",
    "four_p_trajectory_t030_p3",
    "four_p_trajectory_t040_p3",
    "four_p_trajectory_t060_p3",
}

TRAJECTORY_LABELS = {
    "under_expanded",
    "single_source_fragile",
    "source_drained",
    "late_denial_before_base",
    "hold_failure",
    "locally_unrecoverable_terminal",
    "production_gap_to_leader",
    "second_source_secured",
}


def fixture_paths() -> tuple[Path, ...]:
    return tuple(sorted(FIXTURE_DIR.glob("*.json")))


def load_case(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_v2(observation: object):
    if not isinstance(observation, dict):
        raise AssertionError("observation must be a dictionary")
    state = observation_to_game_state(observation)
    result = run_planner_pipeline(
        state,
        RuntimePlannerConfig(
            planner_version=PLANNER_VERSION_V2,
            candidate_config=CandidateGenerationConfig(
                max_candidates=8,
                max_validation_attempts=8,
            ),
            planner_v2_config=PlannerV2Config(max_action_sets=4),
        ),
    )
    if result.v2_result is None:
        raise AssertionError("planner v2 result missing")
    return state, result.v2_result, planner_result_to_actions(result)


def selected_target_class(state, selected) -> str | None:
    if selected is None or not selected.plan.missions:
        return None
    target_id = selected.plan.missions[0].target_planet_id
    if target_id is None:
        return None
    owner = next(
        (planet.owner for planet in state.planets if planet.planet_id == target_id),
        None,
    )
    if owner is None:
        return "missing"
    if owner == state.player_id:
        return "owned"
    if owner < 0:
        return "neutral"
    return "enemy"


class PlannerV2TrajectoryLossFixtureTests(unittest.TestCase):
    def test_fixture_set_exists_and_is_compact(self) -> None:
        paths = fixture_paths()

        self.assertEqual(len(paths), 16)
        self.assertEqual({load_case(path)["case_id"] for path in paths}, REQUIRED_CASE_IDS)
        for path in paths:
            with self.subTest(path=path.name):
                payload = load_case(path)
                self.assertIn("observation", payload)
                self.assertNotIn("steps", payload)
                self.assertNotIn("steps", payload["observation"])
                self.assertEqual(payload["episode_steps"], 500)
                self.assertTrue(str(payload["source_replay_path"]).startswith("/tmp/"))
                self.assertTrue(str(payload["source_result_path"]).startswith("/tmp/"))

    def test_observations_parse_and_trajectory_matches_expected_metadata(self) -> None:
        for path in fixture_paths():
            with self.subTest(path=path.name):
                payload = load_case(path)
                expected = payload["expected_current_v2_runtime"]
                state = observation_to_game_state(payload["observation"])
                owned = tuple(
                    planet for planet in state.planets if planet.owner == state.player_id
                )
                trajectory = diagnose_trajectory(state)

                self.assertEqual(state.player_id, payload["player_id"])
                self.assertEqual(state.tick, payload["turn"])
                self.assertEqual(len(owned), expected["owned_planet_count"])
                self.assertEqual(
                    sum(planet.production for planet in owned),
                    expected["owned_production"],
                )
                self.assertEqual(trajectory.to_dict(), expected["trajectory"])
                self.assertEqual(list(trajectory.labels), payload["trajectory_labels"])
                self.assertEqual(
                    [objective.value for objective in trajectory.recommended_objectives],
                    payload["trajectory_objectives"],
                )

    def test_v2_runtime_diagnostics_match_fixture_characterization(self) -> None:
        for path in fixture_paths():
            with self.subTest(path=path.name):
                payload = load_case(path)
                expected = payload["expected_current_v2_runtime"]
                state, result, actions = run_v2(payload["observation"])
                diagnostics = planner_v2_diagnostics(result)
                selected = result.selected_plan

                self.assertEqual(len(actions), expected["action_count"])
                self.assertEqual(
                    sum(
                        planet.production
                        for planet in state.planets
                        if planet.owner == state.player_id
                    ),
                    expected["owned_production"],
                )
                self.assertEqual(
                    diagnostics["planner_v2_selected_family"],
                    expected["selected_family"],
                )
                self.assertEqual(
                    selected_target_class(state, selected),
                    expected["selected_target_class"],
                )
                self.assertEqual(
                    result.no_action_reason or "actions_emitted",
                    expected["no_action_reason"],
                )
                self.assertEqual(
                    diagnostics["planner_v2_mission_family_counts"],
                    expected["mission_family_counts"],
                )
                self.assertEqual(
                    diagnostics["planner_v2_prune_reason_counts"],
                    expected["prune_reason_counts"],
                )

    def test_trajectory_labels_cover_requested_failure_classes(self) -> None:
        labels = {
            label
            for path in fixture_paths()
            for label in load_case(path)["trajectory_labels"]
        }

        self.assertTrue(labels <= TRAJECTORY_LABELS)
        self.assertIn("under_expanded", labels)
        self.assertIn("single_source_fragile", labels)
        self.assertIn("source_drained", labels)
        self.assertIn("late_denial_before_base", labels)
        self.assertIn("production_gap_to_leader", labels)

    def test_early_fragile_states_recommend_base_security_objectives(self) -> None:
        for path in fixture_paths():
            payload = load_case(path)
            labels = set(payload["trajectory_labels"])
            if not (
                "single_source_fragile" in labels
                or "under_expanded" in labels
            ):
                continue
            with self.subTest(path=path.name):
                objectives = set(payload["trajectory_objectives"])
                self.assertIn("secure_second_source", objectives)
                self.assertIn("preserve_primary_source", objectives)

    def test_trajectory_second_source_surface_can_be_disabled_for_ab_tests(self) -> None:
        state = GameState(
            tick=20,
            player_id=0,
            planets=(
                Planet(1, 0, 0.0, 0.0, 1.0, 20, 5),
                Planet(2, -1, 5.0, 0.0, 1.0, 3, 4),
                Planet(3, 1, 30.0, 0.0, 1.0, 20, 5),
            ),
        )

        enabled = generate_surface_candidates(
            state,
            (),
            config=PlannerV2Config(max_surface_candidates=8),
        )
        disabled = generate_surface_candidates(
            state,
            (),
            config=PlannerV2Config(
                max_surface_candidates=8,
                enable_trajectory_second_source=False,
            ),
        )

        self.assertTrue(
            any(
                candidate.note == "planner_v2_surface:trajectory_second_source"
                for candidate in enabled
            )
        )
        self.assertFalse(
            any(
                candidate.note == "planner_v2_surface:trajectory_second_source"
                for candidate in disabled
            )
        )

    def test_trajectory_diagnostics_remain_when_surface_is_disabled(self) -> None:
        payload = load_case(FIXTURE_DIR / "two_p_trajectory_t020_p1.json")
        state = observation_to_game_state(payload["observation"])
        result = run_planner_pipeline(
            state,
            RuntimePlannerConfig(
                planner_version=PLANNER_VERSION_V2,
                candidate_config=CandidateGenerationConfig(
                    max_candidates=8,
                    max_validation_attempts=8,
                ),
                planner_v2_config=PlannerV2Config(
                    max_action_sets=4,
                    enable_trajectory_second_source=False,
                ),
            ),
        )

        self.assertIsNotNone(result.v2_result)
        diagnostics = planner_v2_diagnostics(result.v2_result)
        self.assertEqual(
            diagnostics["planner_v2_trajectory_labels"],
            payload["trajectory_labels"],
        )
        self.assertEqual(
            diagnostics["planner_v2_trajectory_objectives"],
            payload["trajectory_objectives"],
        )

    def test_trajectory_off_agent_entrypoint_uses_v2_with_surface_disabled(self) -> None:
        payload = load_case(FIXTURE_DIR / "two_p_trajectory_t020_p1.json")

        config = trajectory_off_runtime_config(payload["observation"])

        self.assertIsNotNone(config.planner_config)
        self.assertEqual(config.planner_config.planner_version, PLANNER_VERSION_V2)
        self.assertIsNotNone(config.planner_config.planner_v2_config)
        self.assertFalse(
            config.planner_config.planner_v2_config.enable_trajectory_second_source
        )


if __name__ == "__main__":
    unittest.main()
