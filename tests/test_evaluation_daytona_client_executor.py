"""Tests for injected Daytona-like client executor adapter."""

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
    DaytonaClientExecutor,
    DaytonaSandboxClient,
    DaytonaSandboxHandle,
    DaytonaShardExecutionRequest,
    ShardPlanConfig,
    build_daytona_shard_job_plan,
    build_evaluation_shard_plan,
    run_daytona_shard_job_plan_with_client,
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
            label_prefix="daytona-client",
        ),
    )
    return write_evaluation_shard_job_package(plan)


def written_daytona_plan(temp_dir: str | Path):
    package = packaged_index(temp_dir)
    plan = build_daytona_shard_job_plan(package.index_path)
    plan_path = Path(temp_dir) / "daytona-plan.json"
    write_daytona_shard_job_plan(plan, plan_path)
    return package, plan, plan_path


def execution_requests(temp_dir: str | Path):
    _package, plan, _plan_path = written_daytona_plan(temp_dir)
    return tuple(
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
        if self.fail_step == "command_raise":
            raise RuntimeError("command raised")
        return DaytonaClientCommandResult(
            exit_code=self.command_exit_code,
            stdout="ok" if self.command_exit_code == 0 else None,
            stderr="command failed" if self.command_exit_code != 0 else None,
            summary_text=(
                f"client_command exit_code={self.command_exit_code} "
                f"argv={len(operation.worker_argv)}"
            ),
        )

    def download_file(self, handle, operation):  # noqa: ANN001 - fake protocol.
        self.calls.append(("download", operation.sandbox_path, operation.local_path))
        if self.fail_step == "download":
            raise RuntimeError("download failed")

    def close_sandbox(self, handle):  # noqa: ANN001 - fake protocol.
        self.calls.append(("close", handle.handle_id))
        if self.fail_step == "close":
            raise RuntimeError("close failed")


class DaytonaClientExecutorTests(unittest.TestCase):
    def test_module_imports_and_exports_are_available(self) -> None:
        import ow_eval.daytona_client_executor as daytona_client_executor

        self.assertIs(
            daytona_client_executor.DaytonaSandboxClient,
            DaytonaSandboxClient,
        )
        self.assertIs(
            daytona_client_executor.DaytonaSandboxHandle,
            DaytonaSandboxHandle,
        )
        self.assertIs(
            daytona_client_executor.DaytonaClientCommandResult,
            DaytonaClientCommandResult,
        )
        self.assertIs(
            daytona_client_executor.DaytonaClientExecutionEvent,
            DaytonaClientExecutionEvent,
        )
        self.assertIs(
            daytona_client_executor.DaytonaClientExecutor,
            DaytonaClientExecutor,
        )
        self.assertIs(
            daytona_client_executor.run_daytona_shard_job_plan_with_client,
            run_daytona_shard_job_plan_with_client,
        )

    def test_success_preserves_client_operation_order_and_event_trace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            request = execution_requests(temp_dir)[0]
            client = RecordingClient()
            executor = DaytonaClientExecutor(client)

            result = executor.execute(request)

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.shard_result_path, request.local_shard_result_path)
            self.assertEqual(
                [call[0] for call in client.calls],
                ["open", "upload", "upload", "command", "download", "close"],
            )
            self.assertEqual(client.calls[3][1], request.worker_argv)
            self.assertEqual(len(executor.operation_plans), 1)
            self.assertEqual(executor.operation_plans[0].job_id, request.job_id)
            self.assertEqual(
                [(event.step, event.status) for event in executor.event_trace],
                [
                    ("open", "attempted"),
                    ("open", "completed"),
                    ("upload", "attempted"),
                    ("upload", "completed"),
                    ("upload", "attempted"),
                    ("upload", "completed"),
                    ("command", "attempted"),
                    ("command", "completed"),
                    ("download", "attempted"),
                    ("download", "completed"),
                    ("close", "attempted"),
                    ("close", "completed"),
                ],
            )

    def test_command_failure_skips_download_closes_and_returns_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            request = execution_requests(temp_dir)[0]
            client = RecordingClient(command_exit_code=9)
            executor = DaytonaClientExecutor(client)

            result = executor.execute(request)

            self.assertEqual(result.exit_code, 9)
            self.assertIsNone(result.shard_result_path)
            self.assertIn("command failed", result.error_text)
            self.assertNotIn("download", [call[0] for call in client.calls])
            self.assertEqual(client.calls[-1][0], "close")
            self.assertIn(("command", "error"), [
                (event.step, event.status)
                for event in executor.event_trace
            ])

    def test_upload_failure_closes_and_returns_structured_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            request = execution_requests(temp_dir)[0]
            client = RecordingClient(fail_step="upload")
            executor = DaytonaClientExecutor(client)

            result = executor.execute(request)

            self.assertEqual(result.exit_code, 2)
            self.assertIsNone(result.shard_result_path)
            self.assertIn("RuntimeError: upload failed", result.error_text)
            self.assertNotIn("command", [call[0] for call in client.calls])
            self.assertEqual(client.calls[-1][0], "close")

    def test_download_failure_closes_and_returns_structured_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            request = execution_requests(temp_dir)[0]
            client = RecordingClient(fail_step="download")
            executor = DaytonaClientExecutor(client)

            result = executor.execute(request)

            self.assertEqual(result.exit_code, 2)
            self.assertIn("RuntimeError: download failed", result.error_text)
            self.assertEqual(client.calls[-1][0], "close")

    def test_close_failure_returns_nonzero_after_otherwise_successful_steps(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            request = execution_requests(temp_dir)[0]
            client = RecordingClient(fail_step="close")
            executor = DaytonaClientExecutor(client)

            result = executor.execute(request)

            self.assertEqual(result.exit_code, 2)
            self.assertIsNone(result.shard_result_path)
            self.assertIn("RuntimeError: close failed", result.error_text)
            self.assertEqual(executor.event_trace[-1].step, "close")
            self.assertEqual(executor.event_trace[-1].status, "error")

    def test_helper_runs_validated_plan_through_client_executor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _package, plan, plan_path = written_daytona_plan(temp_dir)
            client = RecordingClient()

            result = run_daytona_shard_job_plan_with_client(
                plan_path,
                client,
                merge_results=False,
            )

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(
                tuple(execution.job_id for execution in result.execution_results),
                tuple(spec.job_id for spec in plan.specs),
            )
            self.assertEqual(
                [call[0] for call in client.calls],
                [
                    "open",
                    "upload",
                    "upload",
                    "command",
                    "download",
                    "close",
                    "open",
                    "upload",
                    "upload",
                    "command",
                    "download",
                    "close",
                ],
            )

    def test_preflight_failure_prevents_client_calls(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package, _plan, plan_path = written_daytona_plan(temp_dir)
            Path(package.jobs[0].manifest_path).unlink()
            client = RecordingClient()

            result = run_daytona_shard_job_plan_with_client(plan_path, client)

            self.assertEqual(result.exit_code, 2)
            self.assertEqual(client.calls, [])
            self.assertIn("preflight failed", result.error_text)

    def test_support_dataclasses_are_frozen_slotted_validated_and_json_safe(self) -> None:
        handle = DaytonaSandboxHandle(
            sandbox_name="sandbox",
            working_dir="/workspace",
            handle_id="handle-1",
        )
        command_result = DaytonaClientCommandResult(
            exit_code=0,
            stdout="ok",
            summary_text="command complete",
        )
        event = DaytonaClientExecutionEvent(
            job_id="job-0000",
            shard_id="shard-0000",
            label="label",
            sandbox_name="sandbox",
            step="open",
            status="completed",
            detail="handle-1",
            exit_code=0,
        )

        with self.assertRaises(FrozenInstanceError):
            handle.handle_id = "changed"  # type: ignore[misc]
        with self.assertRaises((AttributeError, TypeError)):
            event.extra = "nope"  # type: ignore[attr-defined]
        with self.assertRaisesRegex(ValueError, "handle_id"):
            DaytonaSandboxHandle(
                sandbox_name=None,
                working_dir="/workspace",
                handle_id="",
            )
        with self.assertRaisesRegex(ValueError, "exit_code"):
            DaytonaClientCommandResult(
                exit_code=True,  # type: ignore[arg-type]
                summary_text="summary",
            )
        with self.assertRaisesRegex(ValueError, "detail"):
            DaytonaClientExecutionEvent(
                job_id="job",
                shard_id="shard",
                label="label",
                sandbox_name=None,
                step="open",
                status="completed",
                detail="",
            )

        decoded = json.loads(json.dumps({
            "handle": handle.to_dict(),
            "command_result": command_result.to_dict(),
            "event": event.to_dict(),
        }, sort_keys=True))
        self.assertEqual(decoded["handle"]["handle_id"], "handle-1")
        self.assertTrue(decoded["command_result"]["passed"])
        self.assertEqual(decoded["event"]["step"], "open")

    def test_client_executor_does_not_call_daytona_subprocess_or_run_matches(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            request = execution_requests(temp_dir)[0]
            client = RecordingClient()
            executor = DaytonaClientExecutor(client)
            sys.modules.pop("daytona", None)

            with patch("subprocess.run") as subprocess_run:
                with patch(
                    "ow_eval.shard_job_runner.run_evaluation_shard_job",
                ) as run_job:
                    with patch(
                        "ow_eval.official_runner.run_official_match",
                    ) as official_runner:
                        result = executor.execute(request)

            self.assertEqual(result.exit_code, 0)
            subprocess_run.assert_not_called()
            run_job.assert_not_called()
            official_runner.assert_not_called()
            self.assertNotIn("daytona", sys.modules)


if __name__ == "__main__":
    unittest.main()
