"""Characterization tests for compact V1 replay leak fixtures."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from agents.runtime_state import observation_to_game_state
from agents.runtime_turn import (
    last_runtime_diagnostic_metadata,
    safe_actions_for_observation,
)
from ow_planner.owned_threats import owned_production_threat_facts


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "v1_replay_leaks"

REQUIRED_EPISODES = {
    80999800,
    80979989,
    80987824,
    80991772,
    80986331,
    80989880,
    80984201,
    80981260,
    80982912,
    80979440,
}

REQUIRED_LEAK_CLASSES = {
    "owned_production_threat_unanswered",
    "own_transfer_spam",
    "enemy_denial_absent",
    "four_player_plateau",
    "thin_capture_recaptured",
}


def fixture_paths() -> tuple[Path, ...]:
    return tuple(sorted(FIXTURE_DIR.glob("*.json")))


def load_case(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_current_runtime(observation: object) -> tuple[int, dict[str, str]]:
    if not isinstance(observation, dict):
        raise AssertionError("observation must be a dictionary")
    actions = safe_actions_for_observation(observation, {})
    return len(actions), dict(last_runtime_diagnostic_metadata())


class V1ReplayLeakFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runtime_results = {}
        for path in fixture_paths():
            payload = load_case(path)
            cls.runtime_results[path.name] = run_current_runtime(
                payload["observation"],
            )

    def test_fixture_set_exists_and_covers_required_cases(self) -> None:
        paths = fixture_paths()

        self.assertEqual(len(paths), 10)
        self.assertEqual(
            {load_case(path)["episode_id"] for path in paths},
            REQUIRED_EPISODES,
        )
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
                self.assertEqual(payload["source_submission_ref"], 53894832)
                self.assertIn(payload["player_count"], (2, 4))

    def test_observations_parse_through_runtime_state_adapter(self) -> None:
        for path in fixture_paths():
            with self.subTest(path=path.name):
                payload = load_case(path)
                expected = payload["expected_current_runtime"]
                self.assertIsInstance(expected, dict)

                state = observation_to_game_state(payload["observation"])
                owned = [
                    planet for planet in state.planets if planet.owner == state.player_id
                ]

                self.assertEqual(state.player_id, expected["player_id"])
                self.assertEqual(state.step, expected["state_step"])
                self.assertEqual(len(owned), expected["owned_planet_count"])
                self.assertEqual(
                    sum(planet.production for planet in owned),
                    expected["owned_production"],
                )
                self.assertEqual(state.step, expected["state_step"])
                self.assertIsInstance(payload["turn"], int)

    def test_current_runtime_diagnostics_match_characterization(self) -> None:
        for path in fixture_paths():
            with self.subTest(path=path.name):
                payload = load_case(path)
                expected = payload["expected_current_runtime"]
                self.assertIsInstance(expected, dict)

                action_count, metadata = self.runtime_results[path.name]

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
                    metadata.get("runtime_diagnostic_selected_commitment_type"),
                    expected["selected_commitment_type"],
                )

    def test_no_action_cases_are_selector_rejections_not_parse_failures(self) -> None:
        no_action_cases = {
            "four_p_plateau_80981260_t060_p2.json",
            "four_p_plateau_80984201_t240_p0.json",
            "two_p_own_transfer_spam_80991772_t160_p0.json",
            "two_p_production_retention_80979989_t084_p1.json",
        }

        for path in fixture_paths():
            if path.name not in no_action_cases:
                continue
            with self.subTest(path=path.name):
                payload = load_case(path)
                expected = payload["expected_current_runtime"]

                self.assertEqual(expected["action_count"], 0)
                self.assertEqual(expected["diagnostic_status"], "no_action")
                self.assertEqual(
                    expected["no_action_reason"],
                    "strategy_selection_no_action",
                )
                self.assertGreater(expected["candidate_count"], 0)

    def test_two_player_pressure_spam_and_denial_fixtures_are_labeled_precisely(
        self,
    ) -> None:
        class_to_expected_count = {
            "owned_production_threat_unanswered": 3,
            "own_transfer_spam": 2,
            "enemy_denial_absent": 1,
        }

        for leak_class, expected_count in class_to_expected_count.items():
            cases = [
                load_case(path)
                for path in fixture_paths()
                if load_case(path)["leak_class"] == leak_class
            ]
            self.assertEqual(len(cases), expected_count)
            for payload in cases:
                with self.subTest(case=payload["case_id"]):
                    expected = payload["expected_current_runtime"]
                    self.assertEqual(payload["player_count"], 2)
                    self.assertGreaterEqual(expected["owned_production"], 12)
                    self.assertGreater(expected["candidate_count"], 0)

    def test_production_retention_fixtures_expose_owned_threat_facts(self) -> None:
        cases = [
            load_case(path)
            for path in fixture_paths()
            if load_case(path)["leak_class"] == "owned_production_threat_unanswered"
        ]

        self.assertEqual(len(cases), 3)
        for payload in cases:
            with self.subTest(case=payload["case_id"]):
                state = observation_to_game_state(payload["observation"])
                report = owned_production_threat_facts(state)

                self.assertGreater(report.production_pressure_count, 0)
                self.assertGreater(report.production_under_pressure, 0)
                self.assertIn("owned_production_pressure", report.labels)

    def test_four_player_plateau_and_capture_hold_fixtures_are_labeled_precisely(
        self,
    ) -> None:
        plateau_cases = [
            load_case(path)
            for path in fixture_paths()
            if load_case(path)["leak_class"] == "four_player_plateau"
        ]
        capture_hold_cases = [
            load_case(path)
            for path in fixture_paths()
            if load_case(path)["leak_class"] == "thin_capture_recaptured"
        ]

        self.assertEqual(len(plateau_cases), 3)
        self.assertEqual(len(capture_hold_cases), 1)
        for payload in (*plateau_cases, *capture_hold_cases):
            with self.subTest(case=payload["case_id"]):
                expected = payload["expected_current_runtime"]
                self.assertEqual(payload["player_count"], 4)
                self.assertGreater(expected["candidate_count"], 0)
                self.assertLessEqual(expected["owned_production"], 11)

    def test_action_emitting_leaks_preserve_current_commitment_characterization(
        self,
    ) -> None:
        for path in fixture_paths():
            payload = load_case(path)
            expected = payload["expected_current_runtime"]
            if expected["action_count"] == 0:
                continue
            with self.subTest(path=path.name):
                self.assertEqual(expected["diagnostic_status"], "actions")
                self.assertEqual(expected["no_action_reason"], "actions_emitted")
                self.assertEqual(
                    expected["selected_commitment_type"],
                    "reserve_preserving",
                )


if __name__ == "__main__":
    unittest.main()
