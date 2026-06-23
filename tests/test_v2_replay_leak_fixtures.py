"""Characterization tests for compact V2 replay leak fixtures."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from agents.runtime_actions import planner_result_to_actions
from agents.runtime_planner import (
    PLANNER_VERSION_V2,
    RuntimePlannerConfig,
    run_planner_pipeline,
)
from agents.runtime_state import observation_to_game_state
from agents.runtime_turn import (
    last_runtime_diagnostic_metadata,
    safe_actions_for_observation,
)
from ow_planner_v2 import planner_v2_diagnostics


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "v2_replay_leaks"

REQUIRED_EPISODES = {
    81217550,
    81216397,
    81225543,
    81221061,
    81218141,
    81214883,
}

REQUIRED_LEAK_CLASSES = {
    "four_player_action_starvation",
    "four_player_plateau",
    "two_player_action_starvation",
    "hold_defense_failure",
    "own_transfer_spam",
    "late_enemy_denial_absent",
}


def fixture_paths() -> tuple[Path, ...]:
    return tuple(sorted(FIXTURE_DIR.glob("*.json")))


def load_case(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def action_summary(actions: list[list[object]]) -> list[str]:
    return ["|".join(map(str, action)) for action in actions[:5]]


class V2ReplayLeakFixtureTests(unittest.TestCase):
    def test_fixture_set_exists_and_covers_required_cases(self) -> None:
        paths = fixture_paths()

        self.assertEqual(len(paths), 6)
        self.assertEqual({load_case(path)["episode_id"] for path in paths}, REQUIRED_EPISODES)
        self.assertEqual(
            {load_case(path)["leak_class"] for path in paths},
            REQUIRED_LEAK_CLASSES,
        )

    def test_fixtures_are_compact_single_observation_cases(self) -> None:
        for path in fixture_paths():
            with self.subTest(path=path.name):
                payload = load_case(path)

                self.assertIsInstance(payload, dict)
                self.assertNotIn("steps", payload)
                self.assertIn("observation", payload)
                self.assertIsInstance(payload["observation"], dict)
                self.assertEqual(payload["source_submission_ref"], 53925932)
                self.assertIn(payload["player_count"], (2, 4))

    def test_current_runtime_characterization_matches_fixture(self) -> None:
        for path in fixture_paths():
            with self.subTest(path=path.name):
                payload = load_case(path)
                expected = payload["expected_current_runtime"]
                self.assertIsInstance(expected, dict)
                observation = payload["observation"]
                self.assertIsInstance(observation, dict)

                state = observation_to_game_state(observation)
                owned = tuple(
                    planet for planet in state.planets if planet.owner == state.player_id
                )
                actions = safe_actions_for_observation(observation, {})
                metadata = dict(last_runtime_diagnostic_metadata())

                self.assertEqual(state.player_id, expected["player_id"])
                self.assertEqual(len(owned), expected["owned_planet_count"])
                self.assertEqual(
                    sum(planet.production for planet in owned),
                    expected["owned_production"],
                )
                self.assertEqual(len(actions), expected["action_count"])
                self.assertEqual(action_summary(actions), expected["action_summary"])
                self.assertEqual(
                    int(metadata["runtime_diagnostic_candidate_count"]),
                    expected["candidate_count"],
                )
                self.assertEqual(
                    metadata["runtime_diagnostic_status"],
                    expected["diagnostic_status"],
                )
                self.assertEqual(
                    metadata["runtime_diagnostic_no_action_reason"],
                    expected["no_action_reason"],
                )

    def test_opt_in_planner_v2_characterization_matches_fixture(self) -> None:
        for path in fixture_paths():
            with self.subTest(path=path.name):
                payload = load_case(path)
                expected = payload["expected_planner_v2"]
                self.assertIsInstance(expected, dict)
                observation = payload["observation"]
                self.assertIsInstance(observation, dict)
                state = observation_to_game_state(observation)

                result = run_planner_pipeline(
                    state,
                    RuntimePlannerConfig(planner_version=PLANNER_VERSION_V2),
                )
                actions = planner_result_to_actions(result)
                self.assertIsNotNone(result.v2_result)
                diagnostics = planner_v2_diagnostics(result.v2_result)

                self.assertEqual(len(actions), expected["action_count"])
                self.assertEqual(action_summary(actions), expected["action_summary"])
                self.assertEqual(
                    diagnostics["planner_v2_mission_count"],
                    expected["mission_count"],
                )
                self.assertEqual(
                    diagnostics["planner_v2_action_set_count"],
                    expected["action_set_count"],
                )
                self.assertEqual(
                    diagnostics["planner_v2_selected_family"],
                    expected["selected_family"],
                )
                self.assertEqual(
                    diagnostics["planner_v2_no_action_reason"],
                    expected["no_action_reason"],
                )


if __name__ == "__main__":
    unittest.main()
