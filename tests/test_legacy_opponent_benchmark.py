"""Tests for the bounded legacy-opponent smoke benchmark manifest."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from ow_eval import (
    AgentSourceKind,
    EvaluationBatchResult,
    ExperimentManifest,
    ExperimentRunResult,
    PlannerAnalysisPack,
    PlayerCount,
    ScoreboardRecord,
    manifest_to_match_configs,
    run_evaluation_experiment,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "experiments" / "manifests" / "legacy-opponent-smoke.json"
HISTORICAL_ROOTS = (
    Path("/Users/user/dev/hackathons/orbit-wars"),
    Path("/Users/user/dev/hackathons/orbit-wars-2"),
    Path("/Users/user/dev/hackathons/orbit-wars-claude"),
)


def load_manifest() -> ExperimentManifest:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return ExperimentManifest.from_dict(payload)


def fake_run_result(manifest: ExperimentManifest) -> ExperimentRunResult:
    match_count = len(manifest.scenarios)
    record = ScoreboardRecord(
        agent_name=manifest.candidate_agent.name,
        agent_version=manifest.version,
        commit=None,
        scenario_set=manifest.name,
        match_count=match_count,
        completed_count=match_count,
        win_count=0,
        loss_count=match_count,
        error_count=0,
        win_rate=0.0 if match_count else None,
        error_rate=0.0 if match_count else None,
        mean_rank=2.0 if match_count else None,
        mean_score=0.0 if match_count else None,
    )
    return ExperimentRunResult(
        manifest=manifest,
        matches=manifest_to_match_configs(manifest),
        batch_result=EvaluationBatchResult(),
        scoreboard_record=record,
        analysis_pack=PlannerAnalysisPack(total_results=match_count),
        summary_text=(
            f"experiment={manifest.name} matches={match_count} "
            f"completed={match_count} errors=0 win_rate=0 mean_rank=2 "
            "analysis_items=0"
        ),
    )


class LegacyOpponentBenchmarkTests(unittest.TestCase):
    def test_manifest_exists_and_round_trips_deterministically(self) -> None:
        self.assertTrue(MANIFEST_PATH.is_file())

        manifest = load_manifest()
        expected_text = json.dumps(manifest.to_dict(), sort_keys=True, indent=2) + "\n"

        self.assertEqual(MANIFEST_PATH.read_text(encoding="utf-8"), expected_text)
        self.assertEqual(ExperimentManifest.from_dict(json.loads(expected_text)), manifest)

    def test_all_scenarios_are_explicitly_episode_bounded(self) -> None:
        for scenario in load_manifest().scenarios:
            with self.subTest(label=scenario.label):
                metadata = dict(scenario.metadata)

                self.assertEqual(metadata.get("episode_steps"), "5")
                self.assertGreater(int(metadata["episode_steps"]), 0)

    def test_historical_opponents_are_existing_python_files(self) -> None:
        manifest = load_manifest()

        self.assertEqual(manifest.candidate_agent.source_kind, AgentSourceKind.MODULAR_AGENT)
        self.assertEqual(manifest.candidate_agent.module_path, "agents.orbit_wars_agent")
        for scenario in manifest.scenarios:
            with self.subTest(label=scenario.label):
                self.assertEqual(scenario.player_count, PlayerCount.TWO_PLAYER)
                self.assertEqual(len(scenario.opponent_agents), 1)
                opponent = scenario.opponent_agents[0].agent
                file_path = Path(opponent.file_path or "")

                self.assertEqual(opponent.source_kind, AgentSourceKind.PYTHON_FILE)
                self.assertTrue(file_path.is_file())
                self.assertTrue(
                    any(file_path.is_relative_to(root) for root in HISTORICAL_ROOTS),
                    str(file_path),
                )

    def test_manifest_expands_to_valid_match_configs(self) -> None:
        matches = manifest_to_match_configs(load_manifest())

        self.assertEqual(
            tuple(match.label for match in matches),
            (
                "legacy-2p-seed-17-seat-0-vs-ow2-current-main",
                "legacy-2p-seed-18-seat-0-vs-ow2-v11",
                "legacy-2p-seed-19-seat-0-vs-claude-v62",
                "legacy-2p-seed-20-seat-0-vs-claude-main",
            ),
        )
        self.assertEqual(tuple(match.seed for match in matches), (17, 18, 19, 20))
        self.assertTrue(all(match.player_count is PlayerCount.TWO_PLAYER for match in matches))
        self.assertTrue(
            all(dict(match.metadata).get("episode_steps") == "5" for match in matches)
        )

    def test_cli_compatibility_writes_no_report_by_default(self) -> None:
        seen_manifest_names: list[str] = []

        def fake_runner(
            manifest: ExperimentManifest,
            config: object | None = None,
        ) -> ExperimentRunResult:
            _ = config
            seen_manifest_names.append(manifest.name)
            return fake_run_result(manifest)

        with patch(
            "ow_eval.experiment_cli.run_experiment_manifest",
            side_effect=fake_runner,
        ):
            result = run_evaluation_experiment(MANIFEST_PATH)

        self.assertEqual(result.exit_code, 0)
        self.assertIsNone(result.report_path)
        self.assertEqual(seen_manifest_names, ["legacy-opponent-smoke"])


if __name__ == "__main__":
    unittest.main()
