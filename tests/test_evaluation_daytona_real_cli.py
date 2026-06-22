"""Tests for the guarded real-Daytona execution CLI boundary."""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch

from ow_eval import (
    DAYTONA_SOURCE_MODE_SNAPSHOT,
    DaytonaClientCommandResult,
    DaytonaRealCliResult,
    DaytonaRealExecutionConfig,
    DaytonaSandboxHandle,
    DaytonaShardJobPlanConfig,
    ShardPlanConfig,
    build_daytona_shard_job_plan,
    build_evaluation_shard_plan,
    run_daytona_real_shard_jobs,
    run_daytona_real_shard_jobs_main,
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
            label_prefix="daytona-real-cli",
        ),
    )
    return write_evaluation_shard_job_package(plan)


def written_daytona_plan(
    temp_dir: str | Path,
    *,
    source_mode: str | None = DAYTONA_SOURCE_MODE_SNAPSHOT,
):
    package = packaged_index(temp_dir)
    config = None if source_mode is None else DaytonaShardJobPlanConfig(source_mode=source_mode)
    plan = build_daytona_shard_job_plan(package.index_path, config)
    plan_path = Path(temp_dir) / "daytona-plan.json"
    write_daytona_shard_job_plan(plan, plan_path)
    return package, plan, plan_path


class FakeSdkClient:
    def __init__(self, *, snapshot_commit: str | None = None) -> None:
        self.snapshot_commit = snapshot_commit
        self.calls: list[tuple[object, ...]] = []

    def open_sandbox(
        self,
        *,
        sandbox_name: str | None,
        working_dir: str,
    ) -> DaytonaSandboxHandle:
        self.calls.append(("open", sandbox_name, working_dir))
        return DaytonaSandboxHandle(
            sandbox_name=sandbox_name,
            working_dir=working_dir,
            handle_id=f"fake-{sandbox_name or 'default'}",
        )

    def upload_file(self, handle, operation):  # noqa: ANN001 - fake protocol.
        self.calls.append(("upload", operation.local_path, operation.sandbox_path))

    def run_command(self, handle, operation):  # noqa: ANN001 - fake protocol.
        self.calls.append(("command", operation.worker_argv, operation.working_dir))
        if ".ow-runtime-git-commit" in " ".join(operation.worker_argv):
            stdout = self.snapshot_commit or local_git_commit()
            return DaytonaClientCommandResult(
                exit_code=0,
                stdout=stdout + "\n",
                summary_text="fake snapshot commit command exit_code=0",
            )
        return DaytonaClientCommandResult(
            exit_code=0,
            stdout="ok",
            summary_text="fake real cli command exit_code=0",
        )

    def download_file(self, handle, operation):  # noqa: ANN001 - fake protocol.
        self.calls.append(("download", operation.sandbox_path, operation.local_path))

    def close_sandbox(self, handle):  # noqa: ANN001 - fake protocol.
        self.calls.append(("close", handle.handle_id))


def ready_env() -> dict[str, str]:
    return {
        "OW_EVAL_ALLOW_REAL_DAYTONA": "1",
        "DAYTONA_API_KEY_ENV_VAR": "TOKEN",
        "TOKEN": "secret",
        "DAYTONA_SOURCE_MODE": DAYTONA_SOURCE_MODE_SNAPSHOT,
    }


def local_git_commit() -> str:
    completed = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def expected_call_steps_for_real_plan(plan) -> list[str]:
    steps: list[str] = []
    for spec in plan.specs:
        steps.extend(
            ["open", "command"]
            + ["upload"] * len(spec.expected_upload_paths)
            + ["command"]
            + ["download"] * len(spec.expected_download_paths)
            + ["close"]
        )
    return steps


class DaytonaRealCliTests(unittest.TestCase):
    def test_module_imports_and_exports_are_available(self) -> None:
        import ow_eval.daytona_real_cli as daytona_real_cli

        self.assertIs(daytona_real_cli.DaytonaRealCliResult, DaytonaRealCliResult)
        self.assertIs(
            daytona_real_cli.run_daytona_real_shard_jobs,
            run_daytona_real_shard_jobs,
        )
        self.assertIs(daytona_real_cli.main, run_daytona_real_shard_jobs_main)

    def test_default_invocation_fails_before_sdk_import(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _package, _plan, plan_path = written_daytona_plan(temp_dir)
            importer_calls: list[str] = []

            result = run_daytona_real_shard_jobs(
                plan_path,
                sdk_importer=lambda name: importer_calls.append(name) or object(),
            )

            self.assertEqual(result.exit_code, 2)
            self.assertFalse(result.passed)
            self.assertIsNone(result.report)
            self.assertIn("--allow-real-daytona", result.error_text)
            self.assertEqual(importer_calls, [])

    def test_env_ready_without_cli_allow_still_fails_before_sdk_import(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _package, _plan, plan_path = written_daytona_plan(temp_dir)
            importer_calls: list[str] = []

            result = run_daytona_real_shard_jobs(
                plan_path,
                env=ready_env(),
                sdk_importer=lambda name: importer_calls.append(name) or object(),
            )

            self.assertEqual(result.exit_code, 2)
            self.assertTrue(result.readiness.passed)
            self.assertIn("--allow-real-daytona", result.error_text)
            self.assertEqual(importer_calls, [])

    def test_cli_allow_without_required_env_fails_before_sdk_import(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _package, _plan, plan_path = written_daytona_plan(temp_dir)
            importer_calls: list[str] = []

            result = run_daytona_real_shard_jobs(
                plan_path,
                allow_real_daytona=True,
                env={},
                sdk_importer=lambda name: importer_calls.append(name) or object(),
            )

            self.assertEqual(result.exit_code, 2)
            self.assertFalse(result.readiness.passed)
            self.assertIn("missing env vars", result.error_text)
            self.assertEqual(importer_calls, [])

    def test_explicit_allow_and_ready_env_run_fake_sdk_through_report_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _package, plan, plan_path = written_daytona_plan(temp_dir)
            fake = FakeSdkClient()
            importer_calls: list[str] = []
            factory_calls: list[tuple[object, DaytonaRealExecutionConfig]] = []

            def fake_importer(name: str) -> object:
                importer_calls.append(name)
                return object()

            def fake_factory(module, config):  # noqa: ANN001 - fake factory.
                factory_calls.append((module, config))
                return fake

            result = run_daytona_real_shard_jobs(
                plan_path,
                allow_real_daytona=True,
                env=ready_env(),
                sdk_importer=fake_importer,
                sdk_client_factory=fake_factory,
            )

            self.assertEqual(result.exit_code, 0)
            self.assertTrue(result.passed)
            self.assertIsNotNone(result.report)
            self.assertEqual(result.expected_git_commit, local_git_commit())
            self.assertEqual(importer_calls, ["daytona"])
            self.assertEqual(len(factory_calls), 1)
            self.assertEqual(
                tuple(execution.job_id for execution in result.report.batch_result.execution_results),
                tuple(spec.job_id for spec in plan.specs),
            )
            self.assertEqual(
                [call[0] for call in fake.calls],
                expected_call_steps_for_real_plan(plan),
            )

    def test_real_execution_fails_before_upload_when_snapshot_commit_mismatches(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _package, _plan, plan_path = written_daytona_plan(temp_dir)
            fake = FakeSdkClient(snapshot_commit="stale-snapshot")

            result = run_daytona_real_shard_jobs(
                plan_path,
                allow_real_daytona=True,
                env=ready_env(),
                sdk_importer=lambda name: object(),
                sdk_client_factory=lambda module, config: fake,
            )

            self.assertEqual(result.exit_code, 2)
            self.assertFalse(result.passed)
            self.assertIn("remote snapshot commit mismatch", result.error_text)
            self.assertEqual(
                [call[0] for call in fake.calls],
                ["open", "command", "close"],
            )
            self.assertNotIn("upload", [call[0] for call in fake.calls])

    def test_json_output_is_deterministic_report_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _package, _plan, plan_path = written_daytona_plan(temp_dir)
            output_path = Path(temp_dir) / "nested" / "real-report.json"
            fake = FakeSdkClient()

            result = run_daytona_real_shard_jobs(
                plan_path,
                allow_real_daytona=True,
                env=ready_env(),
                sdk_importer=lambda name: object(),
                sdk_client_factory=lambda module, config: fake,
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

    def test_preflight_options_flow_through(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package, _plan, plan_path = written_daytona_plan(temp_dir)
            Path(package.jobs[0].job_path).unlink()
            fake = FakeSdkClient()

            result = run_daytona_real_shard_jobs(
                plan_path,
                allow_real_daytona=True,
                env=ready_env(),
                require_upload_paths_exist=False,
                sdk_importer=lambda name: object(),
                sdk_client_factory=lambda module, config: fake,
            )

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(
                result.report.batch_result.preflight_result.missing_upload_paths,
                (),
            )

    def test_cli_success_failure_and_help(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _package, _plan, plan_path = written_daytona_plan(temp_dir)
            stdout = io.StringIO()
            stderr = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                with contextlib.redirect_stderr(stderr):
                    exit_code = run_daytona_real_shard_jobs_main([str(plan_path)])

            self.assertEqual(exit_code, 2)
            self.assertIn("daytona_real_cli=ERROR", stdout.getvalue())
            self.assertIn("--allow-real-daytona", stderr.getvalue())

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            with self.assertRaises(SystemExit) as raised:
                run_daytona_real_shard_jobs_main(["--help"])
        self.assertEqual(raised.exception.code, 0)
        self.assertIn("real-Daytona", stdout.getvalue())

    def test_result_object_is_frozen_slotted_validated_and_json_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _package, _plan, plan_path = written_daytona_plan(temp_dir)
            result = run_daytona_real_shard_jobs(plan_path)

            with self.assertRaises(FrozenInstanceError):
                result.exit_code = 0  # type: ignore[misc]
            with self.assertRaises((AttributeError, TypeError)):
                result.extra = "nope"  # type: ignore[attr-defined]
            with self.assertRaisesRegex(ValueError, "allow_real_daytona"):
                DaytonaRealCliResult(
                    plan_path=str(plan_path),
                    allow_real_daytona="yes",  # type: ignore[arg-type]
                    readiness=result.readiness,
                    summary_text="summary",
                )
            decoded = json.loads(json.dumps(result.to_dict(), sort_keys=True))
            self.assertEqual(decoded["plan_path"], str(plan_path))
            self.assertFalse(decoded["passed"])

    def test_real_cli_does_not_import_daytona_spawn_subprocess_or_run_matches_when_blocked(self) -> None:
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
                        result = run_daytona_real_shard_jobs(plan_path)

            self.assertEqual(result.exit_code, 2)
            subprocess_run.assert_not_called()
            run_job.assert_not_called()
            official_runner.assert_not_called()
            self.assertNotIn("daytona", sys.modules)


if __name__ == "__main__":
    unittest.main()
