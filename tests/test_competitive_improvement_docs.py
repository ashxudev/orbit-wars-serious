"""Guardrails for the competitive-improvement baseline pack."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from ow_eval import (
    AgentSourceKind,
    ExperimentManifest,
    PlayerCount,
    available_builtin_baselines,
    manifest_to_match_configs,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "experiments" / "manifests" / "competitive-baseline-smoke.json"
RUNBOOK_PATH = REPO_ROOT / "docs" / "competitive-improvement.md"
BASELINE_COMMAND = (
    ".venv/bin/python scripts/run_evaluation_experiment.py "
    "experiments/manifests/competitive-baseline-smoke.json "
    "--report-output /tmp/ow-competitive-baseline-report.json"
)


def load_manifest() -> ExperimentManifest:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return ExperimentManifest.from_dict(payload)


class CompetitiveImprovementDocsTests(unittest.TestCase):
    def test_baseline_manifest_and_runbook_exist(self) -> None:
        self.assertTrue(MANIFEST_PATH.is_file())
        self.assertTrue(RUNBOOK_PATH.is_file())

    def test_baseline_manifest_round_trips_deterministically(self) -> None:
        manifest = load_manifest()
        expected_text = json.dumps(manifest.to_dict(), sort_keys=True, indent=2) + "\n"

        self.assertEqual(MANIFEST_PATH.read_text(encoding="utf-8"), expected_text)
        self.assertEqual(ExperimentManifest.from_dict(json.loads(expected_text)), manifest)

    def test_baseline_manifest_uses_current_runtime_agent(self) -> None:
        manifest = load_manifest()

        self.assertEqual(manifest.name, "competitive-baseline-smoke")
        self.assertEqual(manifest.candidate_agent.name, "orbit-wars-runtime")
        self.assertEqual(
            manifest.candidate_agent.source_kind,
            AgentSourceKind.MODULAR_AGENT,
        )
        self.assertEqual(
            manifest.candidate_agent.module_path,
            "agents.orbit_wars_agent",
        )

    def test_baseline_manifest_covers_two_and_four_player_scenarios(self) -> None:
        matches = manifest_to_match_configs(load_manifest())

        self.assertEqual(len(matches), 6)
        self.assertEqual(
            tuple(match.player_count for match in matches),
            (
                PlayerCount.TWO_PLAYER,
                PlayerCount.TWO_PLAYER,
                PlayerCount.TWO_PLAYER,
                PlayerCount.FOUR_PLAYER,
                PlayerCount.FOUR_PLAYER,
                PlayerCount.FOUR_PLAYER,
            ),
        )
        self.assertEqual(tuple(match.seed for match in matches), (7, 8, 9, 7, 8, 9))
        self.assertEqual(tuple(len(match.opponent_agents) for match in matches), (1, 1, 1, 3, 3, 3))
        self.assertTrue(
            all(dict(match.metadata).get("episode_steps") == "5" for match in matches)
        )

    def test_baseline_manifest_uses_only_supported_builtin_opponents(self) -> None:
        supported_baselines = set(available_builtin_baselines())

        for scenario in load_manifest().scenarios:
            for opponent in scenario.opponent_agents:
                self.assertEqual(
                    opponent.agent.source_kind,
                    AgentSourceKind.BUILTIN_BASELINE,
                )
                self.assertIn(
                    dict(opponent.agent.metadata).get("baseline"),
                    supported_baselines,
                )

    def test_baseline_manifest_has_explicit_conservative_thresholds(self) -> None:
        manifest = load_manifest()
        thresholds = manifest.promotion_thresholds

        self.assertEqual(thresholds.min_win_rate, 0.0)
        self.assertEqual(thresholds.max_error_rate, 0.0)
        self.assertEqual(thresholds.max_mean_rank, 4.0)
        self.assertEqual(thresholds.min_completed_count, len(manifest.scenarios))

    def test_runbook_documents_baseline_purpose_command_and_output_policy(self) -> None:
        text = RUNBOOK_PATH.read_text(encoding="utf-8")
        lower_text = text.lower()

        self.assertIn("measure current strength before changing strategy", lower_text)
        self.assertIn("local evaluation only", lower_text)
        self.assertIn("does not submit to live kaggle", lower_text)
        self.assertIn("bounded 5-step benchmark", lower_text)
        self.assertIn(BASELINE_COMMAND, text)
        self.assertIn("/tmp/ow-competitive-baseline-report.json", text)
        self.assertIn("generated reports", lower_text)
        self.assertIn("should not be committed", lower_text)


if __name__ == "__main__":
    unittest.main()
