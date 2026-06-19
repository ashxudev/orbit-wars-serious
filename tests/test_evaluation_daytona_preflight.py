"""Tests for Daytona shard job plan reader and preflight validation."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch

from ow_eval import (
    DaytonaShardJobPlan,
    DaytonaShardJobPlanValidationResult,
    ShardPlanConfig,
    build_daytona_shard_job_plan,
    build_evaluation_shard_plan,
    read_daytona_shard_job_plan,
    validate_daytona_shard_job_plan,
    validate_daytona_shard_jobs_main,
    write_evaluation_shard_job_package,
    write_daytona_shard_job_plan,
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
            label_prefix="daytona-preflight",
        ),
    )
    return write_evaluation_shard_job_package(plan)


def written_daytona_plan(temp_dir: str | Path):
    package = packaged_index(temp_dir)
    plan = build_daytona_shard_job_plan(package.index_path)
    plan_path = Path(temp_dir) / "daytona-plan.json"
    write_daytona_shard_job_plan(plan, plan_path)
    return package, plan, plan_path


class DaytonaPreflightTests(unittest.TestCase):
    def test_module_imports_and_exports_are_available(self) -> None:
        import ow_eval.daytona_preflight as daytona_preflight

        self.assertIs(
            daytona_preflight.DaytonaShardJobPlanValidationResult,
            DaytonaShardJobPlanValidationResult,
        )
        self.assertIs(
            daytona_preflight.read_daytona_shard_job_plan,
            read_daytona_shard_job_plan,
        )
        self.assertIs(
            daytona_preflight.validate_daytona_shard_job_plan,
            validate_daytona_shard_job_plan,
        )
        self.assertIs(daytona_preflight.main, validate_daytona_shard_jobs_main)

    def test_reads_plan_json_into_typed_objects_with_identical_to_dict(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _package, _plan, plan_path = written_daytona_plan(temp_dir)
            payload = json.loads(plan_path.read_text(encoding="utf-8"))

            loaded = read_daytona_shard_job_plan(plan_path)

            self.assertIsInstance(loaded, DaytonaShardJobPlan)
            self.assertEqual(loaded.to_dict(), payload)
            self.assertEqual(loaded.config.to_dict(), payload["config"])
            self.assertEqual(loaded.job_index.to_dict(), payload["job_index"])
            self.assertEqual(loaded.specs[0].to_dict(), payload["specs"][0])

    def test_valid_temp_plan_passes_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package, plan, plan_path = written_daytona_plan(temp_dir)
            self.assertFalse(Path(package.jobs[0].shard_result_path).exists())

            result = validate_daytona_shard_job_plan(plan_path)

            self.assertEqual(result.exit_code, 0)
            self.assertTrue(result.passed)
            self.assertEqual(result.plan_path, str(plan_path))
            self.assertEqual(result.plan.to_dict(), plan.to_dict())
            self.assertEqual(result.missing_upload_paths, ())
            self.assertEqual(result.duplicate_sandbox_names, ())
            self.assertIn("daytona_shard_job_plan_validation=PASS", result.summary_text)

    def test_plan_object_can_be_validated_without_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _package, plan, _plan_path = written_daytona_plan(temp_dir)

            result = validate_daytona_shard_job_plan(plan)

            self.assertIsNone(result.plan_path)
            self.assertEqual(result.exit_code, 0)
            self.assertIs(result.plan, plan)

    def test_missing_upload_paths_fail_but_missing_download_paths_do_not(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package, _plan, plan_path = written_daytona_plan(temp_dir)
            missing_manifest = Path(package.jobs[0].manifest_path)
            missing_manifest.unlink()
            self.assertFalse(Path(package.jobs[0].shard_result_path).exists())

            result = validate_daytona_shard_job_plan(plan_path)

            self.assertEqual(result.exit_code, 2)
            self.assertFalse(result.passed)
            self.assertIn(str(missing_manifest), result.missing_upload_paths)
            self.assertNotIn(
                package.jobs[0].shard_result_path,
                result.missing_upload_paths,
            )
            self.assertIn("missing upload paths", result.error_text)

    def test_upload_path_existence_check_can_be_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package, _plan, plan_path = written_daytona_plan(temp_dir)
            Path(package.jobs[0].job_path).unlink()

            result = validate_daytona_shard_job_plan(
                plan_path,
                require_upload_paths_exist=False,
            )

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.missing_upload_paths, ())

    def test_duplicate_sandbox_names_fail_by_default_and_can_be_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _package, _plan, plan_path = written_daytona_plan(temp_dir)
            payload = json.loads(plan_path.read_text(encoding="utf-8"))
            payload["specs"][1]["sandbox_name"] = payload["specs"][0]["sandbox_name"]
            plan_path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")

            result = validate_daytona_shard_job_plan(plan_path)

            self.assertEqual(result.exit_code, 2)
            self.assertEqual(
                result.duplicate_sandbox_names,
                (payload["specs"][0]["sandbox_name"],),
            )
            self.assertIn("duplicate sandbox names", result.error_text)

            allowed = validate_daytona_shard_job_plan(
                plan_path,
                require_unique_sandbox_names=False,
            )
            self.assertEqual(allowed.exit_code, 0)
            self.assertEqual(allowed.duplicate_sandbox_names, result.duplicate_sandbox_names)

    def test_malformed_plan_payloads_raise_clear_value_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _package, _plan, plan_path = written_daytona_plan(temp_dir)
            payload = json.loads(plan_path.read_text(encoding="utf-8"))
            bad_path = Path(temp_dir) / "bad-plan.json"

            bad_path.write_text("[]\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "object"):
                read_daytona_shard_job_plan(bad_path)

            bad_payload = dict(payload)
            bad_payload["config"] = {}
            bad_path.write_text(json.dumps(bad_payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "config.working_dir"):
                read_daytona_shard_job_plan(bad_path)

            bad_payload = dict(payload)
            bad_specs = [dict(spec) for spec in payload["specs"]]
            bad_specs[0]["worker_argv"] = []
            bad_payload["specs"] = bad_specs
            bad_path.write_text(json.dumps(bad_payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "worker_argv"):
                read_daytona_shard_job_plan(bad_path)

            bad_payload = dict(payload)
            bad_job_index = dict(payload["job_index"])
            bad_jobs = [dict(job) for job in bad_job_index["jobs"]]
            bad_jobs[0]["job_path"] = ""
            bad_job_index["jobs"] = bad_jobs
            bad_payload["job_index"] = bad_job_index
            bad_path.write_text(json.dumps(bad_payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "job_index.jobs\\[0\\].job_path"):
                read_daytona_shard_job_plan(bad_path)

            bad_payload = dict(payload)
            bad_specs = [dict(spec) for spec in payload["specs"]]
            bad_specs[0]["local_job_path"] = "/tmp/other.job.json"
            bad_specs[0]["worker_argv"] = [
                *bad_specs[0]["worker_argv"][:2],
                "/tmp/other.job.json",
            ]
            bad_payload["specs"] = bad_specs
            bad_path.write_text(json.dumps(bad_payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "local_job_path"):
                read_daytona_shard_job_plan(bad_path)

    def test_cli_success_and_flags(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package, _plan, plan_path = written_daytona_plan(temp_dir)
            Path(package.jobs[0].job_path).unlink()
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = validate_daytona_shard_jobs_main(
                    [
                        str(plan_path),
                        "--no-upload-path-existence-check",
                        "--allow-duplicate-sandbox-names",
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertIn("daytona_shard_job_plan_validation=PASS", stdout.getvalue())

    def test_cli_failure_prints_errors_to_stderr(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package, _plan, plan_path = written_daytona_plan(temp_dir)
            Path(package.jobs[0].job_path).unlink()
            stdout = io.StringIO()
            stderr = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                with contextlib.redirect_stderr(stderr):
                    exit_code = validate_daytona_shard_jobs_main([str(plan_path)])

            self.assertEqual(exit_code, 2)
            self.assertIn("daytona_shard_job_plan_validation=ERROR", stdout.getvalue())
            self.assertIn("missing upload paths", stderr.getvalue())

    def test_cli_help_exits_zero(self) -> None:
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            with self.assertRaises(SystemExit) as raised:
                validate_daytona_shard_jobs_main(["--help"])

        self.assertEqual(raised.exception.code, 0)
        self.assertIn("Daytona shard job plan", stdout.getvalue())

    def test_validation_result_is_frozen_slotted_and_json_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _package, _plan, plan_path = written_daytona_plan(temp_dir)
            result = validate_daytona_shard_job_plan(plan_path)

            with self.assertRaises(FrozenInstanceError):
                result.exit_code = 2  # type: ignore[misc]
            with self.assertRaises((AttributeError, TypeError)):
                result.extra = "nope"  # type: ignore[attr-defined]
            with self.assertRaisesRegex(ValueError, "exit_code"):
                DaytonaShardJobPlanValidationResult(
                    exit_code=True,  # type: ignore[arg-type]
                    summary_text="summary",
                )

            decoded = json.loads(json.dumps(result.to_dict(), sort_keys=True))
            self.assertTrue(decoded["passed"])
            self.assertEqual(decoded["missing_upload_paths"], [])
            self.assertEqual(len(decoded["plan"]["specs"]), 2)

    def test_preflight_does_not_execute_or_call_daytona_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _package, _plan, plan_path = written_daytona_plan(temp_dir)
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
                            result = validate_daytona_shard_job_plan(plan_path)

            self.assertEqual(result.exit_code, 0)
            subprocess_run.assert_not_called()
            run_job.assert_not_called()
            run_index.assert_not_called()
            official_runner.assert_not_called()
            self.assertNotIn("daytona", sys.modules)


if __name__ == "__main__":
    unittest.main()
