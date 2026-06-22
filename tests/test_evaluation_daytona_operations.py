"""Tests for deterministic Daytona sandbox operation-plan contracts."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch

from ow_eval import (
    DaytonaBatchOperationPlan,
    DaytonaCommandOperation,
    DaytonaDownloadOperation,
    DaytonaSandboxOperationPlan,
    DaytonaShardExecutionRequest,
    DaytonaUploadOperation,
    ShardPlanConfig,
    build_daytona_batch_operation_plan,
    build_daytona_sandbox_operation_plan,
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
            label_prefix="daytona-ops",
        ),
    )
    return write_evaluation_shard_job_package(plan)


def execution_requests(temp_dir: str | Path):
    package = packaged_index(temp_dir)
    plan = build_daytona_shard_job_plan(package.index_path)
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


class DaytonaOperationsTests(unittest.TestCase):
    def test_module_imports_and_exports_are_available(self) -> None:
        import ow_eval.daytona_operations as daytona_operations

        self.assertIs(daytona_operations.DaytonaUploadOperation, DaytonaUploadOperation)
        self.assertIs(daytona_operations.DaytonaCommandOperation, DaytonaCommandOperation)
        self.assertIs(
            daytona_operations.DaytonaDownloadOperation,
            DaytonaDownloadOperation,
        )
        self.assertIs(
            daytona_operations.DaytonaSandboxOperationPlan,
            DaytonaSandboxOperationPlan,
        )
        self.assertIs(
            daytona_operations.DaytonaBatchOperationPlan,
            DaytonaBatchOperationPlan,
        )
        self.assertIs(
            daytona_operations.build_daytona_sandbox_operation_plan,
            build_daytona_sandbox_operation_plan,
        )
        self.assertIs(
            daytona_operations.build_daytona_batch_operation_plan,
            build_daytona_batch_operation_plan,
        )

    def test_builds_single_sandbox_operation_plan_from_execution_request(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            request = execution_requests(temp_dir)[0]

            plan = build_daytona_sandbox_operation_plan(request)

            self.assertIsInstance(plan, DaytonaSandboxOperationPlan)
            self.assertEqual(plan.sandbox_name, request.sandbox_name)
            self.assertEqual(plan.job_id, request.job_id)
            self.assertEqual(plan.shard_id, request.shard_id)
            self.assertEqual(plan.label, request.label)
            self.assertEqual(plan.working_dir, request.working_dir)
            self.assertEqual(plan.local_shard_result_path, request.local_shard_result_path)
            self.assertIs(plan.request, request)
            self.assertEqual(
                tuple(operation.local_path for operation in plan.upload_operations),
                request.expected_upload_paths,
            )
            self.assertEqual(
                tuple(operation.sandbox_path for operation in plan.upload_operations),
                request.expected_upload_paths,
            )
            self.assertEqual(plan.command_operation.worker_argv, request.worker_argv)
            self.assertEqual(plan.command_operation.working_dir, request.working_dir)
            self.assertEqual(
                tuple(operation.sandbox_path for operation in plan.download_operations),
                request.expected_download_paths,
            )
            self.assertEqual(
                tuple(operation.local_path for operation in plan.download_operations),
                request.expected_download_paths,
            )
            self.assertIn("daytona_sandbox_operations=READY", plan.summary_text)

    def test_batch_operation_plan_preserves_request_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            requests = execution_requests(temp_dir)

            plan = build_daytona_batch_operation_plan(requests)

            self.assertIsInstance(plan, DaytonaBatchOperationPlan)
            self.assertEqual(
                tuple(item.job_id for item in plan.operation_plans),
                tuple(request.job_id for request in requests),
            )
            self.assertEqual(
                tuple(item.request for item in plan.operation_plans),
                requests,
            )
            self.assertEqual(
                plan.summary_text,
                (
                    "daytona_batch_operations=READY jobs=2 uploads=4 "
                    f"downloads={sum(len(request.expected_download_paths) for request in requests)}"
                ),
            )

    def test_operation_plan_to_dict_is_json_safe_and_keeps_argv_structured(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            requests = execution_requests(temp_dir)
            plan = build_daytona_batch_operation_plan(requests)

            decoded = json.loads(json.dumps(plan.to_dict(), sort_keys=True))

            self.assertEqual(
                [item["job_id"] for item in decoded["operation_plans"]],
                [request.job_id for request in requests],
            )
            command_payload = decoded["operation_plans"][0]["command_operation"]
            self.assertIsInstance(command_payload["worker_argv"], list)
            self.assertEqual(command_payload["worker_argv"], list(requests[0].worker_argv))
            self.assertNotIsInstance(command_payload["worker_argv"], str)
            self.assertEqual(
                decoded["operation_plans"][0]["request"],
                requests[0].to_dict(),
            )

    def test_frozen_slotted_and_validation_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            request = execution_requests(temp_dir)[0]
            plan = build_daytona_sandbox_operation_plan(request)
            batch = build_daytona_batch_operation_plan((request,))

            with self.assertRaises(FrozenInstanceError):
                plan.label = "changed"  # type: ignore[misc]
            with self.assertRaises((AttributeError, TypeError)):
                plan.extra = "nope"  # type: ignore[attr-defined]
            with self.assertRaises(FrozenInstanceError):
                batch.summary_text = "changed"  # type: ignore[misc]
            with self.assertRaisesRegex(ValueError, "local_path"):
                DaytonaUploadOperation(local_path="", sandbox_path="/remote")
            with self.assertRaisesRegex(ValueError, "worker_argv"):
                DaytonaCommandOperation(worker_argv=(), working_dir="/workspace")
            with self.assertRaisesRegex(ValueError, "local_path"):
                DaytonaDownloadOperation(sandbox_path="/remote", local_path="")
            with self.assertRaisesRegex(ValueError, "upload_operations"):
                DaytonaSandboxOperationPlan(
                    sandbox_name=None,
                    job_id=request.job_id,
                    shard_id=request.shard_id,
                    label=request.label,
                    working_dir=request.working_dir,
                    upload_operations=[plan.upload_operations[0]],  # type: ignore[arg-type]
                    command_operation=plan.command_operation,
                    download_operations=plan.download_operations,
                    local_shard_result_path=request.local_shard_result_path,
                    request=request,
                    summary_text="summary",
                )
            with self.assertRaisesRegex(ValueError, "operation_plans"):
                DaytonaBatchOperationPlan(
                    operation_plans=[plan],  # type: ignore[arg-type]
                    summary_text="summary",
                )

    def test_builders_reject_malformed_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            request = execution_requests(temp_dir)[0]

            with self.assertRaisesRegex(ValueError, "request"):
                build_daytona_sandbox_operation_plan(object())  # type: ignore[arg-type]
            with self.assertRaisesRegex(ValueError, "requests"):
                build_daytona_batch_operation_plan(())  # type: ignore[arg-type]
            with self.assertRaisesRegex(ValueError, "non-string sequence"):
                build_daytona_batch_operation_plan("bad")  # type: ignore[arg-type]
            with self.assertRaisesRegex(ValueError, "requests\\[0\\]"):
                build_daytona_batch_operation_plan((object(),))  # type: ignore[arg-type]
            self.assertEqual(
                build_daytona_batch_operation_plan((request,)).operation_plans[0].job_id,
                request.job_id,
            )

    def test_operation_plans_do_not_execute_or_call_daytona_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            requests = execution_requests(temp_dir)
            sys.modules.pop("daytona", None)

            with patch("subprocess.run") as subprocess_run:
                with patch(
                    "ow_eval.shard_job_runner.run_evaluation_shard_job",
                ) as run_job:
                    with patch(
                        "ow_eval.official_runner.run_official_match",
                    ) as official_runner:
                        plan = build_daytona_batch_operation_plan(requests)

            self.assertEqual(len(plan.operation_plans), len(requests))
            subprocess_run.assert_not_called()
            run_job.assert_not_called()
            official_runner.assert_not_called()
            self.assertNotIn("daytona", sys.modules)


if __name__ == "__main__":
    unittest.main()
