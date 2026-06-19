"""Tests for Daytona client execution report dry-run CLI."""

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
    DaytonaClientReportCliResult,
    DaytonaRecordingClient,
    ShardPlanConfig,
    build_daytona_shard_job_plan,
    build_evaluation_shard_plan,
    run_daytona_client_report,
    run_daytona_client_report_main,
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
            label_prefix="daytona-client-cli",
        ),
    )
    return write_evaluation_shard_job_package(plan)


def written_daytona_plan(temp_dir: str | Path):
    package = packaged_index(temp_dir)
    plan = build_daytona_shard_job_plan(package.index_path)
    plan_path = Path(temp_dir) / "daytona-plan.json"
    write_daytona_shard_job_plan(plan, plan_path)
    return package, plan, plan_path


class DaytonaClientReportCliTests(unittest.TestCase):
    def test_module_imports_and_exports_are_available(self) -> None:
        import ow_eval.daytona_client_report_cli as daytona_client_report_cli

        self.assertIs(
            daytona_client_report_cli.DaytonaRecordingClient,
            DaytonaRecordingClient,
        )
        self.assertIs(
            daytona_client_report_cli.DaytonaClientReportCliResult,
            DaytonaClientReportCliResult,
        )
        self.assertIs(
            daytona_client_report_cli.run_daytona_client_report,
            run_daytona_client_report,
        )
        self.assertIs(daytona_client_report_cli.main, run_daytona_client_report_main)

    def test_dry_run_success_produces_report_trace_and_operation_plans(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _package, plan, plan_path = written_daytona_plan(temp_dir)

            result = run_daytona_client_report(plan_path, dry_run=True)

            self.assertEqual(result.exit_code, 0)
            self.assertTrue(result.passed)
            self.assertIsNotNone(result.report)
            self.assertEqual(
                tuple(execution.job_id for execution in result.report.batch_result.execution_results),
                tuple(spec.job_id for spec in plan.specs),
            )
            self.assertEqual(
                tuple(operation.job_id for operation in result.report.operation_plans),
                tuple(spec.job_id for spec in plan.specs),
            )
            self.assertEqual(len(result.report.client_event_trace), 24)
            self.assertIn("daytona_client_report_cli=COMPLETE", result.summary_text)
            self.assertIn("daytona_client_execution_report=COMPLETE", result.report.summary_text)
            self.assertIsNone(result.report.batch_result.merged_result)

    def test_dry_run_mode_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _package, _plan, plan_path = written_daytona_plan(temp_dir)

            result = run_daytona_client_report(plan_path)

            self.assertEqual(result.exit_code, 2)
            self.assertFalse(result.passed)
            self.assertIsNone(result.report)
            self.assertIn("dry-run mode is required", result.error_text)

    def test_preflight_failure_returns_nonzero_and_no_client_calls(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package, _plan, plan_path = written_daytona_plan(temp_dir)
            Path(package.jobs[0].manifest_path).unlink()

            with patch.object(
                DaytonaRecordingClient,
                "open_sandbox",
                wraps=DaytonaRecordingClient.open_sandbox,
            ) as open_sandbox:
                result = run_daytona_client_report(plan_path, dry_run=True)

            self.assertEqual(result.exit_code, 2)
            self.assertIsNotNone(result.report)
            self.assertEqual(result.report.client_event_trace, ())
            self.assertEqual(result.report.operation_plans, ())
            self.assertIn("preflight failed", result.error_text)
            open_sandbox.assert_not_called()

    def test_synthetic_fail_step_and_command_exit_code_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _package, _plan, plan_path = written_daytona_plan(temp_dir)

            upload_failure = run_daytona_client_report(
                plan_path,
                dry_run=True,
                fail_step="upload",
            )

            self.assertEqual(upload_failure.exit_code, 2)
            self.assertEqual(len(upload_failure.report.operation_plans), 1)
            self.assertIn("synthetic upload failure", upload_failure.error_text)
            self.assertIn(("client", "error"), [
                (event.step, event.status)
                for event in upload_failure.report.client_event_trace
            ])

            command_failure = run_daytona_client_report(
                plan_path,
                dry_run=True,
                command_exit_code=7,
            )

            self.assertEqual(command_failure.exit_code, 2)
            self.assertEqual(len(command_failure.report.operation_plans), 1)
            self.assertIn("synthetic command exit 7", command_failure.error_text)
            self.assertIn(("command", "error"), [
                (event.step, event.status)
                for event in command_failure.report.client_event_trace
            ])

    def test_preflight_options_flow_through(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package, _plan, plan_path = written_daytona_plan(temp_dir)
            Path(package.jobs[0].job_path).unlink()

            result = run_daytona_client_report(
                plan_path,
                dry_run=True,
                require_upload_paths_exist=False,
            )

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(
                result.report.batch_result.preflight_result.missing_upload_paths,
                (),
            )

    def test_json_output_is_deterministic_full_report_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _package, _plan, plan_path = written_daytona_plan(temp_dir)
            output_path = Path(temp_dir) / "nested" / "client-report.json"

            result = run_daytona_client_report(
                plan_path,
                dry_run=True,
                json_output=output_path,
            )

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.json_output_path, str(output_path))
            expected = (
                json.dumps(result.report.to_dict(), sort_keys=True, indent=2)
                + "\n"
            )
            self.assertEqual(output_path.read_text(encoding="utf-8"), expected)
            self.assertEqual(
                json.loads(output_path.read_text(encoding="utf-8")),
                result.report.to_dict(),
            )

    def test_cli_success_failure_help_and_json_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _package, plan, plan_path = written_daytona_plan(temp_dir)
            output_path = Path(temp_dir) / "cli-report.json"
            stdout = io.StringIO()
            stderr = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                with contextlib.redirect_stderr(stderr):
                    exit_code = run_daytona_client_report_main(
                        [
                            str(plan_path),
                            "--dry-run",
                            "--json-output",
                            str(output_path),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertIn("daytona_client_report_cli=COMPLETE", stdout.getvalue())
            decoded = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(
                [item["job_id"] for item in decoded["operation_plans"]],
                [spec.job_id for spec in plan.specs],
            )

            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                with contextlib.redirect_stderr(stderr):
                    exit_code = run_daytona_client_report_main(
                        [
                            str(plan_path),
                            "--dry-run",
                            "--fail-step",
                            "download",
                        ]
                    )

            self.assertEqual(exit_code, 2)
            self.assertIn("daytona_client_report_cli=ERROR", stdout.getvalue())
            self.assertIn("synthetic download failure", stderr.getvalue())

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                with self.assertRaises(SystemExit) as raised:
                    run_daytona_client_report_main(["--help"])
            self.assertEqual(raised.exception.code, 0)
            self.assertIn("Daytona client execution report", stdout.getvalue())

    def test_result_objects_are_frozen_slotted_validated_and_json_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _package, _plan, plan_path = written_daytona_plan(temp_dir)
            result = run_daytona_client_report(plan_path, dry_run=True)

            with self.assertRaises(FrozenInstanceError):
                result.exit_code = 2  # type: ignore[misc]
            with self.assertRaises((AttributeError, TypeError)):
                result.extra = "nope"  # type: ignore[attr-defined]
            with self.assertRaisesRegex(ValueError, "dry_run"):
                DaytonaClientReportCliResult(
                    plan_path=str(plan_path),
                    dry_run="yes",  # type: ignore[arg-type]
                    summary_text="summary",
                )
            with self.assertRaisesRegex(ValueError, "fail_step"):
                DaytonaRecordingClient(fail_step="bad")
            with self.assertRaisesRegex(ValueError, "command_exit_code"):
                DaytonaRecordingClient(command_exit_code=True)  # type: ignore[arg-type]

            decoded = json.loads(json.dumps(result.to_dict(), sort_keys=True))
            self.assertTrue(decoded["passed"])
            self.assertEqual(decoded["report"]["passed"], True)

    def test_cli_does_not_execute_subprocess_daytona_or_matches(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _package, _plan, plan_path = written_daytona_plan(temp_dir)
            sys.modules.pop("daytona", None)

            with patch("subprocess.run") as subprocess_run:
                with patch(
                    "ow_eval.shard_job_runner.run_evaluation_shard_job",
                ) as run_job:
                    with patch(
                        "ow_eval.official_runner.run_official_match",
                    ) as official_runner:
                        result = run_daytona_client_report(plan_path, dry_run=True)

            self.assertEqual(result.exit_code, 0)
            subprocess_run.assert_not_called()
            run_job.assert_not_called()
            official_runner.assert_not_called()
            self.assertNotIn("daytona", sys.modules)


if __name__ == "__main__":
    unittest.main()
