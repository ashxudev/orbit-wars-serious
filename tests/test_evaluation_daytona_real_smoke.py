"""Tests for guarded real-Daytona smoke diagnostics."""

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
    DaytonaClientCommandResult,
    DaytonaRealSmokeEvent,
    DaytonaRealSmokeResult,
    DaytonaSandboxHandle,
    run_daytona_real_smoke,
    run_daytona_real_smoke_main,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class FakeSmokeClient:
    def __init__(self, command_result: DaytonaClientCommandResult | None = None) -> None:
        self.command_result = command_result or DaytonaClientCommandResult(
            stdout="daytona_smoke=OK\n",
            summary_text="fake_smoke_command exit_code=0",
        )
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
            handle_id="fake-smoke",
        )

    def upload_file(self, handle, operation):  # noqa: ANN001 - protocol stub.
        self.calls.append(("upload", operation.local_path, operation.sandbox_path))

    def run_command(self, handle, operation):  # noqa: ANN001 - protocol stub.
        self.calls.append(("command", operation.worker_argv, operation.working_dir))
        return self.command_result

    def download_file(self, handle, operation):  # noqa: ANN001 - protocol stub.
        self.calls.append(("download", operation.sandbox_path, operation.local_path))

    def close_sandbox(self, handle):  # noqa: ANN001 - protocol stub.
        self.calls.append(("close", handle.handle_id))


class TransportFailureClient(FakeSmokeClient):
    def run_command(self, handle, operation):  # noqa: ANN001 - protocol stub.
        self.calls.append(("command", operation.worker_argv, operation.working_dir))
        raise RuntimeError("proxy disconnected")


def ready_env() -> dict[str, str]:
    return {
        "OW_EVAL_ALLOW_REAL_DAYTONA": "1",
        "DAYTONA_API_KEY_ENV_VAR": "TOKEN",
        "TOKEN": "secret",
        "DAYTONA_WORKING_DIR": "/workspace/orbit-wars-serious",
    }


class DaytonaRealSmokeTests(unittest.TestCase):
    def test_exports_are_available(self) -> None:
        import ow_eval.daytona_real_smoke as daytona_real_smoke

        self.assertIs(daytona_real_smoke.DaytonaRealSmokeEvent, DaytonaRealSmokeEvent)
        self.assertIs(daytona_real_smoke.DaytonaRealSmokeResult, DaytonaRealSmokeResult)
        self.assertIs(daytona_real_smoke.run_daytona_real_smoke, run_daytona_real_smoke)
        self.assertIs(daytona_real_smoke.main, run_daytona_real_smoke_main)

    def test_blocked_without_cli_allow_does_not_import_sdk(self) -> None:
        importer_calls: list[str] = []

        result = run_daytona_real_smoke(
            env=ready_env(),
            sdk_importer=lambda name: importer_calls.append(name) or object(),
        )

        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.diagnosis, "blocked_missing_cli_allow")
        self.assertIn("--allow-real-daytona", result.error_text)
        self.assertEqual(result.events, ())
        self.assertEqual(importer_calls, [])

    def test_blocked_readiness_does_not_import_sdk(self) -> None:
        importer_calls: list[str] = []

        result = run_daytona_real_smoke(
            allow_real_daytona=True,
            env={},
            sdk_importer=lambda name: importer_calls.append(name) or object(),
        )

        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.diagnosis, "blocked_readiness")
        self.assertIn("missing env vars", result.error_text)
        self.assertEqual(result.events, ())
        self.assertEqual(importer_calls, [])

    def test_fake_success_runs_open_command_close_only(self) -> None:
        fake = FakeSmokeClient()

        result = run_daytona_real_smoke(
            allow_real_daytona=True,
            env=ready_env(),
            sandbox_name="smoke",
            worker_argv=("python", "-c", "print('ok')"),
            sdk_importer=lambda name: object(),
            sdk_client_factory=lambda module, config: fake,
        )

        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.passed)
        self.assertEqual(result.diagnosis, "smoke_passed")
        self.assertEqual(
            [event.step for event in result.events],
            ["open", "open", "command", "command", "close", "close"],
        )
        self.assertEqual(
            [call[0] for call in fake.calls],
            ["open", "command", "close"],
        )
        self.assertEqual(fake.calls[1][1], ("python", "-c", "print('ok')"))

    def test_nonzero_command_classifies_snapshot_command_failure_and_closes(self) -> None:
        fake = FakeSmokeClient(
            DaytonaClientCommandResult(
                exit_code=7,
                stderr="missing module",
                summary_text="fake_smoke_command exit_code=7",
            )
        )

        result = run_daytona_real_smoke(
            allow_real_daytona=True,
            env=ready_env(),
            sdk_importer=lambda name: object(),
            sdk_client_factory=lambda module, config: fake,
        )

        self.assertEqual(result.exit_code, 7)
        self.assertEqual(result.diagnosis, "snapshot_command_failed")
        self.assertEqual(result.error_text, "missing module")
        self.assertEqual(fake.calls[-1][0], "close")

    def test_transport_exception_classifies_command_transport_failure_and_closes(self) -> None:
        fake = TransportFailureClient()

        result = run_daytona_real_smoke(
            allow_real_daytona=True,
            env=ready_env(),
            sdk_importer=lambda name: object(),
            sdk_client_factory=lambda module, config: fake,
        )

        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.diagnosis, "command_transport_failed")
        self.assertIn("proxy disconnected", result.error_text)
        self.assertEqual(fake.calls[-1][0], "close")

    def test_json_output_and_cli_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "smoke.json"
            fake = FakeSmokeClient()

            result = run_daytona_real_smoke(
                allow_real_daytona=True,
                env=ready_env(),
                sdk_importer=lambda name: object(),
                sdk_client_factory=lambda module, config: fake,
                json_output=output_path,
            )

            self.assertEqual(result.json_output_path, str(output_path))
            decoded = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(decoded["diagnosis"], "smoke_passed")
            self.assertEqual(decoded["exit_code"], 0)

        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            with contextlib.redirect_stderr(stderr):
                exit_code = run_daytona_real_smoke_main([])
        self.assertEqual(exit_code, 2)
        self.assertIn("daytona_real_smoke=ERROR", stdout.getvalue())
        self.assertIn("--allow-real-daytona", stderr.getvalue())

    def test_script_wrapper_help_imports_repo_package(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "run_daytona_real_smoke.py"),
                "--help",
            ],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0)
        self.assertIn("real-Daytona smoke", completed.stdout)

    def test_result_objects_are_frozen_slotted_validated_and_json_safe(self) -> None:
        result = run_daytona_real_smoke()

        with self.assertRaises(FrozenInstanceError):
            result.exit_code = 0  # type: ignore[misc]
        with self.assertRaises((AttributeError, TypeError)):
            result.extra = "nope"  # type: ignore[attr-defined]
        with self.assertRaisesRegex(ValueError, "worker_argv"):
            run_daytona_real_smoke(worker_argv=())  # type: ignore[arg-type]
        decoded = json.loads(json.dumps(result.to_dict(), sort_keys=True))
        self.assertEqual(decoded["diagnosis"], "blocked_missing_cli_allow")

    def test_blocked_smoke_does_not_spawn_subprocess_or_run_matches(self) -> None:
        sys.modules.pop("daytona", None)

        with patch("subprocess.run") as subprocess_run:
            with patch("ow_eval.shard_job_runner.run_evaluation_shard_job") as run_job:
                with patch("ow_eval.official_runner.run_official_match") as run_match:
                    result = run_daytona_real_smoke()

        self.assertEqual(result.exit_code, 2)
        subprocess_run.assert_not_called()
        run_job.assert_not_called()
        run_match.assert_not_called()
        self.assertNotIn("daytona", sys.modules)


if __name__ == "__main__":
    unittest.main()
