"""Tests for package compatibility of historical champion gauntlet shards."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ow_eval import ExperimentManifest
from ow_eval import build_daytona_shard_job_plan
from ow_eval.historical_gauntlet_shards import (
    build_historical_champion_evaluation_shard_plan,
    build_historical_champion_shard_plan,
    select_historical_champion_shard,
    write_historical_champion_probe_shard_package,
)
from ow_eval.shard_jobs import EvaluationShardJobPackageResult
from ow_eval.shard_manifests import shard_to_experiment_manifest


class HistoricalChampionGauntletPackageTests(unittest.TestCase):
    def test_recommended_shard_is_selected_deterministically(self) -> None:
        plan = build_historical_champion_shard_plan()
        shard = select_historical_champion_shard(plan)

        self.assertEqual(shard.shard_id, "historical-gauntlet-shard-000")
        self.assertTrue(shard.recommended_for_probe)
        self.assertEqual(shard.scenario_count, 5)
        self.assertEqual(len(shard.scenarios), 5)

    def test_unknown_shard_is_rejected(self) -> None:
        plan = build_historical_champion_shard_plan()

        with self.assertRaisesRegex(ValueError, "unknown historical champion shard id"):
            select_historical_champion_shard(plan, "missing-shard")

    def test_recommended_shard_converts_to_existing_evaluation_shard_plan(self) -> None:
        historical_plan = build_historical_champion_shard_plan()
        historical_shard = select_historical_champion_shard(historical_plan)
        evaluation_plan = build_historical_champion_evaluation_shard_plan(
            historical_plan,
            output_root="/tmp/ow-historical-gauntlet-package-test",
        )
        evaluation_shard = evaluation_plan.shards[0]

        self.assertEqual(evaluation_plan.total_matches, historical_shard.scenario_count)
        self.assertEqual(evaluation_shard.shard_id, historical_shard.shard_id)
        self.assertEqual(evaluation_shard.label, historical_shard.shard_id)
        self.assertEqual(evaluation_shard.match_count, historical_shard.scenario_count)
        self.assertEqual(
            evaluation_shard.match_labels,
            tuple(scenario.scenario_label for scenario in historical_shard.scenarios),
        )
        self.assertEqual(
            evaluation_shard.seeds,
            tuple(scenario.seed for scenario in historical_shard.scenarios),
        )
        self.assertIn("scripts/run_evaluation_experiment.py", evaluation_shard.command)
        self.assertIn("--report-output", evaluation_shard.command)

    def test_converted_manifest_preserves_full_horizon_scenarios(self) -> None:
        evaluation_plan = build_historical_champion_evaluation_shard_plan(
            output_root="/tmp/ow-historical-gauntlet-package-test",
        )
        manifest = shard_to_experiment_manifest(evaluation_plan.shards[0])

        self.assertIsInstance(manifest, ExperimentManifest)
        self.assertEqual(len(manifest.scenarios), 5)
        self.assertEqual(dict(manifest.metadata)["shard_id"], "historical-gauntlet-shard-000")
        for scenario in manifest.scenarios:
            with self.subTest(label=scenario.label):
                self.assertEqual(dict(scenario.metadata).get("episode_steps"), "500")
                self.assertTrue(scenario.label)
                self.assertTrue(scenario.opponent_agents)

    def test_probe_shard_package_writes_only_package_specs_under_output_root(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ow-historical-gauntlet-package-") as tmp:
            output_root = Path(tmp)
            result = write_historical_champion_probe_shard_package(output_root)

            self.assertIsInstance(result, EvaluationShardJobPackageResult)
            self.assertEqual(result.summary_text.split()[0], "shard_jobs=WRITTEN")
            self.assertEqual(len(result.jobs), 1)
            self.assertEqual(len(result.manifest_paths), 1)
            self.assertEqual(len(result.job_paths), 1)
            self.assertTrue(Path(result.index_path).is_file())

            job = result.jobs[0]
            self.assertEqual(job.shard_id, "historical-gauntlet-shard-000")
            self.assertEqual(job.label, "historical-gauntlet-shard-000")
            self.assertEqual(len(job.match_labels), 5)
            self.assertTrue(Path(job.manifest_path).is_file())
            self.assertTrue(Path(job.job_path).is_file())
            self.assertTrue(Path(job.shard_result_path).parent.is_dir())
            self.assertTrue(str(Path(job.manifest_path)).startswith(str(output_root)))
            self.assertTrue(str(Path(job.job_path)).startswith(str(output_root)))
            self.assertTrue(str(Path(result.index_path)).startswith(str(output_root)))
            self.assertTrue(job.extra_upload_paths)
            for upload_path in job.extra_upload_paths:
                with self.subTest(upload_path=upload_path):
                    self.assertTrue(Path(upload_path).is_file())
                    self.assertTrue(str(Path(upload_path)).startswith(str(output_root)))
                    self.assertIn("agent_files", Path(upload_path).parts)

            manifest_payload = json.loads(Path(job.manifest_path).read_text(encoding="utf-8"))
            manifest = ExperimentManifest.from_dict(manifest_payload)
            self.assertEqual(len(manifest.scenarios), 5)
            self.assertEqual(
                {dict(scenario.metadata).get("episode_steps") for scenario in manifest.scenarios},
                {"500"},
            )
            file_paths = [
                opponent["agent"]["file_path"]
                for scenario in manifest_payload["scenarios"]
                for opponent in scenario["opponent_agents"]
                if opponent["agent"]["source_kind"] == "python_file"
            ]
            self.assertTrue(file_paths)
            self.assertEqual(set(file_paths), set(job.extra_upload_paths))
            for file_path in file_paths:
                with self.subTest(file_path=file_path):
                    self.assertTrue(str(Path(file_path)).startswith(str(output_root)))

            job_payload = json.loads(Path(job.job_path).read_text(encoding="utf-8"))
            self.assertEqual(job_payload["shard_id"], "historical-gauntlet-shard-000")
            self.assertEqual(job_payload["extra_upload_paths"], list(job.extra_upload_paths))
            daytona_plan = build_daytona_shard_job_plan(result.index_path)
            self.assertEqual(
                set(daytona_plan.specs[0].expected_upload_paths),
                {job.job_path, job.manifest_path, *job.extra_upload_paths},
            )
            serialized_package = json.dumps(result.to_dict(), sort_keys=True)
            for term in ("replay_path", "scoreboard_record", "daytona_job_id", "credentials"):
                self.assertNotIn(term, serialized_package)


if __name__ == "__main__":
    unittest.main()
