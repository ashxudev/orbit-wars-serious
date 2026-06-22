"""Tests for package compatibility of historical champion gauntlet shards."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ow_eval import ExperimentManifest
from ow_eval import build_daytona_shard_job_plan
from ow_eval.historical_gauntlet_shards import (
    build_historical_champion_evaluation_shard_plan,
    build_historical_champion_full_evaluation_shard_plan,
    build_historical_champion_shard_plan,
    select_historical_champion_shard,
    write_historical_champion_full_shard_package,
    write_historical_champion_probe_shard_package,
)
from ow_eval.shard_jobs import EvaluationShardJobPackageResult
from ow_eval.shard_manifests import shard_to_experiment_manifest

REPO_ROOT = Path(__file__).resolve().parents[1]


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

    def test_probe_shard_package_uses_committed_historical_paths_by_default(self) -> None:
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
            self.assertEqual(job.extra_upload_paths, ())

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
            for file_path in file_paths:
                with self.subTest(file_path=file_path):
                    path = Path(file_path)
                    self.assertFalse(path.is_absolute(), file_path)
                    self.assertTrue((REPO_ROOT / path).is_file())
                    self.assertTrue(path.is_relative_to("historical_opponents/agents"))

            job_payload = json.loads(Path(job.job_path).read_text(encoding="utf-8"))
            self.assertEqual(job_payload["shard_id"], "historical-gauntlet-shard-000")
            self.assertEqual(job_payload["extra_upload_paths"], list(job.extra_upload_paths))
            daytona_plan = build_daytona_shard_job_plan(result.index_path)
            self.assertEqual(
                set(daytona_plan.specs[0].expected_upload_paths),
                {job.job_path, job.manifest_path},
            )
            serialized_package = json.dumps(result.to_dict(), sort_keys=True)
            for term in ("replay_path", "scoreboard_record", "daytona_job_id", "credentials"):
                self.assertNotIn(term, serialized_package)

    def test_probe_package_rejects_skipping_manifest_materialization(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ow-historical-gauntlet-package-") as tmp:
            with self.assertRaisesRegex(
                ValueError,
                "require materialized manifests",
            ):
                write_historical_champion_probe_shard_package(
                    tmp,
                    materialize_manifests=False,
                )

    def test_probe_shard_package_can_materialize_local_python_file_fallback(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ow-historical-gauntlet-package-") as tmp:
            output_root = Path(tmp)
            result = write_historical_champion_probe_shard_package(
                output_root,
                package_historical_python_files=True,
            )
            job = result.jobs[0]

            self.assertTrue(job.extra_upload_paths)
            for upload_path in job.extra_upload_paths:
                with self.subTest(upload_path=upload_path):
                    self.assertTrue(Path(upload_path).is_file())
                    self.assertTrue(str(Path(upload_path)).startswith(str(output_root)))
                    self.assertIn("agent_files", Path(upload_path).parts)

            manifest_payload = json.loads(Path(job.manifest_path).read_text(encoding="utf-8"))
            file_paths = [
                opponent["agent"]["file_path"]
                for scenario in manifest_payload["scenarios"]
                for opponent in scenario["opponent_agents"]
                if opponent["agent"]["source_kind"] == "python_file"
            ]
            self.assertEqual(set(file_paths), set(job.extra_upload_paths))

    def test_full_gauntlet_converts_all_shards_to_existing_evaluation_plan(self) -> None:
        historical_plan = build_historical_champion_shard_plan()
        evaluation_plan = build_historical_champion_full_evaluation_shard_plan(
            historical_plan,
            output_root="/tmp/ow-historical-gauntlet-full-package-test",
        )

        self.assertEqual(len(evaluation_plan.shards), 6)
        self.assertEqual(evaluation_plan.total_matches, 30)
        self.assertEqual(
            [shard.match_count for shard in evaluation_plan.shards],
            [5, 5, 5, 5, 5, 5],
        )
        labels = [
            label
            for shard in evaluation_plan.shards
            for label in shard.match_labels
        ]
        self.assertEqual(len(labels), 30)
        self.assertEqual(len(set(labels)), 30)
        self.assertEqual(
            [shard.shard_id for shard in evaluation_plan.shards],
            [f"historical-gauntlet-shard-{index:03d}" for index in range(6)],
        )

    def test_full_gauntlet_package_writes_all_shards_without_historical_uploads_by_default(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ow-historical-gauntlet-full-package-") as tmp:
            output_root = Path(tmp)
            result = write_historical_champion_full_shard_package(output_root)

            self.assertIsInstance(result, EvaluationShardJobPackageResult)
            self.assertEqual(len(result.jobs), 6)
            self.assertEqual(len(result.manifest_paths), 6)
            self.assertEqual(len(result.job_paths), 6)
            self.assertTrue(Path(result.index_path).is_file())
            self.assertEqual(sum(len(job.match_labels) for job in result.jobs), 30)
            self.assertEqual([len(job.match_labels) for job in result.jobs], [5] * 6)

            all_labels: list[str] = []
            daytona_plan = build_daytona_shard_job_plan(result.index_path)
            self.assertEqual(len(daytona_plan.specs), 6)

            for job, spec in zip(result.jobs, daytona_plan.specs, strict=True):
                with self.subTest(job=job.shard_id):
                    self.assertEqual(spec.shard_id, job.shard_id)
                    self.assertEqual(
                        set(spec.expected_upload_paths),
                        {job.job_path, job.manifest_path},
                    )
                    self.assertEqual(job.extra_upload_paths, ())

                    payload = json.loads(Path(job.manifest_path).read_text(encoding="utf-8"))
                    manifest = ExperimentManifest.from_dict(payload)
                    self.assertEqual(len(manifest.scenarios), 5)
                    self.assertEqual(
                        {dict(scenario.metadata).get("episode_steps") for scenario in manifest.scenarios},
                        {"500"},
                    )
                    file_paths = [
                        opponent["agent"]["file_path"]
                        for scenario in payload["scenarios"]
                        for opponent in scenario["opponent_agents"]
                        if opponent["agent"]["source_kind"] == "python_file"
                    ]
                    self.assertTrue(file_paths)
                    for file_path in file_paths:
                        path = Path(file_path)
                        self.assertFalse(path.is_absolute(), file_path)
                        self.assertTrue((REPO_ROOT / path).is_file())
                        self.assertTrue(path.is_relative_to("historical_opponents/agents"))
                    all_labels.extend(scenario.label or "" for scenario in manifest.scenarios)

            self.assertEqual(len(all_labels), 30)
            self.assertEqual(len(set(all_labels)), 30)
            serialized_package = json.dumps(result.to_dict(), sort_keys=True)
            for term in ("scoreboard_record", "daytona_job_id", "credentials"):
                self.assertNotIn(term, serialized_package)

    def test_full_package_rejects_skipping_manifest_materialization(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ow-historical-gauntlet-full-package-") as tmp:
            with self.assertRaisesRegex(
                ValueError,
                "require materialized manifests",
            ):
                write_historical_champion_full_shard_package(
                    tmp,
                    materialize_manifests=False,
                )

    def test_full_package_script_exposes_help_successfully(self) -> None:
        completed = subprocess.run(
            [sys.executable, "scripts/prepare_historical_champion_gauntlet_package.py", "--help"],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0)
        self.assertIn("usage:", completed.stdout)
        self.assertNotIn("--no-materialize-manifests", completed.stdout)
        self.assertEqual(completed.stderr, "")


if __name__ == "__main__":
    unittest.main()
