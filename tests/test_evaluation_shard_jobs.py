"""Tests for deterministic shard job package contracts."""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch

from ow_eval import (
    EvaluationShardJob,
    EvaluationShardJobPackageResult,
    ShardPlanConfig,
    build_evaluation_shard_jobs,
    build_evaluation_shard_plan,
    write_evaluation_shard_job_package,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = REPO_ROOT / "experiments" / "manifests"
QUICK_2P = MANIFEST_DIR / "quick-2p-smoke.json"
QUICK_4P = MANIFEST_DIR / "quick-4p-smoke.json"


def shard_plan(output_root: str | Path):
    return build_evaluation_shard_plan(
        (QUICK_2P, QUICK_4P),
        ShardPlanConfig(
            shard_count=2,
            output_root=output_root,
            label_prefix="job",
        ),
    )


class EvaluationShardJobTests(unittest.TestCase):
    def test_module_imports_and_exports_are_available(self) -> None:
        import ow_eval.shard_jobs as shard_jobs

        self.assertIs(shard_jobs.EvaluationShardJob, EvaluationShardJob)
        self.assertIs(
            shard_jobs.EvaluationShardJobPackageResult,
            EvaluationShardJobPackageResult,
        )
        self.assertIs(
            shard_jobs.build_evaluation_shard_jobs,
            build_evaluation_shard_jobs,
        )
        self.assertIs(
            shard_jobs.write_evaluation_shard_job_package,
            write_evaluation_shard_job_package,
        )

    def test_builds_deterministic_job_specs_from_shard_plan(self) -> None:
        plan = shard_plan("/tmp/ow-shard-jobs")

        jobs = build_evaluation_shard_jobs(plan)

        self.assertEqual(tuple(job.job_id for job in jobs), ("job-0000", "job-0001"))
        self.assertEqual(tuple(job.shard_id for job in jobs), ("shard-0000", "shard-0001"))
        self.assertEqual(tuple(job.label for job in jobs), ("job-0000", "job-0001"))
        self.assertEqual(
            tuple(job.manifest_path for job in jobs),
            (
                "/tmp/ow-shard-jobs/job-0000.manifest.json",
                "/tmp/ow-shard-jobs/job-0001.manifest.json",
            ),
        )
        self.assertEqual(
            tuple(job.job_path for job in jobs),
            (
                "/tmp/ow-shard-jobs/job-0000.job.json",
                "/tmp/ow-shard-jobs/job-0001.job.json",
            ),
        )
        self.assertEqual(
            tuple(job.shard_result_path for job in jobs),
            (
                "/tmp/ow-shard-jobs/job-0000.shard-result.json",
                "/tmp/ow-shard-jobs/job-0001.shard-result.json",
            ),
        )
        self.assertEqual(jobs[0].report_path, plan.shards[0].planned_report_path)
        self.assertEqual(jobs[0].command, plan.shards[0].command)
        self.assertEqual(jobs[0].source_manifest_refs, plan.shards[0].source_manifest_refs)
        self.assertEqual(jobs[0].match_labels, plan.shards[0].match_labels)
        self.assertEqual(jobs[0].seeds, plan.shards[0].seeds)

    def test_write_package_materializes_manifests_jobs_and_default_index(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plan = shard_plan(Path(temp_dir) / "package")

            result = write_evaluation_shard_job_package(plan)

            self.assertIs(result.shard_plan, plan)
            self.assertEqual(len(result.jobs), 2)
            self.assertEqual(
                result.index_path,
                str(Path(temp_dir) / "package" / "shard-jobs.index.json"),
            )
            self.assertEqual(
                result.manifest_paths,
                tuple(shard.planned_manifest_path for shard in plan.shards),
            )
            self.assertEqual(result.job_paths, tuple(job.job_path for job in result.jobs))
            self.assertEqual(result.commands, tuple(shard.command for shard in plan.shards))
            self.assertEqual(
                result.summary_text,
                f"shard_jobs=WRITTEN shards=2 jobs=2 index_path={result.index_path}",
            )

            for job in result.jobs:
                job_path = Path(job.job_path)
                self.assertTrue(job_path.is_file())
                self.assertEqual(
                    job_path.read_text(encoding="utf-8"),
                    json.dumps(job.to_dict(), sort_keys=True, indent=2) + "\n",
                )
                self.assertTrue(Path(job.manifest_path).is_file())

            index_path = Path(result.index_path)
            self.assertTrue(index_path.is_file())
            self.assertEqual(
                index_path.read_text(encoding="utf-8"),
                json.dumps(result.to_dict(), sort_keys=True, indent=2) + "\n",
            )

    def test_materialize_false_writes_jobs_and_index_but_not_manifests(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plan = shard_plan(Path(temp_dir) / "package")

            result = write_evaluation_shard_job_package(
                plan,
                materialize_manifests=False,
            )

            self.assertTrue(Path(result.index_path).is_file())
            self.assertTrue(all(Path(path).is_file() for path in result.job_paths))
            self.assertFalse(any(Path(path).exists() for path in result.manifest_paths))

    def test_explicit_index_path_is_stable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            plan = shard_plan(root / "package")
            index_path = root / "indexes" / "custom.index.json"

            result = write_evaluation_shard_job_package(
                plan,
                index_path=index_path,
                materialize_manifests=False,
            )

            self.assertEqual(result.index_path, str(index_path))
            self.assertTrue(index_path.is_file())
            self.assertFalse((root / "package" / "shard-jobs.index.json").exists())

    def test_package_result_is_frozen_slotted_validates_and_is_json_safe(self) -> None:
        plan = shard_plan("/tmp/ow-shard-jobs")
        jobs = build_evaluation_shard_jobs(plan)
        result = EvaluationShardJobPackageResult(
            shard_plan=plan,
            jobs=jobs,
            manifest_paths=tuple(job.manifest_path for job in jobs),
            job_paths=tuple(job.job_path for job in jobs),
            index_path="/tmp/ow-shard-jobs/index.json",
            commands=tuple(job.command for job in jobs),
            summary_text="summary",
        )

        with self.assertRaises(FrozenInstanceError):
            result.summary_text = "changed"  # type: ignore[misc]
        with self.assertRaises((AttributeError, TypeError)):
            result.extra = "nope"  # type: ignore[attr-defined]
        with self.assertRaisesRegex(ValueError, "shard_plan"):
            EvaluationShardJobPackageResult(
                shard_plan="bad",  # type: ignore[arg-type]
                jobs=(),
                manifest_paths=(),
                job_paths=(),
                index_path="/tmp/index.json",
                commands=(),
                summary_text="summary",
            )
        with self.assertRaisesRegex(ValueError, "jobs"):
            EvaluationShardJobPackageResult(
                shard_plan=plan,
                jobs=["bad"],  # type: ignore[list-item]
                manifest_paths=(),
                job_paths=(),
                index_path="/tmp/index.json",
                commands=(),
                summary_text="summary",
            )
        with self.assertRaisesRegex(ValueError, "index_path"):
            EvaluationShardJobPackageResult(
                shard_plan=plan,
                jobs=jobs,
                manifest_paths=(),
                job_paths=(),
                index_path="",
                commands=(),
                summary_text="summary",
            )

        decoded = json.loads(json.dumps(result.to_dict(), sort_keys=True))
        self.assertEqual(decoded["index_path"], "/tmp/ow-shard-jobs/index.json")
        self.assertEqual(decoded["jobs"][0]["job_id"], "job-0000")
        self.assertEqual(decoded["shard_plan"]["total_matches"], 4)

    def test_job_object_is_frozen_slotted_and_validates(self) -> None:
        job = build_evaluation_shard_jobs(shard_plan("/tmp/ow-shard-jobs"))[0]

        with self.assertRaises(FrozenInstanceError):
            job.job_id = "changed"  # type: ignore[misc]
        with self.assertRaises((AttributeError, TypeError)):
            job.extra = "nope"  # type: ignore[attr-defined]
        with self.assertRaisesRegex(ValueError, "job_id"):
            EvaluationShardJob(
                job_id="",
                shard_id="shard-0000",
                label="label",
                manifest_path="/tmp/manifest.json",
                report_path="/tmp/report.json",
                shard_result_path="/tmp/result.json",
                job_path="/tmp/job.json",
                command="python script.py",
                source_manifest_refs=(),
                match_labels=(),
                seeds=(),
            )
        with self.assertRaisesRegex(ValueError, "seeds"):
            EvaluationShardJob(
                job_id="job-0000",
                shard_id="shard-0000",
                label="label",
                manifest_path="/tmp/manifest.json",
                report_path="/tmp/report.json",
                shard_result_path="/tmp/result.json",
                job_path="/tmp/job.json",
                command="python script.py",
                source_manifest_refs=(),
                match_labels=(),
                seeds=(True,),  # type: ignore[arg-type]
            )

    def test_invalid_inputs_raise_clear_errors(self) -> None:
        with self.assertRaisesRegex(ValueError, "plan"):
            build_evaluation_shard_jobs("bad")  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "plan"):
            write_evaluation_shard_job_package("bad")  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "materialize_manifests"):
            write_evaluation_shard_job_package(
                shard_plan("/tmp/ow-shard-jobs"),
                materialize_manifests="yes",  # type: ignore[arg-type]
            )

    def test_packaging_does_not_run_matches_spawn_subprocesses_or_call_daytona(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plan = shard_plan(Path(temp_dir) / "package")

            with patch("ow_eval.official_runner.run_official_match") as official_runner:
                with patch("ow_eval.shard_runner.run_evaluation_batch") as batch_runner:
                    with patch("subprocess.run") as subprocess_run:
                        result = write_evaluation_shard_job_package(plan)

            self.assertEqual(len(result.jobs), 2)
            official_runner.assert_not_called()
            batch_runner.assert_not_called()
            subprocess_run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
