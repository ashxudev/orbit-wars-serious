"""Tests for deterministic Daytona shard worker job specs."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch

from ow_eval import (
    DaytonaShardJobPlan,
    DaytonaShardJobPlanConfig,
    DaytonaShardJobSpec,
    ShardPlanConfig,
    build_daytona_shard_job_plan,
    build_evaluation_shard_plan,
    write_evaluation_shard_job_package,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = REPO_ROOT / "experiments" / "manifests"
QUICK_2P = MANIFEST_DIR / "quick-2p-smoke.json"
QUICK_4P = MANIFEST_DIR / "quick-4p-smoke.json"


def packaged_index(temp_dir: str | Path):
    plan = build_evaluation_shard_plan(
        (QUICK_2P, QUICK_4P),
        ShardPlanConfig(
            shard_count=2,
            output_root=Path(temp_dir) / "package",
            label_prefix="daytona",
        ),
    )
    return write_evaluation_shard_job_package(plan)


def expected_artifact_download_paths(job) -> tuple[str, ...]:
    artifact_dir = Path(job.manifest_path).parent / f"{job.label}.artifacts"
    paths: list[str] = []
    for index in range(len(job.match_labels)):
        base_name = f"{job.label}-match-{index:04d}"
        paths.append(str(artifact_dir / f"{base_name}-replay.json"))
        paths.append(str(artifact_dir / f"{base_name}-result.json"))
    return tuple(paths)


class DaytonaShardJobTests(unittest.TestCase):
    def test_module_imports_and_exports_are_available(self) -> None:
        import ow_eval.daytona_jobs as daytona_jobs

        self.assertIs(daytona_jobs.DaytonaShardJobSpec, DaytonaShardJobSpec)
        self.assertIs(daytona_jobs.DaytonaShardJobPlan, DaytonaShardJobPlan)
        self.assertIs(
            daytona_jobs.DaytonaShardJobPlanConfig,
            DaytonaShardJobPlanConfig,
        )
        self.assertIs(
            daytona_jobs.build_daytona_shard_job_plan,
            build_daytona_shard_job_plan,
        )

    def test_builds_specs_in_shard_job_index_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = packaged_index(temp_dir)

            plan = build_daytona_shard_job_plan(package.index_path)

            self.assertIsInstance(plan, DaytonaShardJobPlan)
            self.assertEqual(plan.index_path, package.index_path)
            self.assertEqual(
                tuple(spec.job_id for spec in plan.specs),
                tuple(job.job_id for job in package.jobs),
            )
            self.assertEqual(
                tuple(spec.shard_id for spec in plan.specs),
                tuple(job.shard_id for job in package.jobs),
            )
            self.assertEqual(
                tuple(spec.label for spec in plan.specs),
                tuple(job.label for job in package.jobs),
            )
            self.assertEqual(
                plan.summary_text,
                (
                    f"daytona_shard_jobs=READY index_path={package.index_path} "
                    "jobs=2 working_dir=/workspace/orbit-wars-serious"
                ),
            )

    def test_worker_argv_is_structured_and_references_runner_and_job_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = packaged_index(temp_dir)

            plan = build_daytona_shard_job_plan(package.index_path)

            for spec, job in zip(plan.specs, package.jobs, strict=True):
                self.assertIsInstance(spec.worker_argv, tuple)
                self.assertEqual(
                    spec.worker_argv,
                    (
                        ".venv/bin/python",
                        "scripts/run_evaluation_shard_job.py",
                        job.job_path,
                    ),
                )
                self.assertEqual(spec.local_job_path, job.job_path)
                self.assertEqual(spec.local_manifest_path, job.manifest_path)
                self.assertEqual(spec.local_shard_result_path, job.shard_result_path)
                self.assertEqual(
                    spec.expected_upload_paths,
                    (job.job_path, job.manifest_path),
                )
                self.assertEqual(
                    spec.expected_download_paths,
                    (
                        job.shard_result_path,
                        *expected_artifact_download_paths(job),
                    ),
                )
                self.assertTrue(spec.sandbox_name.startswith("ow-eval-shard-"))

    def test_custom_config_overrides_worker_defaults_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = packaged_index(temp_dir)
            config = DaytonaShardJobPlanConfig(
                working_dir="/workspace/custom",
                python_command="python3",
                runner_script="scripts/run_evaluation_shard_job.py",
                sandbox_name_prefix="custom-sandbox",
            )

            plan = build_daytona_shard_job_plan(package.index_path, config)

            self.assertIs(plan.config, config)
            self.assertEqual(plan.specs[0].working_dir, "/workspace/custom")
            self.assertEqual(plan.specs[0].worker_argv[0], "python3")
            self.assertEqual(
                plan.specs[0].sandbox_name,
                f"custom-sandbox-0000-{package.jobs[0].label}",
            )

    def test_none_sandbox_prefix_leaves_sandbox_name_unset(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = packaged_index(temp_dir)
            config = DaytonaShardJobPlanConfig(sandbox_name_prefix=None)

            plan = build_daytona_shard_job_plan(package.index_path, config)

            self.assertIsNone(plan.specs[0].sandbox_name)

    def test_malformed_config_and_spec_validation_raise_clear_errors(self) -> None:
        with self.assertRaisesRegex(ValueError, "working_dir"):
            DaytonaShardJobPlanConfig(working_dir="")
        with self.assertRaisesRegex(ValueError, "python_command"):
            DaytonaShardJobPlanConfig(python_command="")
        with self.assertRaisesRegex(ValueError, "runner_script"):
            DaytonaShardJobPlanConfig(runner_script="")
        with self.assertRaisesRegex(ValueError, "sandbox_name_prefix"):
            DaytonaShardJobPlanConfig(sandbox_name_prefix="")

        with tempfile.TemporaryDirectory() as temp_dir:
            package = packaged_index(temp_dir)
            with self.assertRaisesRegex(ValueError, "config"):
                build_daytona_shard_job_plan(
                    package.index_path,
                    config=object(),  # type: ignore[arg-type]
                )

        with self.assertRaisesRegex(ValueError, "runner_script"):
            DaytonaShardJobSpec(
                job_id="job-0000",
                shard_id="shard-0000",
                label="label",
                local_job_path="/tmp/job.json",
                local_manifest_path="/tmp/manifest.json",
                local_shard_result_path="/tmp/result.json",
                worker_argv=("python", "/tmp/job.json"),
                working_dir="/workspace",
                runner_script="scripts/run_evaluation_shard_job.py",
                sandbox_name=None,
                expected_upload_paths=("/tmp/job.json", "/tmp/manifest.json"),
                expected_download_paths=("/tmp/result.json",),
            )
        with self.assertRaisesRegex(ValueError, "local_job_path"):
            DaytonaShardJobSpec(
                job_id="job-0000",
                shard_id="shard-0000",
                label="label",
                local_job_path="/tmp/job.json",
                local_manifest_path="/tmp/manifest.json",
                local_shard_result_path="/tmp/result.json",
                worker_argv=("python", "scripts/run_evaluation_shard_job.py"),
                working_dir="/workspace",
                runner_script="scripts/run_evaluation_shard_job.py",
                sandbox_name=None,
                expected_upload_paths=("/tmp/job.json", "/tmp/manifest.json"),
                expected_download_paths=("/tmp/result.json",),
            )

    def test_malformed_index_or_job_metadata_fails_from_reader_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = packaged_index(temp_dir)
            payload = json.loads(Path(package.index_path).read_text(encoding="utf-8"))
            bad_index_path = Path(temp_dir) / "bad.index.json"

            bad_payload = dict(payload)
            bad_payload["job_paths"] = ["/tmp/other.job.json", package.job_paths[1]]
            bad_index_path.write_text(json.dumps(bad_payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "job_paths\\[0\\]"):
                build_daytona_shard_job_plan(bad_index_path)

            bad_payload = dict(payload)
            bad_jobs = [dict(job) for job in payload["jobs"]]
            bad_jobs[0]["job_path"] = ""
            bad_payload["jobs"] = bad_jobs
            bad_index_path.write_text(json.dumps(bad_payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "jobs\\[0\\].job_path"):
                build_daytona_shard_job_plan(bad_index_path)

    def test_plan_and_spec_are_frozen_slotted_and_json_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = packaged_index(temp_dir)
            plan = build_daytona_shard_job_plan(package.index_path)
            spec = plan.specs[0]

            with self.assertRaises(FrozenInstanceError):
                plan.summary_text = "changed"  # type: ignore[misc]
            with self.assertRaises((AttributeError, TypeError)):
                plan.extra = "nope"  # type: ignore[attr-defined]
            with self.assertRaises(FrozenInstanceError):
                spec.label = "changed"  # type: ignore[misc]
            with self.assertRaises((AttributeError, TypeError)):
                spec.extra = "nope"  # type: ignore[attr-defined]
            with self.assertRaisesRegex(ValueError, "specs"):
                DaytonaShardJobPlan(
                    index_path=package.index_path,
                    config=plan.config,
                    job_index=plan.job_index,
                    specs=(),
                    summary_text="summary",
                )

            decoded = json.loads(json.dumps(plan.to_dict(), sort_keys=True))
            self.assertEqual(decoded["specs"][0]["job_id"], "job-0000")
            self.assertEqual(
                decoded["specs"][0]["worker_argv"][1],
                "scripts/run_evaluation_shard_job.py",
            )
            self.assertEqual(decoded["job_index"]["job_paths"], list(package.job_paths))

    def test_building_plan_does_not_execute_or_call_daytona_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = packaged_index(temp_dir)
            sys.modules.pop("daytona", None)

            with patch("subprocess.run") as subprocess_run:
                with patch(
                    "ow_eval.shard_job_runner.run_evaluation_shard_job",
                ) as run_job:
                    with patch(
                        "ow_eval.shard_index_runner.run_evaluation_shard_job_index",
                    ) as run_index:
                        with patch(
                            "ow_eval.official_runner.run_official_match",
                        ) as official_runner:
                            plan = build_daytona_shard_job_plan(package.index_path)

            self.assertEqual(len(plan.specs), 2)
            subprocess_run.assert_not_called()
            run_job.assert_not_called()
            run_index.assert_not_called()
            official_runner.assert_not_called()
            self.assertNotIn("daytona", sys.modules)


if __name__ == "__main__":
    unittest.main()
