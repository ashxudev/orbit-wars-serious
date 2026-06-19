"""Tests for the real-Daytona SDK adapter skeleton."""

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
    DaytonaRealExecutionConfig,
    DaytonaSandboxHandle,
    DaytonaSdkAdapter,
    DaytonaSdkAdapterConfig,
    DaytonaSdkUnavailableError,
    DaytonaUploadOperation,
    DaytonaCommandOperation,
    DaytonaDownloadOperation,
    ShardPlanConfig,
    build_daytona_shard_job_plan,
    build_evaluation_shard_plan,
    run_daytona_shard_job_plan_with_client_report,
    validate_daytona_real_execution_readiness,
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
            label_prefix="daytona-sdk",
        ),
    )
    return write_evaluation_shard_job_package(plan)


def written_daytona_plan(temp_dir: str | Path):
    package = packaged_index(temp_dir)
    plan = build_daytona_shard_job_plan(package.index_path)
    plan_path = Path(temp_dir) / "daytona-plan.json"
    write_daytona_shard_job_plan(plan, plan_path)
    return package, plan, plan_path


class FakeSdkClient:
    def __init__(self, *, command_exit_code: int = 0) -> None:
        self.command_exit_code = command_exit_code
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

    def upload_file(self, handle, operation):  # noqa: ANN001 - fake SDK protocol.
        self.calls.append(("upload", operation.local_path, operation.sandbox_path))

    def run_command(self, handle, operation):  # noqa: ANN001 - fake SDK protocol.
        self.calls.append(("command", operation.worker_argv, operation.working_dir))
        return DaytonaClientCommandResult(
            exit_code=self.command_exit_code,
            stdout="ok" if self.command_exit_code == 0 else None,
            stderr="fake command failed" if self.command_exit_code != 0 else None,
            summary_text=f"fake_sdk_command exit_code={self.command_exit_code}",
        )

    def download_file(self, handle, operation):  # noqa: ANN001 - fake SDK protocol.
        self.calls.append(("download", operation.sandbox_path, operation.local_path))

    def close_sandbox(self, handle):  # noqa: ANN001 - fake SDK protocol.
        self.calls.append(("close", handle.handle_id))


class MissingMethodsClient:
    pass


def ready_adapter_config(fake_client: object) -> DaytonaSdkAdapterConfig:
    config = DaytonaRealExecutionConfig(
        allow_real_daytona=True,
        api_key_env_var="TOKEN",
    )
    readiness = validate_daytona_real_execution_readiness(
        config,
        env={"TOKEN": "secret"},
    )
    return DaytonaSdkAdapterConfig(
        real_execution_config=config,
        readiness=readiness,
        sdk_client=fake_client,
    )


class DaytonaSdkAdapterTests(unittest.TestCase):
    def test_module_imports_and_exports_are_available(self) -> None:
        import ow_eval.daytona_sdk_adapter as daytona_sdk_adapter

        self.assertIs(daytona_sdk_adapter.DaytonaSdkAdapter, DaytonaSdkAdapter)
        self.assertIs(
            daytona_sdk_adapter.DaytonaSdkAdapterConfig,
            DaytonaSdkAdapterConfig,
        )
        self.assertIs(
            daytona_sdk_adapter.DaytonaSdkUnavailableError,
            DaytonaSdkUnavailableError,
        )

    def test_adapter_without_injected_client_fails_closed_without_daytona_import(self) -> None:
        sys.modules.pop("daytona", None)
        adapter = DaytonaSdkAdapter()

        with self.assertRaisesRegex(
            DaytonaSdkUnavailableError,
            "not ready for real execution",
        ):
            adapter.open_sandbox(sandbox_name="sandbox", working_dir="/workspace")

        self.assertEqual(adapter.readiness.exit_code, 2)
        self.assertNotIn("daytona", sys.modules)

    def test_blocked_readiness_prevents_injected_client_bypass(self) -> None:
        fake = FakeSdkClient()
        adapter = DaytonaSdkAdapter(
            DaytonaSdkAdapterConfig(
                real_execution_config=DaytonaRealExecutionConfig(),
                sdk_client=fake,
            )
        )

        with self.assertRaisesRegex(
            DaytonaSdkUnavailableError,
            "Daytona SDK adapter is not ready for real execution",
        ):
            adapter.open_sandbox(sandbox_name="sandbox", working_dir="/workspace")

        self.assertEqual(fake.calls, [])

    def test_injected_fake_client_receives_protocol_calls_in_order(self) -> None:
        fake = FakeSdkClient()
        adapter = DaytonaSdkAdapter(ready_adapter_config(fake))
        handle = adapter.open_sandbox(
            sandbox_name="sandbox",
            working_dir="/workspace",
        )

        adapter.upload_file(
            handle,
            DaytonaUploadOperation(
                local_path="/local/input.json",
                sandbox_path="/workspace/input.json",
            ),
        )
        command_result = adapter.run_command(
            handle,
            DaytonaCommandOperation(
                worker_argv=("python", "worker.py"),
                working_dir="/workspace",
            ),
        )
        adapter.download_file(
            handle,
            DaytonaDownloadOperation(
                sandbox_path="/workspace/result.json",
                local_path="/local/result.json",
            ),
        )
        adapter.close_sandbox(handle)

        self.assertEqual(command_result.exit_code, 0)
        self.assertEqual(
            [call[0] for call in fake.calls],
            ["open", "upload", "command", "download", "close"],
        )
        self.assertEqual(fake.calls[2][1], ("python", "worker.py"))

    def test_missing_fake_sdk_methods_raise_deterministic_unavailable_error(self) -> None:
        adapter = DaytonaSdkAdapter(
            ready_adapter_config(MissingMethodsClient())
        )

        with self.assertRaisesRegex(
            DaytonaSdkUnavailableError,
            "does not provide open_sandbox",
        ):
            adapter.open_sandbox(sandbox_name=None, working_dir="/workspace")

    def test_bad_fake_sdk_return_types_raise_deterministic_errors(self) -> None:
        class BadOpenClient(FakeSdkClient):
            def open_sandbox(self, *, sandbox_name, working_dir):  # noqa: ANN001
                return object()

        class BadCommandClient(FakeSdkClient):
            def run_command(self, handle, operation):  # noqa: ANN001
                return object()

        bad_open = DaytonaSdkAdapter(ready_adapter_config(BadOpenClient()))
        with self.assertRaisesRegex(
            DaytonaSdkUnavailableError,
            "open_sandbox must return DaytonaSandboxHandle",
        ):
            bad_open.open_sandbox(sandbox_name=None, working_dir="/workspace")

        bad_command = DaytonaSdkAdapter(ready_adapter_config(BadCommandClient()))
        handle = DaytonaSandboxHandle(
            sandbox_name=None,
            working_dir="/workspace",
            handle_id="handle",
        )
        with self.assertRaisesRegex(
            DaytonaSdkUnavailableError,
            "run_command must return DaytonaClientCommandResult",
        ):
            bad_command.run_command(
                handle,
                DaytonaCommandOperation(
                    worker_argv=("python", "worker.py"),
                    working_dir="/workspace",
                ),
            )

    def test_adapter_works_with_existing_client_report_boundary_using_fake_sdk(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _package, plan, plan_path = written_daytona_plan(temp_dir)
            fake = FakeSdkClient()
            adapter = DaytonaSdkAdapter(ready_adapter_config(fake))

            report = run_daytona_shard_job_plan_with_client_report(
                plan_path,
                adapter,
                merge_results=False,
            )

            self.assertEqual(report.exit_code, 0)
            self.assertEqual(
                tuple(result.job_id for result in report.batch_result.execution_results),
                tuple(spec.job_id for spec in plan.specs),
            )
            self.assertEqual(
                [call[0] for call in fake.calls],
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

    def test_config_is_frozen_slotted_validated_and_json_safe(self) -> None:
        fake = FakeSdkClient()
        config = DaytonaSdkAdapterConfig(
            real_execution_config=DaytonaRealExecutionConfig(
                allow_real_daytona=True,
                api_key_env_var="TOKEN",
            ),
            sdk_client=fake,
        )

        with self.assertRaises(FrozenInstanceError):
            config.sdk_client = None  # type: ignore[misc]
        with self.assertRaises((AttributeError, TypeError)):
            config.extra = "nope"  # type: ignore[attr-defined]
        with self.assertRaisesRegex(ValueError, "real_execution_config"):
            DaytonaSdkAdapterConfig(real_execution_config=object())  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "readiness"):
            DaytonaSdkAdapterConfig(readiness=object())  # type: ignore[arg-type]

        decoded = json.loads(json.dumps(config.to_dict(), sort_keys=True))
        self.assertTrue(decoded["has_sdk_client"])
        self.assertEqual(decoded["real_execution_config"]["api_key_env_var"], "TOKEN")

    def test_adapter_does_not_import_daytona_spawn_subprocess_or_run_matches(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _package, _plan, plan_path = written_daytona_plan(temp_dir)
            fake = FakeSdkClient()
            adapter = DaytonaSdkAdapter(ready_adapter_config(fake))
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
                            adapter,
                            merge_results=False,
                        )

            self.assertEqual(report.exit_code, 0)
            subprocess_run.assert_not_called()
            run_job.assert_not_called()
            official_runner.assert_not_called()
            self.assertNotIn("daytona", sys.modules)


if __name__ == "__main__":
    unittest.main()
