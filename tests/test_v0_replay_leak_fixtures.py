"""Characterization tests for V0 live replay leak fixtures."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from agents.runtime_config import runtime_turn_config_for_observation
from agents.runtime_state import observation_to_game_state
from agents.runtime_turn import (
    last_runtime_diagnostic_metadata,
    safe_actions_for_observation,
)


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "v0_replay_leaks"
REQUIRED_LEAK_CLASSES = {
    "four_player_no_action_candidate_starvation",
    "two_player_pressure_collapse",
    "two_player_idle_or_near_idle",
    "capture_hold_failure",
}
NO_ACTION_REASONS = {
    "no_candidates_generated",
    "strategy_selection_no_action",
    "budget_guard_budget_exhausted",
}


def fixture_paths() -> tuple[Path, ...]:
    return tuple(sorted(FIXTURE_DIR.glob("*.json")))


def load_case(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_current_runtime(
    observation: dict[str, object],
    runtime_mode: str,
) -> tuple[int, dict[str, str]]:
    if runtime_mode == "bounded":
        config = runtime_turn_config_for_observation(observation, {})
        actions = safe_actions_for_observation(observation, {}, config)
    elif runtime_mode == "direct":
        actions = safe_actions_for_observation(observation, {})
    else:
        raise AssertionError(f"unexpected runtime mode: {runtime_mode}")
    return len(actions), dict(last_runtime_diagnostic_metadata())


class V0ReplayLeakFixtureTests(unittest.TestCase):
    def test_expected_fixture_set_exists(self) -> None:
        self.assertEqual(
            tuple(path.name for path in fixture_paths()),
            (
                "four_p_no_action_80761836_t100_p2.json",
                "four_p_no_action_80766287_t000_p2.json",
                "two_p_capture_hold_80763852_t125_p1.json",
                "two_p_capture_hold_80763852_t131_p1.json",
                "two_p_idle_80768833_t000_p1.json",
                "two_p_pressure_80756891_t060_p0.json",
                "two_p_pressure_80760443_t100_p0.json",
            ),
        )

    def test_fixtures_are_single_observation_cases_not_full_replays(self) -> None:
        for path in fixture_paths():
            with self.subTest(path=path.name):
                payload = load_case(path)

                self.assertIn("observation", payload)
                self.assertIn("expected_current_runtime", payload)
                self.assertNotIn("steps", payload)
                self.assertNotIn("statuses", payload)
                self.assertNotIn("rewards", payload)
                expected_text = json.dumps(payload, sort_keys=True, indent=2) + "\n"
                self.assertEqual(path.read_text(encoding="utf-8"), expected_text)

    def test_all_fixtures_parse_through_runtime_state_adapter(self) -> None:
        seen_classes = set()
        for path in fixture_paths():
            with self.subTest(path=path.name):
                payload = load_case(path)
                observation = payload["observation"]
                self.assertIsInstance(observation, dict)

                state = observation_to_game_state(observation)
                expected = payload["expected_current_runtime"]
                self.assertIsInstance(expected, dict)

                owned = [planet for planet in state.planets if planet.owner == state.player_id]
                self.assertEqual(state.player_id, expected["player_id"])
                self.assertEqual(state.step, expected["state_step"])
                self.assertEqual(len(owned), expected["owned_planet_count"])
                self.assertEqual(
                    sum(planet.production for planet in owned),
                    expected["owned_production"],
                )
                self.assertEqual(payload["player_count"], 2 if state.player_id < 2 else 4)
                seen_classes.add(payload["leak_class"])

        self.assertEqual(seen_classes, REQUIRED_LEAK_CLASSES)

    def test_four_player_t0_fixture_can_remain_true_no_candidate_no_action(self) -> None:
        payload = load_case(FIXTURE_DIR / "four_p_no_action_80766287_t000_p2.json")
        observation = payload["observation"]
        self.assertIsInstance(observation, dict)

        action_count, metadata = run_current_runtime(observation, "direct")

        self.assertEqual(action_count, 0)
        self.assertEqual(metadata["runtime_diagnostic_status"], "no_action")
        self.assertEqual(
            metadata["runtime_diagnostic_no_action_reason"],
            "no_candidates_generated",
        )
        self.assertEqual(metadata["runtime_diagnostic_candidate_count"], "0")

    def test_four_player_t100_fixture_no_longer_starves_candidate_generation(self) -> None:
        payload = load_case(FIXTURE_DIR / "four_p_no_action_80761836_t100_p2.json")
        observation = payload["observation"]
        self.assertIsInstance(observation, dict)

        actions = safe_actions_for_observation(observation, {})
        metadata = dict(last_runtime_diagnostic_metadata())

        self.assertGreater(len(actions), 0)
        self.assertEqual(len(actions[0]), 3)
        self.assertIsInstance(actions[0][0], int)
        self.assertIsInstance(actions[0][1], float)
        self.assertIsInstance(actions[0][2], int)
        self.assertEqual(metadata["runtime_diagnostic_status"], "actions")
        self.assertNotEqual(
            metadata["runtime_diagnostic_no_action_reason"],
            "no_candidates_generated",
        )
        self.assertNotEqual(
            metadata["runtime_diagnostic_no_action_reason"],
            "strategy_selection_no_action",
        )
        self.assertEqual(
            metadata["runtime_diagnostic_no_action_reason"],
            "actions_emitted",
        )
        self.assertGreater(int(metadata["runtime_diagnostic_candidate_count"]), 0)

    def test_current_runtime_diagnostics_match_committed_characterization(self) -> None:
        for path in fixture_paths():
            with self.subTest(path=path.name):
                payload = load_case(path)
                observation = payload["observation"]
                expected = payload["expected_current_runtime"]
                self.assertIsInstance(observation, dict)
                self.assertIsInstance(expected, dict)

                action_count, metadata = run_current_runtime(
                    observation,
                    str(expected["runtime_mode"]),
                )

                self.assertEqual(action_count, expected["action_count"])
                self.assertEqual(
                    metadata["runtime_diagnostic_status"],
                    expected["diagnostic_status"],
                )
                self.assertEqual(
                    metadata["runtime_diagnostic_no_action_reason"],
                    expected["no_action_reason"],
                )

    def test_pressure_idle_and_capture_fixtures_expose_later_cycle_metadata(self) -> None:
        for path in fixture_paths():
            payload = load_case(path)
            if payload["leak_class"] == "four_player_no_action_candidate_starvation":
                continue
            with self.subTest(path=path.name):
                expected = payload["expected_current_runtime"]
                self.assertIsInstance(expected, dict)

                self.assertIn(payload["player_count"], (2, 4))
                self.assertIsInstance(payload["turn"], int)
                self.assertIn("player_id", expected)
                self.assertIn("owned_planet_count", expected)
                self.assertIn("owned_production", expected)
                self.assertIn("action_count", expected)
                self.assertIn("diagnostic_status", expected)
                self.assertIn("no_action_reason", expected)
                self.assertGreaterEqual(expected["owned_planet_count"], 1)
                self.assertGreaterEqual(expected["owned_production"], 1)
                self.assertIn(expected["no_action_reason"], NO_ACTION_REASONS | {"actions_emitted"})


if __name__ == "__main__":
    unittest.main()
