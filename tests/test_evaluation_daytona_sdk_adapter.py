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
    DaytonaSdkProtocolClient,
    DaytonaSdkUnavailableError,
    DaytonaUploadOperation,
    DaytonaCommandOperation,
    DaytonaDownloadOperation,
    ShardPlanConfig,
    build_daytona_sdk_protocol_client,
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


class FakeLowLevelHandle:
    def __init__(self, *, handle_id: str, sandbox_name: str | None, working_dir: str) -> None:
        self.handle_id = handle_id
        self.sandbox_name = sandbox_name
        self.working_dir = working_dir


class FakeLowLevelCommandResult:
    def __init__(self, *, exit_code: int = 0) -> None:
        self.exit_code = exit_code
        self.stdout = "low-level ok" if exit_code == 0 else None
        self.stderr = "low-level failed" if exit_code != 0 else None


class FakeLowLevelSdkClient:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    def open_sandbox(self, *, sandbox_name, working_dir):  # noqa: ANN001
        self.calls.append(("open", sandbox_name, working_dir))
        return FakeLowLevelHandle(
            handle_id=f"low-{sandbox_name or 'default'}",
            sandbox_name=sandbox_name,
            working_dir=working_dir,
        )

    def upload_file(self, handle, local_path, sandbox_path):  # noqa: ANN001
        self.calls.append(("upload", handle.handle_id, local_path, sandbox_path))

    def run_command(self, handle, worker_argv, working_dir):  # noqa: ANN001
        self.calls.append(("command", handle.handle_id, worker_argv, working_dir))
        return FakeLowLevelCommandResult()

    def download_file(self, handle, sandbox_path, local_path):  # noqa: ANN001
        self.calls.append(("download", handle.handle_id, sandbox_path, local_path))

    def close_sandbox(self, handle):  # noqa: ANN001
        self.calls.append(("close", handle.handle_id))


class FakeSdkModule:
    def __init__(self, client: object | None = None) -> None:
        self.client = client if client is not None else FakeLowLevelSdkClient()
        self.created_configs: list[DaytonaRealExecutionConfig] = []

    def create_client(self, config: DaytonaRealExecutionConfig):
        self.created_configs.append(config)
        return self.client


def ready_adapter_config(
    fake_client: object | None = None,
    *,
    sdk_module_name: str = "fake_daytona",
    sdk_importer=None,  # noqa: ANN001 - tests pass simple fake callables.
    sdk_client_factory=None,  # noqa: ANN001 - tests pass simple fake callables.
) -> DaytonaSdkAdapterConfig:
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
        sdk_module_name=sdk_module_name,
        sdk_importer=sdk_importer,
        sdk_client_factory=sdk_client_factory,
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
            daytona_sdk_adapter.DaytonaSdkProtocolClient,
            DaytonaSdkProtocolClient,
        )
        self.assertIs(
            daytona_sdk_adapter.DaytonaSdkUnavailableError,
            DaytonaSdkUnavailableError,
        )
        self.assertIs(
            daytona_sdk_adapter.build_daytona_sdk_protocol_client,
            build_daytona_sdk_protocol_client,
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

    def test_blocked_readiness_prevents_lazy_import_and_factory(self) -> None:
        importer_calls: list[str] = []
        factory_calls: list[object] = []

        def fake_importer(name: str) -> object:
            importer_calls.append(name)
            return object()

        def fake_factory(module, config):  # noqa: ANN001 - fake factory.
            factory_calls.append((module, config))
            return FakeSdkClient()

        adapter = DaytonaSdkAdapter(
            DaytonaSdkAdapterConfig(
                real_execution_config=DaytonaRealExecutionConfig(),
                sdk_module_name="fake_daytona",
                sdk_importer=fake_importer,
                sdk_client_factory=fake_factory,
            )
        )

        with self.assertRaisesRegex(
            DaytonaSdkUnavailableError,
            "not ready for real execution",
        ):
            adapter.open_sandbox(sandbox_name="sandbox", working_dir="/workspace")

        self.assertEqual(importer_calls, [])
        self.assertEqual(factory_calls, [])

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

    def test_lazy_importer_and_factory_resolve_client_on_first_operation_and_cache_it(self) -> None:
        fake = FakeSdkClient()
        fake_module = object()
        importer_calls: list[str] = []
        factory_calls: list[tuple[object, object]] = []

        def fake_importer(name: str) -> object:
            importer_calls.append(name)
            return fake_module

        def fake_factory(module, config):  # noqa: ANN001 - fake factory.
            factory_calls.append((module, config))
            return fake

        adapter = DaytonaSdkAdapter(
            ready_adapter_config(
                sdk_module_name="fake_daytona_sdk",
                sdk_importer=fake_importer,
                sdk_client_factory=fake_factory,
            )
        )

        handle = adapter.open_sandbox(
            sandbox_name="sandbox",
            working_dir="/workspace",
        )
        adapter.close_sandbox(handle)

        self.assertEqual(importer_calls, ["fake_daytona_sdk"])
        self.assertEqual(len(factory_calls), 1)
        self.assertIs(factory_calls[0][0], fake_module)
        self.assertEqual(
            [call[0] for call in fake.calls],
            ["open", "close"],
        )

    def test_default_factory_missing_constructor_missing_sdk_and_factory_exceptions_are_deterministic(self) -> None:
        missing_constructor = DaytonaSdkAdapter(
            ready_adapter_config(sdk_importer=lambda name: object())
        )
        with self.assertRaisesRegex(
            DaytonaSdkUnavailableError,
            "must provide create_client, Client, or Session",
        ):
            missing_constructor.open_sandbox(
                sandbox_name="sandbox",
                working_dir="/workspace",
            )

        missing_sdk = DaytonaSdkAdapter(
            ready_adapter_config(
                sdk_module_name="missing_daytona",
                sdk_importer=lambda name: (_ for _ in ()).throw(
                    ModuleNotFoundError("missing_daytona")
                ),
                sdk_client_factory=lambda module, config: FakeSdkClient(),
            )
        )
        with self.assertRaisesRegex(
            DaytonaSdkUnavailableError,
            "Daytona SDK module import failed: missing_daytona",
        ):
            missing_sdk.open_sandbox(
                sandbox_name="sandbox",
                working_dir="/workspace",
            )

        factory_failure = DaytonaSdkAdapter(
            ready_adapter_config(
                sdk_importer=lambda name: object(),
                sdk_client_factory=lambda module, config: (_ for _ in ()).throw(
                    RuntimeError("factory failed")
                ),
            )
        )
        with self.assertRaisesRegex(
            DaytonaSdkUnavailableError,
            "Daytona SDK client factory failed: RuntimeError: factory failed",
        ):
            factory_failure.open_sandbox(
                sandbox_name="sandbox",
                working_dir="/workspace",
            )

    def test_default_facade_factory_uses_fake_sdk_module_and_caches_resolved_client(self) -> None:
        fake_module = FakeSdkModule()
        importer_calls: list[str] = []

        def fake_importer(name: str) -> object:
            importer_calls.append(name)
            return fake_module

        adapter = DaytonaSdkAdapter(
            ready_adapter_config(
                sdk_module_name="fake_daytona_sdk",
                sdk_importer=fake_importer,
            )
        )

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

        self.assertEqual(importer_calls, ["fake_daytona_sdk"])
        self.assertEqual(len(fake_module.created_configs), 1)
        self.assertEqual(command_result.exit_code, 0)
        self.assertIn(
            "daytona_sdk_protocol_command exit_code=0",
            command_result.summary_text,
        )
        self.assertEqual(
            fake_module.client.calls,
            [
                ("open", "sandbox", "/workspace"),
                ("upload", "low-sandbox", "/local/input.json", "/workspace/input.json"),
                ("command", "low-sandbox", ("python", "worker.py"), "/workspace"),
                ("download", "low-sandbox", "/workspace/result.json", "/local/result.json"),
                ("close", "low-sandbox"),
            ],
        )

        second = adapter.open_sandbox(sandbox_name="second", working_dir="/workspace")
        self.assertEqual(second.handle_id, "low-second")
        self.assertEqual(importer_calls, ["fake_daytona_sdk"])
        self.assertEqual(len(fake_module.created_configs), 1)

    def test_default_facade_supports_client_and_session_constructor_names(self) -> None:
        class ClientModule:
            def Client(self, config):  # noqa: N802, ANN001 - fake SDK shape.
                return FakeLowLevelSdkClient()

        class SessionModule:
            def Session(self, config):  # noqa: N802, ANN001 - fake SDK shape.
                return FakeLowLevelSdkClient()

        for module in (ClientModule(), SessionModule()):
            client = build_daytona_sdk_protocol_client(
                module,
                DaytonaRealExecutionConfig(allow_real_daytona=True),
            )
            handle = client.open_sandbox(sandbox_name=None, working_dir="/workspace")
            self.assertEqual(handle.handle_id, "low-default")

    def test_malformed_default_facade_surfaces_fail_deterministically(self) -> None:
        class MissingUploadClient:
            def open_sandbox(self, *, sandbox_name, working_dir):  # noqa: ANN001
                return "handle"

        class BadHandleClient(FakeLowLevelSdkClient):
            def open_sandbox(self, *, sandbox_name, working_dir):  # noqa: ANN001
                return object()

        class BadCommandResultClient(FakeLowLevelSdkClient):
            def run_command(self, handle, worker_argv, working_dir):  # noqa: ANN001
                return {}

        with self.assertRaisesRegex(
            DaytonaSdkUnavailableError,
            "requires low-level method upload_file",
        ):
            build_daytona_sdk_protocol_client(
                FakeSdkModule(MissingUploadClient()),
                DaytonaRealExecutionConfig(allow_real_daytona=True),
            )

        bad_handle = build_daytona_sdk_protocol_client(
            FakeSdkModule(BadHandleClient()),
            DaytonaRealExecutionConfig(allow_real_daytona=True),
        )
        with self.assertRaisesRegex(
            DaytonaSdkUnavailableError,
            "must provide handle_id or id",
        ):
            bad_handle.open_sandbox(sandbox_name=None, working_dir="/workspace")

        bad_command = build_daytona_sdk_protocol_client(
            FakeSdkModule(BadCommandResultClient()),
            DaytonaRealExecutionConfig(allow_real_daytona=True),
        )
        handle = bad_command.open_sandbox(sandbox_name=None, working_dir="/workspace")
        with self.assertRaisesRegex(
            DaytonaSdkUnavailableError,
            "must provide exit_code",
        ):
            bad_command.run_command(
                handle,
                DaytonaCommandOperation(
                    worker_argv=("python", "worker.py"),
                    working_dir="/workspace",
                ),
            )

    def test_bad_factory_return_value_fails_before_operation_call(self) -> None:
        adapter = DaytonaSdkAdapter(
            ready_adapter_config(
                sdk_importer=lambda name: object(),
                sdk_client_factory=lambda module, config: MissingMethodsClient(),
            )
        )

        with self.assertRaisesRegex(
            DaytonaSdkUnavailableError,
            "factory returned an object missing open_sandbox",
        ):
            adapter.open_sandbox(sandbox_name="sandbox", working_dir="/workspace")

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
        with self.assertRaisesRegex(ValueError, "sdk_module_name"):
            DaytonaSdkAdapterConfig(sdk_module_name="")
        with self.assertRaisesRegex(ValueError, "sdk_importer"):
            DaytonaSdkAdapterConfig(sdk_importer=object())  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "sdk_client_factory"):
            DaytonaSdkAdapterConfig(sdk_client_factory=object())  # type: ignore[arg-type]

        decoded = json.loads(json.dumps(config.to_dict(), sort_keys=True))
        self.assertTrue(decoded["has_sdk_client"])
        self.assertEqual(decoded["real_execution_config"]["api_key_env_var"], "TOKEN")
        self.assertEqual(decoded["sdk_module_name"], "daytona")
        self.assertFalse(decoded["has_sdk_importer"])
        self.assertFalse(decoded["has_sdk_client_factory"])

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
