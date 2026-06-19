"""Tests for Daytona shard executor protocol orchestration."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch

from ow_eval import (
    DaytonaShardExecutionBatchResult,
    DaytonaShardExecutionRequest,
    DaytonaShardExecutionResult,
    DaytonaShardJobExecutor,
    EvaluationBatchResult,
    EvaluationBatchSummary,
    EvaluationShardMergeResult,
    ShardPlanConfig,
    build_daytona_shard_job_plan,
    build_evaluation_shard_plan,
    run_daytona_shard_job_plan,
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
            label_prefix="daytona-executor",
        ),
    )
    return write_evaluation_shard_job_package(plan)


def written_daytona_plan(temp_dir: str | Path):
    package = packaged_index(temp_dir)
    plan = build_daytona_shard_job_plan(package.index_path)
    plan_path = Path(temp_dir) / "daytona-plan.json"
    write_daytona_shard_job_plan(plan, plan_path)
    return package, plan, plan_path


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


class FakeExecutor:
    def __init__(
        self,
        results: tuple[DaytonaShardExecutionResult, ...] = (),
    ) -> None:
        self.requests: list[DaytonaShardExecutionRequest] = []
        self._results = list(results)

    def execute(
        self,
        request: DaytonaShardExecutionRequest,
    ) -> DaytonaShardExecutionResult:
        self.requests.append(request)
        if self._results:
            return self._results.pop(0)
        return DaytonaShardExecutionResult(
            job_id=request.job_id,
            shard_id=request.shard_id,
            label=request.label,
            sandbox_name=request.sandbox_name,
            shard_result_path=request.local_shard_result_path,
            exit_code=0,
            summary_text=(
                f"daytona_shard_job=COMPLETE job_id={request.job_id} exit_code=0"
            ),
        )


class DaytonaExecutorTests(unittest.TestCase):
    def test_module_imports_and_exports_are_available(self) -> None:
        import ow_eval.daytona_executor as daytona_executor

        self.assertIs(
            daytona_executor.DaytonaShardExecutionRequest,
            DaytonaShardExecutionRequest,
        )
        self.assertIs(
            daytona_executor.DaytonaShardExecutionResult,
            DaytonaShardExecutionResult,
        )
        self.assertIs(
            daytona_executor.DaytonaShardExecutionBatchResult,
            DaytonaShardExecutionBatchResult,
        )
        self.assertIs(
            daytona_executor.DaytonaShardJobExecutor,
            DaytonaShardJobExecutor,
        )
        self.assertIs(
            daytona_executor.run_daytona_shard_job_plan,
            run_daytona_shard_job_plan,
        )

    def test_preflight_failure_prevents_executor_calls(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package, _plan, plan_path = written_daytona_plan(temp_dir)
            Path(package.jobs[0].manifest_path).unlink()
            executor = FakeExecutor()

            result = run_daytona_shard_job_plan(plan_path, executor)

            self.assertEqual(result.exit_code, 2)
            self.assertFalse(result.passed)
            self.assertEqual(executor.requests, [])
            self.assertIsNotNone(result.preflight_result)
            self.assertEqual(result.preflight_result.exit_code, 2)
            self.assertIn("preflight failed", result.error_text)
            self.assertIn("daytona_shard_execution=ERROR", result.summary_text)

    def test_execution_requests_are_built_in_plan_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _package, plan, plan_path = written_daytona_plan(temp_dir)
            executor = FakeExecutor()

            with patch(
                "ow_eval.daytona_executor.merge_evaluation_shard_result_files",
                return_value=fake_merge_result(),
            ):
                result = run_daytona_shard_job_plan(plan_path, executor)

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(
                tuple(request.job_id for request in executor.requests),
                tuple(spec.job_id for spec in plan.specs),
            )
            self.assertEqual(
                tuple(request.job_id for request in result.execution_requests),
                tuple(spec.job_id for spec in plan.specs),
            )
            for request, spec in zip(result.execution_requests, plan.specs, strict=True):
                self.assertIsInstance(request.worker_argv, tuple)
                self.assertEqual(request.shard_id, spec.shard_id)
                self.assertEqual(request.label, spec.label)
                self.assertEqual(request.sandbox_name, spec.sandbox_name)
                self.assertEqual(request.worker_argv, spec.worker_argv)
                self.assertEqual(request.working_dir, spec.working_dir)
                self.assertEqual(
                    request.expected_upload_paths,
                    spec.expected_upload_paths,
                )
                self.assertEqual(
                    request.expected_download_paths,
                    spec.expected_download_paths,
                )
                self.assertEqual(
                    request.local_shard_result_path,
                    spec.local_shard_result_path,
                )
                self.assertEqual(request.spec, spec)

    def test_successful_execution_results_are_preserved_and_merged_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _package, plan, plan_path = written_daytona_plan(temp_dir)
            executor = FakeExecutor()
            merged = fake_merge_result()

            with patch(
                "ow_eval.daytona_executor.merge_evaluation_shard_result_files",
                return_value=merged,
            ) as merge_files:
                result = run_daytona_shard_job_plan(plan_path, executor)

            expected_paths = tuple(spec.local_shard_result_path for spec in plan.specs)
            self.assertEqual(result.exit_code, 0)
            self.assertTrue(result.passed)
            self.assertEqual(
                tuple(execution.job_id for execution in result.execution_results),
                tuple(spec.job_id for spec in plan.specs),
            )
            self.assertEqual(result.shard_result_paths, expected_paths)
            self.assertIs(result.merged_result, merged)
            merge_files.assert_called_once_with(expected_paths)
            self.assertIn("merged=True", result.summary_text)

    def test_failed_execution_returns_nonzero_and_skips_merge(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _package, plan, plan_path = written_daytona_plan(temp_dir)
            first, second = plan.specs
            executor = FakeExecutor(
                results=(
                    DaytonaShardExecutionResult(
                        job_id=first.job_id,
                        shard_id=first.shard_id,
                        label=first.label,
                        sandbox_name=first.sandbox_name,
                        shard_result_path=first.local_shard_result_path,
                        exit_code=0,
                        summary_text="daytona_shard_job=COMPLETE job_id=job-0000",
                    ),
                    DaytonaShardExecutionResult(
                        job_id=second.job_id,
                        shard_id=second.shard_id,
                        label=second.label,
                        sandbox_name=second.sandbox_name,
                        shard_result_path=second.local_shard_result_path,
                        exit_code=17,
                        summary_text="daytona_shard_job=ERROR job_id=job-0001",
                        error_text="RuntimeError: synthetic failure",
                    ),
                )
            )

            with patch(
                "ow_eval.daytona_executor.merge_evaluation_shard_result_files",
            ) as merge_files:
                result = run_daytona_shard_job_plan(plan_path, executor)

            self.assertEqual(result.exit_code, 2)
            self.assertFalse(result.passed)
            self.assertEqual(len(result.execution_results), 2)
            self.assertEqual(result.shard_result_paths, (first.local_shard_result_path,))
            self.assertIn("execution failed: job-0001", result.error_text)
            self.assertIn("synthetic failure", result.error_text)
            merge_files.assert_not_called()

    def test_merge_results_false_skips_merge_and_still_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _package, plan, plan_path = written_daytona_plan(temp_dir)
            executor = FakeExecutor()

            with patch(
                "ow_eval.daytona_executor.merge_evaluation_shard_result_files",
            ) as merge_files:
                result = run_daytona_shard_job_plan(
                    plan_path,
                    executor,
                    merge_results=False,
                )

            self.assertEqual(result.exit_code, 0)
            self.assertTrue(result.passed)
            self.assertIsNone(result.merged_result)
            self.assertEqual(
                result.shard_result_paths,
                tuple(spec.local_shard_result_path for spec in plan.specs),
            )
            self.assertIn("merged=False", result.summary_text)
            merge_files.assert_not_called()

    def test_executor_exception_returns_structured_error(self) -> None:
        class RaisingExecutor:
            def execute(self, request):  # noqa: ANN001 - intentionally loose fake.
                raise RuntimeError(f"failed {request.job_id}")

        with tempfile.TemporaryDirectory() as temp_dir:
            _package, _plan, plan_path = written_daytona_plan(temp_dir)

            result = run_daytona_shard_job_plan(plan_path, RaisingExecutor())

            self.assertEqual(result.exit_code, 2)
            self.assertEqual(result.execution_results, ())
            self.assertIn("executor failed for job-0000", result.error_text)
            self.assertIn("RuntimeError: failed job-0000", result.error_text)

    def test_missing_result_path_is_structured_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _package, plan, plan_path = written_daytona_plan(temp_dir)
            spec = plan.specs[0]
            executor = FakeExecutor(
                results=(
                    DaytonaShardExecutionResult(
                        job_id=spec.job_id,
                        shard_id=spec.shard_id,
                        label=spec.label,
                        sandbox_name=spec.sandbox_name,
                        shard_result_path=None,
                        exit_code=0,
                        summary_text="daytona_shard_job=COMPLETE missing-path",
                    ),
                )
            )

            result = run_daytona_shard_job_plan(plan_path, executor)

            self.assertEqual(result.exit_code, 2)
            self.assertIn("missing shard_result_path", result.error_text)

    def test_result_objects_are_frozen_slotted_validated_and_json_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _package, plan, plan_path = written_daytona_plan(temp_dir)
            preflight = run_daytona_shard_job_plan(
                plan_path,
                FakeExecutor(),
                merge_results=False,
            ).preflight_result
            request = DaytonaShardExecutionRequest(
                job_id=plan.specs[0].job_id,
                shard_id=plan.specs[0].shard_id,
                label=plan.specs[0].label,
                sandbox_name=plan.specs[0].sandbox_name,
                worker_argv=plan.specs[0].worker_argv,
                working_dir=plan.specs[0].working_dir,
                expected_upload_paths=plan.specs[0].expected_upload_paths,
                expected_download_paths=plan.specs[0].expected_download_paths,
                local_shard_result_path=plan.specs[0].local_shard_result_path,
                spec=plan.specs[0],
            )
            execution = DaytonaShardExecutionResult(
                job_id=request.job_id,
                shard_id=request.shard_id,
                label=request.label,
                sandbox_name=request.sandbox_name,
                shard_result_path=request.local_shard_result_path,
                exit_code=0,
                summary_text="daytona_shard_job=COMPLETE validation",
            )
            batch = DaytonaShardExecutionBatchResult(
                plan_path=str(plan_path),
                plan=plan,
                preflight_result=preflight,
                execution_requests=(request,),
                execution_results=(execution,),
                shard_result_paths=(execution.shard_result_path,),
                exit_code=0,
                summary_text="daytona_shard_execution=COMPLETE validation",
            )

            with self.assertRaises(FrozenInstanceError):
                batch.exit_code = 2  # type: ignore[misc]
            with self.assertRaises((AttributeError, TypeError)):
                batch.extra = "nope"  # type: ignore[attr-defined]
            with self.assertRaises(FrozenInstanceError):
                request.label = "changed"  # type: ignore[misc]
            with self.assertRaises(FrozenInstanceError):
                execution.exit_code = 2  # type: ignore[misc]
            with self.assertRaisesRegex(ValueError, "execution_requests"):
                DaytonaShardExecutionBatchResult(
                    execution_requests=[request],  # type: ignore[arg-type]
                    summary_text="summary",
                )
            with self.assertRaisesRegex(ValueError, "exit_code"):
                DaytonaShardExecutionResult(
                    job_id="job",
                    shard_id="shard",
                    label="label",
                    exit_code=True,  # type: ignore[arg-type]
                    summary_text="summary",
                )

            decoded = json.loads(json.dumps(batch.to_dict(), sort_keys=True))
            self.assertTrue(decoded["passed"])
            self.assertEqual(decoded["execution_requests"][0]["job_id"], request.job_id)
            self.assertEqual(decoded["execution_results"][0]["exit_code"], 0)

    def test_executor_does_not_call_daytona_subprocess_or_run_matches(self) -> None:
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
                            result = run_daytona_shard_job_plan(
                                plan_path,
                                FakeExecutor(),
                                merge_results=False,
                            )

            self.assertEqual(result.exit_code, 0)
            subprocess_run.assert_not_called()
            run_job.assert_not_called()
            run_index.assert_not_called()
            official_runner.assert_not_called()
            self.assertNotIn("daytona", sys.modules)


if __name__ == "__main__":
    unittest.main()
