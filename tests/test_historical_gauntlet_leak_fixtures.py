"""Characterization tests for compact historical gauntlet leak fixtures."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from agents.orbit_wars_agent import agent
from agents.runtime_state import observation_to_game_state
from agents.runtime_turn import (
    last_runtime_diagnostic_metadata,
    safe_actions_for_observation,
)


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "historical_gauntlet_leaks"

REQUIRED_SCENARIO_LABELS = {
    "historical-gauntlet-2p-500-seat-1-vs-claude-v31-race-awareness",
    "historical-gauntlet-2p-500-seat-1-vs-claude-v9-hold-aware-capture",
    "historical-gauntlet-2p-500-seat-0-vs-ow2-current-main",
    "historical-gauntlet-4p-500-top-score-seat-3",
    "historical-gauntlet-4p-500-mixed-style-seat-2",
    "historical-gauntlet-4p-500-ow2-smoke-reference-seat-0",
}

REQUIRED_FIX_CATEGORIES = {
    "2P early production/candidate-starvation collapse",
    "2P non-Claude control pressure",
    "4P top-score plateau/no-action pressure",
    "4P budget-guard-heavy long-game pressure",
    "4P strategy-selection/no-action pressure",
}

TWO_PLAYER_EARLY_COLLAPSE_TARGETS = {
    "two_p_collapse_claude_v31_t002_p1.json",
    "two_p_collapse_claude_v9_t001_p1.json",
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


class HistoricalGauntletLeakFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runtime_results = {}
        for path in fixture_paths():
            payload = load_case(path)
            cls.runtime_results[path.name] = run_current_runtime(
                payload["observation"],
            )

    def test_fixture_set_exists_and_covers_cycle_12_candidates(self) -> None:
        paths = fixture_paths()

        self.assertEqual(len(paths), 6)
        self.assertEqual(
            {load_case(path)["scenario_label"] for path in paths},
            REQUIRED_SCENARIO_LABELS,
        )
        self.assertEqual(
            {load_case(path)["future_fix_category"] for path in paths},
            REQUIRED_FIX_CATEGORIES,
        )

    def test_fixtures_are_compact_single_observation_cases(self) -> None:
        for path in fixture_paths():
            with self.subTest(path=path.name):
                payload = load_case(path)

                self.assertIsInstance(payload, dict)
                self.assertNotIn("steps", payload)
                self.assertIn("observation", payload)
                self.assertIsInstance(payload["observation"], dict)
                self.assertNotIn("steps", payload["observation"])
                self.assertIn(payload["player_count"], (2, 4))
                self.assertEqual(payload["episode_steps"], 500)
                self.assertEqual(payload["source_segment"], "distributed_historical_champion_gauntlet")
                self.assertEqual(payload["source_cycle"], 13)
                self.assertRegex(
                    payload["shard_id"],
                    r"^historical-gauntlet-shard-00[0-5]$",
                )
                self.assertTrue(
                    str(payload["source_replay_path"]).startswith(
                        "/tmp/ow-historical-gauntlet-cycle13-artifacts/",
                    ),
                )

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
                self.assertEqual(state.step, payload["turn"])

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
                    int(metadata["runtime_diagnostic_evaluation_count"]),
                    expected["evaluation_count"],
                )
                self.assertEqual(
                    metadata.get("runtime_diagnostic_selected_commitment_type"),
                    expected["selected_commitment_type"],
                )

    def test_two_player_collapse_fixtures_recover_bounded_candidates(self) -> None:
        cases = [
            load_case(path)
            for path in fixture_paths()
            if str(load_case(path)["leak_class"]).startswith("two_player")
        ]

        self.assertEqual(len(cases), 3)
        for payload in cases:
            with self.subTest(case=payload["case_id"]):
                expected = payload["expected_current_runtime"]
                self.assertEqual(payload["player_count"], 2)
                self.assertEqual(expected["action_count"], 0)
                self.assertGreater(expected["candidate_count"], 0)
                self.assertEqual(
                    expected["no_action_reason"],
                    "strategy_selection_no_action",
                )
                self.assertRegex(
                    payload["source_match_summary"]["runtime_no_action_reasons"],
                    r"no_candidates_generated:\d+",
                )

    def test_target_two_player_early_collapse_fixtures_emit_runtime_actions(
        self,
    ) -> None:
        for fixture_name in TWO_PLAYER_EARLY_COLLAPSE_TARGETS:
            with self.subTest(fixture_name=fixture_name):
                payload = load_case(FIXTURE_DIR / fixture_name)

                actions = agent(payload["observation"], {})
                metadata = dict(last_runtime_diagnostic_metadata())

                self.assertGreater(len(actions), 0)
                self.assertEqual(
                    metadata["runtime_diagnostic_status"],
                    "actions",
                )
                self.assertEqual(
                    metadata["runtime_diagnostic_no_action_reason"],
                    "actions_emitted",
                )
                self.assertGreater(
                    int(metadata["runtime_diagnostic_candidate_count"]),
                    0,
                )
                self.assertEqual(
                    metadata.get("runtime_diagnostic_selected_commitment_type"),
                    "reserve_preserving",
                )

    def test_four_player_fixtures_cover_plateau_budget_and_strategy_pressure(
        self,
    ) -> None:
        cases_by_class = {
            load_case(path)["leak_class"]: load_case(path)
            for path in fixture_paths()
            if load_case(path)["player_count"] == 4
        }

        self.assertEqual(
            set(cases_by_class),
            {
                "four_player_plateau_no_action_pressure",
                "four_player_budget_guard_heavy_pressure",
                "four_player_strategy_selection_pressure",
            },
        )

        plateau = cases_by_class["four_player_plateau_no_action_pressure"]
        self.assertEqual(
            plateau["expected_current_runtime"]["no_action_reason"],
            "strategy_selection_no_action",
        )
        self.assertGreater(plateau["expected_current_runtime"]["candidate_count"], 0)

        budget = cases_by_class["four_player_budget_guard_heavy_pressure"]
        self.assertIn(
            "budget_guard_budget_exhausted",
            budget["source_match_summary"]["runtime_no_action_reasons"],
        )
        self.assertEqual(
            budget["expected_current_runtime"]["no_action_reason"],
            "no_candidates_generated",
        )

        strategy = cases_by_class["four_player_strategy_selection_pressure"]
        self.assertRegex(
            strategy["source_match_summary"]["runtime_no_action_reasons"],
            r"strategy_selection_(no_action|rejected):\d+",
        )
        self.assertEqual(
            strategy["expected_current_runtime"]["no_action_reason"],
            "no_candidates_generated",
        )

    def test_source_metadata_labels_are_stable_and_full_horizon(self) -> None:
        label_pattern = re.compile(r"^historical-gauntlet-.+-500-.+")
        for path in fixture_paths():
            with self.subTest(path=path.name):
                payload = load_case(path)

                self.assertRegex(payload["scenario_label"], label_pattern)
                self.assertEqual(payload["episode_steps"], 500)
                self.assertEqual(
                    payload["source_match_summary"]["status"],
                    "completed",
                )
                self.assertGreater(
                    payload["source_match_summary"]["runtime_no_action_turn_count"],
                    0,
                )
                self.assertGreaterEqual(
                    payload["source_match_summary"]["runtime_action_turn_count"],
                    0,
                )


if __name__ == "__main__":
    unittest.main()
