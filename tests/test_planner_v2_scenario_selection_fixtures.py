"""Scenario-selection fixtures extracted from post-surface V2 Daytona probes."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from agents.runtime_budget import RuntimeBudgetConfig
from agents.runtime_planner import PLANNER_VERSION_V2, RuntimePlannerConfig, run_planner_pipeline
from agents.runtime_state import observation_to_game_state
from agents.runtime_turn import RuntimeTurnConfig, last_runtime_diagnostic_metadata, safe_actions_for_observation
from ow_planner import CandidateGenerationConfig
from ow_planner_v2 import PlannerV2Config


FIXTURE_DIR = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "planner_v2_scenario_selection"
)

REQUIRED_CASE_IDS = {
    "two_p_scenario_selection_t020_p1",
    "two_p_scenario_selection_t040_p1",
    "two_p_scenario_selection_t054_p1",
    "two_p_scenario_selection_t060_p1",
    "four_p_scenario_selection_t020_p3",
    "four_p_scenario_selection_t040_p3",
    "four_p_scenario_selection_t060_p3",
    "four_p_scenario_selection_t080_p3",
}

FAILURE_CLASSES = {
    "early_collapse",
    "over_aggressive_enemy_pressure",
    "source_drain",
    "under_expansion",
}


def fixture_paths() -> tuple[Path, ...]:
    return tuple(sorted(FIXTURE_DIR.glob("*.json")))


def load_case(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def planner_v2_runtime_config() -> RuntimeTurnConfig:
    return RuntimeTurnConfig(
        planner_config=RuntimePlannerConfig(
            planner_version=PLANNER_VERSION_V2,
            candidate_config=CandidateGenerationConfig(
                max_candidates=8,
                max_validation_attempts=8,
            ),
            planner_v2_config=PlannerV2Config(),
        ),
        budget_config=RuntimeBudgetConfig(
            turn_budget_seconds=60.0,
            minimum_stage_start_seconds=0.0,
        ),
    )


def run_bounded_v2_runtime(observation: object) -> tuple[int, dict[str, str]]:
    if not isinstance(observation, dict):
        raise AssertionError("observation must be a dictionary")
    actions = safe_actions_for_observation(observation, None, planner_v2_runtime_config())
    return len(actions), dict(last_runtime_diagnostic_metadata())


class PlannerV2ScenarioSelectionFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runtime_results = {}
        for path in fixture_paths():
            payload = load_case(path)
            cls.runtime_results[payload["case_id"]] = run_bounded_v2_runtime(
                payload["observation"],
            )

    def test_fixture_set_exists_and_is_compact(self) -> None:
        paths = fixture_paths()

        self.assertEqual(len(paths), 8)
        self.assertEqual({load_case(path)["case_id"] for path in paths}, REQUIRED_CASE_IDS)
        for path in paths:
            with self.subTest(path=path.name):
                payload = load_case(path)
                self.assertNotIn("steps", payload)
                self.assertIn("observation", payload)
                self.assertNotIn("steps", payload["observation"])
                self.assertIn(payload["player_count"], (2, 4))
                self.assertIn(payload["failure_class"], FAILURE_CLASSES)
                self.assertTrue(str(payload["source_replay_path"]).startswith("/tmp/"))
                self.assertTrue(str(payload["source_result_path"]).startswith("/tmp/"))

    def test_observations_parse_and_match_fixture_metadata(self) -> None:
        for path in fixture_paths():
            with self.subTest(path=path.name):
                payload = load_case(path)
                expected = payload["expected_current_v2_runtime"]
                state = observation_to_game_state(payload["observation"])
                owned = [
                    planet for planet in state.planets if planet.owner == state.player_id
                ]

                self.assertEqual(state.player_id, payload["player_id"])
                self.assertEqual(state.tick, payload["turn"])
                self.assertEqual(len(owned), expected["owned_planet_count"])
                self.assertEqual(
                    sum(planet.production for planet in owned),
                    expected["owned_production"],
                )

    def test_bounded_v2_runtime_matches_expected_characterization(self) -> None:
        for path in fixture_paths():
            with self.subTest(path=path.name):
                payload = load_case(path)
                expected = payload["expected_current_v2_runtime"]
                action_count, metadata = self.runtime_results[payload["case_id"]]

                self.assertEqual(action_count, expected["action_count"])
                self.assertEqual(
                    metadata["runtime_diagnostic_status"],
                    expected["diagnostic_status"],
                )
                self.assertEqual(
                    metadata["runtime_diagnostic_no_action_reason"],
                    expected["no_action_reason"],
                )
                self.assertEqual(
                    int(metadata["runtime_diagnostic_candidate_count"]),
                    expected["candidate_count"],
                )
                self.assertEqual(
                    int(metadata["runtime_diagnostic_evaluation_count"]),
                    expected["evaluation_count"],
                )

    def test_selected_v2_plan_exposes_scenario_diagnostics(self) -> None:
        for path in fixture_paths():
            payload = load_case(path)
            expected = payload["expected_current_v2_runtime"]
            if expected["action_count"] == 0:
                continue
            with self.subTest(case=payload["case_id"]):
                state = observation_to_game_state(payload["observation"])
                result = run_planner_pipeline(
                    state,
                    planner_v2_runtime_config().planner_config,
                )
                selected = result.v2_result.selected_plan if result.v2_result else None

                self.assertIsNotNone(selected)
                self.assertIsNotNone(selected.scenario_evaluation)
                self.assertEqual(
                    selected.plan.missions[0].family.value,
                    expected["selected_family"],
                )
                self.assertEqual(
                    selected.plan.missions[0].mission_type.value,
                    expected["selected_mission_type"],
                )
                self.assertEqual(
                    selected.selected_horizon,
                    expected["selected_horizon"],
                )
                self.assertEqual(
                    selected.scenario_evaluation.valid,
                    True,
                )

    def test_fixture_failure_classes_cover_collapse_and_pressure_patterns(self) -> None:
        classes = {load_case(path)["failure_class"] for path in fixture_paths()}

        self.assertIn("early_collapse", classes)
        self.assertIn("over_aggressive_enemy_pressure", classes)
        self.assertIn("under_expansion", classes)


if __name__ == "__main__":
    unittest.main()
