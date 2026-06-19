"""Tests for deterministic Daytona executor dry-run CLI."""

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
    DaytonaDryRunExecutor,
    DaytonaExecutorCliResult,
    DaytonaShardExecutionBatchResult,
    DaytonaShardExecutionRequest,
    ShardPlanConfig,
    build_daytona_shard_job_plan,
    build_evaluation_shard_plan,
    run_daytona_shard_jobs,
    run_daytona_shard_jobs_main,
    write_daytona_shard_job_plan,
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
            label_prefix="daytona-dry-run",
        ),
    )
    return write_evaluation_shard_job_package(plan)


def written_daytona_plan(temp_dir: str | Path):
    package = packaged_index(temp_dir)
    plan = build_daytona_shard_job_plan(package.index_path)
    plan_path = Path(temp_dir) / "daytona-plan.json"
    write_daytona_shard_job_plan(plan, plan_path)
    return package, plan, plan_path


class DaytonaExecutorCliTests(unittest.TestCase):
    def test_module_imports_and_exports_are_available(self) -> None:
        import ow_eval.daytona_executor_cli as daytona_executor_cli

        self.assertIs(daytona_executor_cli.DaytonaDryRunExecutor, DaytonaDryRunExecutor)
        self.assertIs(
            daytona_executor_cli.DaytonaExecutorCliResult,
            DaytonaExecutorCliResult,
        )
        self.assertIs(
            daytona_executor_cli.run_daytona_shard_jobs,
            run_daytona_shard_jobs,
        )
        self.assertIs(daytona_executor_cli.main, run_daytona_shard_jobs_main)

    def test_dry_run_executor_preserves_order_and_returns_request_result_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _package, plan, _plan_path = written_daytona_plan(temp_dir)
            executor = DaytonaDryRunExecutor()
            requests = tuple(
                DaytonaShardExecutionRequest(
                    job_id=spec.job_id,
                    shard_id=spec.shard_id,
                    label=spec.label,
                    sandbox_name=spec.sandbox_name,
                    worker_argv=spec.worker_argv,
                    working_dir=spec.working_dir,
                    expected_upload_paths=spec.expected_upload_paths,
                    expected_download_paths=spec.expected_download_paths,
                    local_shard_result_path=spec.local_shard_result_path,
                    spec=spec,
                )
                for spec in plan.specs
            )

            results = tuple(executor.execute(request) for request in requests)

            self.assertEqual(tuple(executor.requests), requests)
            self.assertEqual(
                tuple(result.shard_result_path for result in results),
                tuple(spec.local_shard_result_path for spec in plan.specs),
            )
            self.assertEqual(tuple(result.exit_code for result in results), (0, 0))
            self.assertIn("daytona_dry_run=COMPLETE", results[0].summary_text)

    def test_dry_run_success_preserves_requests_and_results_without_merge(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _package, plan, plan_path = written_daytona_plan(temp_dir)

            with patch(
                "ow_eval.daytona_executor.merge_evaluation_shard_result_files",
            ) as merge_files:
                result = run_daytona_shard_jobs(plan_path, dry_run=True)

            self.assertEqual(result.exit_code, 0)
            self.assertTrue(result.passed)
            self.assertIsInstance(result.batch_result, DaytonaShardExecutionBatchResult)
            self.assertEqual(
                tuple(request.job_id for request in result.batch_result.execution_requests),
                tuple(spec.job_id for spec in plan.specs),
            )
            self.assertEqual(
                tuple(execution.job_id for execution in result.batch_result.execution_results),
                tuple(spec.job_id for spec in plan.specs),
            )
            self.assertEqual(
                result.batch_result.shard_result_paths,
                tuple(spec.local_shard_result_path for spec in plan.specs),
            )
            self.assertIsNone(result.batch_result.merged_result)
            self.assertIn("merged=False", result.batch_result.summary_text)
            merge_files.assert_not_called()

    def test_dry_run_mode_is_required_for_this_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _package, _plan, plan_path = written_daytona_plan(temp_dir)

            result = run_daytona_shard_jobs(plan_path)

            self.assertEqual(result.exit_code, 2)
            self.assertFalse(result.passed)
            self.assertIsNone(result.batch_result)
            self.assertIn("dry-run mode is required", result.error_text)

    def test_preflight_failure_stops_before_executor_requests(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package, _plan, plan_path = written_daytona_plan(temp_dir)
            Path(package.jobs[0].manifest_path).unlink()

            with patch.object(
                DaytonaDryRunExecutor,
                "execute",
                wraps=DaytonaDryRunExecutor.execute,
            ) as execute:
                result = run_daytona_shard_jobs(plan_path, dry_run=True)

            self.assertEqual(result.exit_code, 2)
            self.assertIsNotNone(result.batch_result)
            self.assertEqual(result.batch_result.execution_requests, ())
            self.assertEqual(result.batch_result.execution_results, ())
            self.assertIn("preflight failed", result.error_text)
            execute.assert_not_called()

    def test_synthetic_failure_by_job_id_returns_nonzero_and_skips_merge(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _package, plan, plan_path = written_daytona_plan(temp_dir)
            failing = plan.specs[1]

            with patch(
                "ow_eval.daytona_executor.merge_evaluation_shard_result_files",
            ) as merge_files:
                result = run_daytona_shard_jobs(
                    plan_path,
                    dry_run=True,
                    fail_job_id=failing.job_id,
                )

            self.assertEqual(result.exit_code, 2)
            self.assertFalse(result.passed)
            self.assertEqual(len(result.batch_result.execution_results), 2)
            self.assertEqual(
                tuple(execution.exit_code for execution in result.batch_result.execution_results),
                (0, 2),
            )
            self.assertIn("synthetic dry-run failure", result.error_text)
            self.assertIn(failing.job_id, result.error_text)
            merge_files.assert_not_called()

    def test_synthetic_failure_by_job_index_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _package, _plan, plan_path = written_daytona_plan(temp_dir)

            result = run_daytona_shard_jobs(
                plan_path,
                dry_run=True,
                fail_job_index=0,
            )

            self.assertEqual(result.exit_code, 2)
            self.assertEqual(len(result.batch_result.execution_results), 1)
            self.assertIn("job_index=0", result.error_text)

    def test_preflight_options_flow_through(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package, _plan, plan_path = written_daytona_plan(temp_dir)
            Path(package.jobs[0].job_path).unlink()

            result = run_daytona_shard_jobs(
                plan_path,
                dry_run=True,
                require_upload_paths_exist=False,
            )

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.batch_result.preflight_result.missing_upload_paths, ())

    def test_optional_json_output_is_deterministic_batch_result_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _package, _plan, plan_path = written_daytona_plan(temp_dir)
            output_path = Path(temp_dir) / "nested" / "dry-run.json"

            result = run_daytona_shard_jobs(
                plan_path,
                dry_run=True,
                json_output=output_path,
            )

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.json_output_path, str(output_path))
            expected = (
                json.dumps(
                    result.batch_result.to_dict(),
                    sort_keys=True,
                    indent=2,
                )
                + "\n"
            )
            self.assertEqual(output_path.read_text(encoding="utf-8"), expected)
            decoded = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(decoded, result.batch_result.to_dict())

    def test_cli_success_failure_help_and_json_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _package, plan, plan_path = written_daytona_plan(temp_dir)
            output_path = Path(temp_dir) / "cli-result.json"
            stdout = io.StringIO()
            stderr = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                with contextlib.redirect_stderr(stderr):
                    exit_code = run_daytona_shard_jobs_main(
                        [
                            str(plan_path),
                            "--dry-run",
                            "--json-output",
                            str(output_path),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertIn("daytona_shard_jobs_cli=COMPLETE", stdout.getvalue())
            decoded = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(
                [result["job_id"] for result in decoded["execution_results"]],
                [spec.job_id for spec in plan.specs],
            )

            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                with contextlib.redirect_stderr(stderr):
                    exit_code = run_daytona_shard_jobs_main(
                        [
                            str(plan_path),
                            "--dry-run",
                            "--fail-job-index",
                            "1",
                        ]
                    )

            self.assertEqual(exit_code, 2)
            self.assertIn("daytona_shard_jobs_cli=ERROR", stdout.getvalue())
            self.assertIn("synthetic dry-run failure", stderr.getvalue())

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                with self.assertRaises(SystemExit) as raised:
                    run_daytona_shard_jobs_main(["--help"])
            self.assertEqual(raised.exception.code, 0)
            self.assertIn("Dry-run", stdout.getvalue())

    def test_result_objects_are_frozen_slotted_validated_and_json_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _package, _plan, plan_path = written_daytona_plan(temp_dir)
            result = run_daytona_shard_jobs(plan_path, dry_run=True)

            with self.assertRaises(FrozenInstanceError):
                result.exit_code = 2  # type: ignore[misc]
            with self.assertRaises((AttributeError, TypeError)):
                result.extra = "nope"  # type: ignore[attr-defined]
            with self.assertRaisesRegex(ValueError, "dry_run"):
                DaytonaExecutorCliResult(
                    plan_path=str(plan_path),
                    dry_run="yes",  # type: ignore[arg-type]
                    summary_text="summary",
                )
            with self.assertRaisesRegex(ValueError, "fail_job_index"):
                DaytonaDryRunExecutor(fail_job_index=-1)

            decoded = json.loads(json.dumps(result.to_dict(), sort_keys=True))
            self.assertTrue(decoded["passed"])
            self.assertEqual(decoded["batch_result"]["merged_result"], None)

    def test_cli_does_not_execute_worker_argv_subprocess_daytona_or_matches(self) -> None:
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
                            result = run_daytona_shard_jobs(
                                plan_path,
                                dry_run=True,
                            )

            self.assertEqual(result.exit_code, 0)
            subprocess_run.assert_not_called()
            run_job.assert_not_called()
            run_index.assert_not_called()
            official_runner.assert_not_called()
            self.assertNotIn("daytona", sys.modules)


if __name__ == "__main__":
    unittest.main()
