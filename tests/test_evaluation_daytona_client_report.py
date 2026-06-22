"""Tests for deterministic Daytona client execution reports."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch

from ow_eval import (
    DaytonaClientCommandResult,
    DaytonaClientExecutionEvent,
    DaytonaClientExecutionReport,
    DaytonaSandboxHandle,
    EvaluationBatchResult,
    EvaluationBatchSummary,
    EvaluationShardMergeResult,
    ShardPlanConfig,
    build_daytona_shard_job_plan,
    build_evaluation_shard_plan,
    run_daytona_shard_job_plan_with_client_report,
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
            label_prefix="daytona-report",
        ),
    )
    return write_evaluation_shard_job_package(plan)


def written_daytona_plan(temp_dir: str | Path):
    package = packaged_index(temp_dir)
    plan = build_daytona_shard_job_plan(package.index_path)
    plan_path = Path(temp_dir) / "daytona-plan.json"
    write_daytona_shard_job_plan(plan, plan_path)
    return package, plan, plan_path


def expected_call_steps_for_plan(plan) -> list[str]:
    steps: list[str] = []
    for spec in plan.specs:
        steps.extend(
            ["open"]
            + ["upload"] * len(spec.expected_upload_paths)
            + ["command"]
            + ["download"] * len(spec.expected_download_paths)
            + ["close"]
        )
    return steps


def fake_merge_result(match_count: int = 4) -> EvaluationShardMergeResult:
    return EvaluationShardMergeResult(
        shard_results=(),
        batch_result=EvaluationBatchResult(
            summary=EvaluationBatchSummary(
                total_matches=match_count,
                completed_count=match_count,
                error_count=0,
                status_counts=(("completed", match_count),),
            ),
        ),
        summary_text=(
            f"shard_merge=COMPLETE shards=2 matches={match_count} "
            f"completed={match_count} errors=0"
        ),
    )


class RecordingClient:
    def __init__(
        self,
        *,
        fail_step: str | None = None,
        command_exit_code: int = 0,
    ) -> None:
        self.fail_step = fail_step
        self.command_exit_code = command_exit_code
        self.calls: list[tuple[object, ...]] = []

    def open_sandbox(
        self,
        *,
        sandbox_name: str | None,
        working_dir: str,
    ) -> DaytonaSandboxHandle:
        self.calls.append(("open", sandbox_name, working_dir))
        if self.fail_step == "open":
            raise RuntimeError("open failed")
        return DaytonaSandboxHandle(
            sandbox_name=sandbox_name,
            working_dir=working_dir,
            handle_id=f"handle-{sandbox_name or 'default'}",
        )

    def upload_file(self, handle, operation):  # noqa: ANN001 - fake protocol.
        self.calls.append(("upload", operation.local_path, operation.sandbox_path))
        if self.fail_step == "upload":
            raise RuntimeError("upload failed")

    def run_command(self, handle, operation):  # noqa: ANN001 - fake protocol.
        self.calls.append(("command", operation.worker_argv, operation.working_dir))
        return DaytonaClientCommandResult(
            exit_code=self.command_exit_code,
            stdout="ok" if self.command_exit_code == 0 else None,
            stderr="command failed" if self.command_exit_code != 0 else None,
            summary_text=f"client_command exit_code={self.command_exit_code}",
        )

    def download_file(self, handle, operation):  # noqa: ANN001 - fake protocol.
        self.calls.append(("download", operation.sandbox_path, operation.local_path))

    def close_sandbox(self, handle):  # noqa: ANN001 - fake protocol.
        self.calls.append(("close", handle.handle_id))


class DaytonaClientReportTests(unittest.TestCase):
    def test_module_imports_and_exports_are_available(self) -> None:
        import ow_eval.daytona_client_report as daytona_client_report

        self.assertIs(
            daytona_client_report.DaytonaClientExecutionReport,
            DaytonaClientExecutionReport,
        )
        self.assertIs(
            daytona_client_report.run_daytona_shard_job_plan_with_client_report,
            run_daytona_shard_job_plan_with_client_report,
        )

    def test_successful_fake_client_report_contains_batch_trace_and_plans(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _package, plan, plan_path = written_daytona_plan(temp_dir)
            client = RecordingClient()

            with patch(
                "ow_eval.daytona_executor.merge_evaluation_shard_result_files",
                return_value=fake_merge_result(),
            ):
                report = run_daytona_shard_job_plan_with_client_report(
                    plan_path,
                    client,
                )

            self.assertEqual(report.exit_code, 0)
            self.assertTrue(report.passed)
            self.assertEqual(report.plan_path, str(plan_path))
            self.assertEqual(
                tuple(result.job_id for result in report.batch_result.execution_results),
                tuple(spec.job_id for spec in plan.specs),
            )
            self.assertEqual(
                tuple(operation_plan.job_id for operation_plan in report.operation_plans),
                tuple(spec.job_id for spec in plan.specs),
            )
            self.assertEqual(
                [call[0] for call in client.calls],
                expected_call_steps_for_plan(plan),
            )
            self.assertEqual(
                len(report.client_event_trace),
                2 * len(expected_call_steps_for_plan(plan)),
            )
            self.assertIn("daytona_client_execution_report=COMPLETE", report.summary_text)
            self.assertIsNotNone(report.batch_result.merged_result)

    def test_preflight_failure_report_has_empty_trace_and_no_client_calls(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package, _plan, plan_path = written_daytona_plan(temp_dir)
            Path(package.jobs[0].manifest_path).unlink()
            client = RecordingClient()

            report = run_daytona_shard_job_plan_with_client_report(plan_path, client)

            self.assertEqual(report.exit_code, 2)
            self.assertFalse(report.passed)
            self.assertEqual(client.calls, [])
            self.assertEqual(report.client_event_trace, ())
            self.assertEqual(report.operation_plans, ())
            self.assertEqual(report.batch_result.execution_results, ())
            self.assertIn("preflight failed", report.error_text)

    def test_mid_run_command_failure_preserves_partial_trace_and_operation_plans(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _package, plan, plan_path = written_daytona_plan(temp_dir)
            client = RecordingClient(command_exit_code=9)

            report = run_daytona_shard_job_plan_with_client_report(plan_path, client)

            self.assertEqual(report.exit_code, 2)
            self.assertFalse(report.passed)
            self.assertEqual(len(report.batch_result.execution_results), 1)
            self.assertEqual(len(report.operation_plans), 1)
            self.assertEqual(report.operation_plans[0].job_id, plan.specs[0].job_id)
            self.assertIn("command failed", report.error_text)
            self.assertIn(("command", "error"), [
                (event.step, event.status)
                for event in report.client_event_trace
            ])
            self.assertNotIn("download", [call[0] for call in client.calls])
            self.assertEqual(client.calls[-1][0], "close")

    def test_client_exception_report_preserves_attempted_trace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _package, plan, plan_path = written_daytona_plan(temp_dir)
            client = RecordingClient(fail_step="upload")

            report = run_daytona_shard_job_plan_with_client_report(plan_path, client)

            self.assertEqual(report.exit_code, 2)
            self.assertEqual(len(report.batch_result.execution_results), 1)
            self.assertEqual(len(report.operation_plans), 1)
            self.assertEqual(report.operation_plans[0].job_id, plan.specs[0].job_id)
            self.assertIn("RuntimeError: upload failed", report.error_text)
            self.assertEqual(report.client_event_trace[0].step, "open")
            self.assertIn(("client", "error"), [
                (event.step, event.status)
                for event in report.client_event_trace
            ])

    def test_report_to_dict_is_json_safe_and_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _package, _plan, plan_path = written_daytona_plan(temp_dir)
            report = run_daytona_shard_job_plan_with_client_report(
                plan_path,
                RecordingClient(),
                merge_results=False,
            )

            decoded = json.loads(json.dumps(report.to_dict(), sort_keys=True))

            self.assertTrue(decoded["passed"])
            self.assertEqual(decoded["plan_path"], str(plan_path))
            self.assertEqual(
                decoded["batch_result"],
                report.batch_result.to_dict(),
            )
            self.assertEqual(
                decoded["client_event_trace"][0],
                report.client_event_trace[0].to_dict(),
            )
            self.assertEqual(
                decoded["operation_plans"][0],
                report.operation_plans[0].to_dict(),
            )

    def test_report_is_frozen_slotted_and_validates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _package, _plan, plan_path = written_daytona_plan(temp_dir)
            report = run_daytona_shard_job_plan_with_client_report(
                plan_path,
                RecordingClient(),
                merge_results=False,
            )

            with self.assertRaises(FrozenInstanceError):
                report.exit_code = 2  # type: ignore[misc]
            with self.assertRaises((AttributeError, TypeError)):
                report.extra = "nope"  # type: ignore[attr-defined]
            with self.assertRaisesRegex(ValueError, "client_event_trace"):
                DaytonaClientExecutionReport(
                    plan_path=str(plan_path),
                    batch_result=report.batch_result,
                    client_event_trace=[report.client_event_trace[0]],  # type: ignore[arg-type]
                    operation_plans=report.operation_plans,
                    exit_code=0,
                    summary_text="summary",
                )
            with self.assertRaisesRegex(ValueError, "operation_plans"):
                DaytonaClientExecutionReport(
                    plan_path=str(plan_path),
                    batch_result=report.batch_result,
                    client_event_trace=report.client_event_trace,
                    operation_plans=[report.operation_plans[0]],  # type: ignore[arg-type]
                    exit_code=0,
                    summary_text="summary",
                )
            with self.assertRaisesRegex(ValueError, "exit_code"):
                DaytonaClientExecutionReport(
                    plan_path=str(plan_path),
                    batch_result=report.batch_result,
                    client_event_trace=(),
                    operation_plans=(),
                    exit_code=True,  # type: ignore[arg-type]
                    summary_text="summary",
                )

    def test_report_layer_does_not_call_daytona_subprocess_or_run_matches(self) -> None:
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
                        report = run_daytona_shard_job_plan_with_client_report(
                            plan_path,
                            RecordingClient(),
                            merge_results=False,
                        )

            self.assertEqual(report.exit_code, 0)
            subprocess_run.assert_not_called()
            run_job.assert_not_called()
            official_runner.assert_not_called()
            self.assertNotIn("daytona", sys.modules)


if __name__ == "__main__":
    unittest.main()
