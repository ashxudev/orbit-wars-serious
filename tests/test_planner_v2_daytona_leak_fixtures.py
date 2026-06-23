"""Characterization tests for Planner V2 Daytona leak fixtures."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from agents.orbit_wars_agent_v2 import agent as planner_v2_agent
from agents.runtime_state import observation_to_game_state
from agents.runtime_turn import last_runtime_diagnostic_metadata


FIXTURE_DIR = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "planner_v2_daytona_leaks"
)

REQUIRED_CASE_IDS = {
    "two_p_claude_v31_t060_p1",
    "two_p_claude_v31_t080_p1",
    "two_p_claude_v31_t098_p1",
    "two_p_enemy_denial_absent_t090_p1",
    "four_p_top_score_t150_p3",
    "four_p_top_score_t176_p3",
    "four_p_top_score_t183_p3",
    "four_p_rank_pressure_absent_t120_p3",
}

COLLAPSE_CASE_IDS = {
    "two_p_claude_v31_t060_p1",
    "two_p_claude_v31_t080_p1",
    "two_p_claude_v31_t098_p1",
    "four_p_top_score_t150_p3",
    "four_p_top_score_t176_p3",
    "four_p_top_score_t183_p3",
}


def fixture_paths() -> tuple[Path, ...]:
    return tuple(sorted(FIXTURE_DIR.glob("*.json")))


def load_case(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_v2_runtime(observation: object) -> tuple[int, dict[str, str]]:
    if not isinstance(observation, dict):
        raise AssertionError("observation must be a dictionary")
    actions = planner_v2_agent(observation, {}) or []
    return len(actions), dict(last_runtime_diagnostic_metadata())


class PlannerV2DaytonaLeakFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runtime_results = {}
        for path in fixture_paths():
            payload = load_case(path)
            cls.runtime_results[payload["case_id"]] = run_v2_runtime(
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
                self.assertEqual(payload["episode_steps"], 500)
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

                self.assertEqual(state.player_id, expected["player_id"])
                self.assertEqual(payload["turn"], expected["state_step"])
                self.assertEqual(len(owned), expected["owned_planet_count"])
                self.assertEqual(
                    sum(planet.production for planet in owned),
                    expected["owned_production"],
                )

    def test_current_v2_runtime_matches_expected_characterization(self) -> None:
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
                self.assertEqual(
                    metadata.get("runtime_diagnostic_selected_commitment_type", ""),
                    expected["selected_commitment_type"],
                )

    def test_extracted_collapse_windows_no_longer_starve_candidates(self) -> None:
        for path in fixture_paths():
            payload = load_case(path)
            if payload["case_id"] not in COLLAPSE_CASE_IDS:
                continue
            with self.subTest(case=payload["case_id"]):
                expected = payload["expected_current_v2_runtime"]
                self.assertGreater(expected["candidate_count"], 0)
                self.assertGreater(expected["evaluation_count"], 0)
                self.assertGreater(expected["action_count"], 0)
                self.assertEqual(expected["no_action_reason"], "actions_emitted")
                self.assertEqual(expected["selected_commitment_type"], "reserve_preserving")
                self.assertRegex(
                    expected["selection_notes"],
                    r"(urgent_defend|enemy_production_denial|leader_pressure)",
                )


if __name__ == "__main__":
    unittest.main()
