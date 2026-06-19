"""Tests for local shard job package index runner contracts."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import call, patch

from ow_eval import (
    EvaluationBatchResult,
    EvaluationBatchSummary,
    EvaluationShardIndexRunResult,
    EvaluationShardJobIndex,
    EvaluationShardJobRunResult,
    EvaluationShardMergeResult,
    ShardPlanConfig,
    build_evaluation_shard_plan,
    read_evaluation_shard_job_index,
    run_evaluation_shard_index_main,
    run_evaluation_shard_job_index,
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
            label_prefix="index-runner",
        ),
    )
    return write_evaluation_shard_job_package(plan)


def successful_job_result(job) -> EvaluationShardJobRunResult:
    return EvaluationShardJobRunResult(
        job_path=job.job_path,
        job=job,
        shard_result_path=job.shard_result_path,
        exit_code=0,
        summary_text=f"shard_job=COMPLETE job_id={job.job_id} exit_code=0",
    )


def failed_job_result(job) -> EvaluationShardJobRunResult:
    return EvaluationShardJobRunResult(
        job_path=job.job_path,
        job=job,
        exit_code=2,
        summary_text=f"shard_job=ERROR job_path={job.job_path} exit_code=2",
        error_text="ValueError: synthetic job failure",
    )


def merged_result(total_matches: int = 4) -> EvaluationShardMergeResult:
    return EvaluationShardMergeResult(
        shard_results=(),
        batch_result=EvaluationBatchResult(
            summary=EvaluationBatchSummary(
                total_matches=total_matches,
                completed_count=total_matches,
                error_count=0,
                status_counts=(("completed", total_matches),),
            ),
        ),
        summary_text=(
            f"shard_merge=COMPLETE shards=2 matches={total_matches} "
            f"completed={total_matches} errors=0"
        ),
    )


class EvaluationShardIndexRunnerTests(unittest.TestCase):
    def test_module_imports_and_exports_are_available(self) -> None:
        import ow_eval.shard_index_runner as shard_index_runner

        self.assertIs(
            shard_index_runner.EvaluationShardJobIndex,
            EvaluationShardJobIndex,
        )
        self.assertIs(
            shard_index_runner.EvaluationShardIndexRunResult,
            EvaluationShardIndexRunResult,
        )
        self.assertIs(
            shard_index_runner.read_evaluation_shard_job_index,
            read_evaluation_shard_job_index,
        )
        self.assertIs(
            shard_index_runner.run_evaluation_shard_job_index,
            run_evaluation_shard_job_index,
        )
        self.assertIs(shard_index_runner.main, run_evaluation_shard_index_main)

    def test_reads_package_index_json_into_typed_index(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = packaged_index(temp_dir)

            index = read_evaluation_shard_job_index(package.index_path)

            self.assertIsInstance(index, EvaluationShardJobIndex)
            self.assertEqual(index.index_path, package.index_path)
            self.assertEqual(
                tuple(job.to_dict() for job in index.jobs),
                tuple(job.to_dict() for job in package.jobs),
            )
            self.assertEqual(index.job_paths, package.job_paths)
            self.assertEqual(index.manifest_paths, package.manifest_paths)
            self.assertEqual(index.commands, package.commands)
            self.assertEqual(index.summary_text, package.summary_text)

    def test_read_validates_malformed_index_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = packaged_index(temp_dir)
            payload = json.loads(Path(package.index_path).read_text(encoding="utf-8"))
            path = Path(temp_dir) / "bad.index.json"

            path.write_text("[]\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "object"):
                read_evaluation_shard_job_index(path)

            bad_payload = dict(payload)
            bad_payload["jobs"] = []
            path.write_text(json.dumps(bad_payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "jobs"):
                read_evaluation_shard_job_index(path)

            bad_payload = dict(payload)
            bad_payload["job_paths"] = ["", package.job_paths[1]]
            path.write_text(json.dumps(bad_payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "job_paths\\[0\\]"):
                read_evaluation_shard_job_index(path)

            bad_payload = dict(payload)
            bad_payload["job_paths"] = ["/tmp/other.job.json", package.job_paths[1]]
            path.write_text(json.dumps(bad_payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "job_paths\\[0\\]"):
                read_evaluation_shard_job_index(path)

            bad_payload = dict(payload)
            bad_payload["manifest_paths"] = [
                "/tmp/other.manifest.json",
                package.manifest_paths[1],
            ]
            path.write_text(json.dumps(bad_payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "manifest_paths\\[0\\]"):
                read_evaluation_shard_job_index(path)

            bad_payload = dict(payload)
            bad_payload["commands"] = ["python other.py", package.commands[1]]
            path.write_text(json.dumps(bad_payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "commands\\[0\\]"):
                read_evaluation_shard_job_index(path)

    def test_runs_jobs_in_index_order_and_merges_result_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = packaged_index(temp_dir)
            job_results = tuple(successful_job_result(job) for job in package.jobs)
            merge_result = merged_result()

            with patch(
                "ow_eval.shard_index_runner.run_evaluation_shard_job",
                side_effect=job_results,
            ) as run_job:
                with patch(
                    "ow_eval.shard_index_runner.merge_evaluation_shard_result_files",
                    return_value=merge_result,
                ) as merge_files:
                    result = run_evaluation_shard_job_index(package.index_path)

            self.assertEqual(result.exit_code, 0)
            self.assertTrue(result.passed)
            self.assertIs(result.merged_result, merge_result)
            self.assertEqual(result.job_run_results, job_results)
            self.assertEqual(
                result.shard_result_paths,
                tuple(job.shard_result_path for job in package.jobs),
            )
            self.assertIn("shard_index=COMPLETE", result.summary_text)
            self.assertEqual(
                run_job.call_args_list,
                [call(job.job_path) for job in package.jobs],
            )
            merge_files.assert_called_once_with(
                tuple(job.shard_result_path for job in package.jobs)
            )

    def test_failed_job_returns_nonzero_and_skips_merge(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = packaged_index(temp_dir)
            first_success = successful_job_result(package.jobs[0])
            second_failure = failed_job_result(package.jobs[1])

            with patch(
                "ow_eval.shard_index_runner.run_evaluation_shard_job",
                side_effect=(first_success, second_failure),
            ) as run_job:
                with patch(
                    "ow_eval.shard_index_runner.merge_evaluation_shard_result_files",
                ) as merge_files:
                    result = run_evaluation_shard_job_index(package.index_path)

            self.assertEqual(result.exit_code, 2)
            self.assertFalse(result.passed)
            self.assertIsNone(result.merged_result)
            self.assertEqual(result.job_run_results, (first_success, second_failure))
            self.assertEqual(result.shard_result_paths, (package.jobs[0].shard_result_path,))
            self.assertIn("shard job failed: job-0001", result.error_text)
            self.assertEqual(
                run_job.call_args_list,
                [call(package.jobs[0].job_path), call(package.jobs[1].job_path)],
            )
            merge_files.assert_not_called()

    def test_merge_failure_returns_structured_error_with_attempts_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = packaged_index(temp_dir)
            job_results = tuple(successful_job_result(job) for job in package.jobs)

            with patch(
                "ow_eval.shard_index_runner.run_evaluation_shard_job",
                side_effect=job_results,
            ):
                with patch(
                    "ow_eval.shard_index_runner.merge_evaluation_shard_result_files",
                    side_effect=ValueError("merge failed"),
                ):
                    result = run_evaluation_shard_job_index(package.index_path)

            self.assertEqual(result.exit_code, 2)
            self.assertEqual(result.job_run_results, job_results)
            self.assertEqual(
                result.shard_result_paths,
                tuple(job.shard_result_path for job in package.jobs),
            )
            self.assertIn("ValueError: merge failed", result.error_text)

    def test_cli_success_prints_index_job_and_merge_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = packaged_index(temp_dir)
            job_results = tuple(successful_job_result(job) for job in package.jobs)
            cli_result = EvaluationShardIndexRunResult(
                index_path=package.index_path,
                index=read_evaluation_shard_job_index(package.index_path),
                job_run_results=job_results,
                shard_result_paths=tuple(job.shard_result_path for job in package.jobs),
                merged_result=merged_result(),
                exit_code=0,
                summary_text="shard_index=COMPLETE jobs=2 exit_code=0",
            )

            stdout = io.StringIO()
            with patch(
                "ow_eval.shard_index_runner.run_evaluation_shard_job_index",
                return_value=cli_result,
            ) as run_index:
                with contextlib.redirect_stdout(stdout):
                    exit_code = run_evaluation_shard_index_main([package.index_path])

            self.assertEqual(exit_code, 0)
            run_index.assert_called_once_with(package.index_path)
            output = stdout.getvalue()
            self.assertIn("shard_index=COMPLETE", output)
            self.assertIn("shard_job=COMPLETE job_id=job-0000", output)
            self.assertIn("shard_job=COMPLETE job_id=job-0001", output)
            self.assertIn("shard_merge=COMPLETE", output)

    def test_cli_errors_print_to_stderr(self) -> None:
        cli_result = EvaluationShardIndexRunResult(
            index_path="/tmp/bad.index.json",
            exit_code=2,
            summary_text="shard_index=ERROR index_path=/tmp/bad.index.json exit_code=2",
            error_text="ValueError: bad index",
        )
        stdout = io.StringIO()
        stderr = io.StringIO()

        with patch(
            "ow_eval.shard_index_runner.run_evaluation_shard_job_index",
            return_value=cli_result,
        ):
            with contextlib.redirect_stdout(stdout):
                with contextlib.redirect_stderr(stderr):
                    exit_code = run_evaluation_shard_index_main(["/tmp/bad.index.json"])

        self.assertEqual(exit_code, 2)
        self.assertIn("shard_index=ERROR", stdout.getvalue())
        self.assertIn("ValueError: bad index", stderr.getvalue())

    def test_cli_help_exits_zero(self) -> None:
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            with self.assertRaises(SystemExit) as raised:
                run_evaluation_shard_index_main(["--help"])

        self.assertEqual(raised.exception.code, 0)
        self.assertIn("package index", stdout.getvalue())

    def test_result_objects_are_frozen_slotted_validating_and_json_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = packaged_index(temp_dir)
            index = read_evaluation_shard_job_index(package.index_path)
            job_results = tuple(successful_job_result(job) for job in package.jobs)
            result = EvaluationShardIndexRunResult(
                index_path=package.index_path,
                index=index,
                job_run_results=job_results,
                shard_result_paths=tuple(job.shard_result_path for job in package.jobs),
                merged_result=merged_result(),
                exit_code=0,
                summary_text="summary",
            )

            with self.assertRaises(FrozenInstanceError):
                index.summary_text = "changed"  # type: ignore[misc]
            with self.assertRaises((AttributeError, TypeError)):
                index.extra = "nope"  # type: ignore[attr-defined]
            with self.assertRaises(FrozenInstanceError):
                result.exit_code = 2  # type: ignore[misc]
            with self.assertRaises((AttributeError, TypeError)):
                result.extra = "nope"  # type: ignore[attr-defined]
            with self.assertRaisesRegex(ValueError, "jobs"):
                EvaluationShardJobIndex(
                    index_path="/tmp/index.json",
                    jobs=(),
                    job_paths=(),
                    manifest_paths=(),
                    commands=(),
                    summary_text="summary",
                )
            with self.assertRaisesRegex(ValueError, "job_run_results"):
                EvaluationShardIndexRunResult(
                    index_path="/tmp/index.json",
                    job_run_results=[job_results[0]],  # type: ignore[arg-type]
                    summary_text="summary",
                )

            decoded = json.loads(json.dumps(result.to_dict(), sort_keys=True))
            self.assertTrue(decoded["passed"])
            self.assertEqual(decoded["index"]["jobs"][0]["job_id"], "job-0000")
            self.assertEqual(len(decoded["job_run_results"]), 2)
            self.assertEqual(decoded["merged_result"]["summary_text"], merged_result().summary_text)

    def test_runner_does_not_execute_commands_or_other_workflows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = packaged_index(temp_dir)
            job_results = tuple(successful_job_result(job) for job in package.jobs)

            with patch(
                "ow_eval.shard_index_runner.run_evaluation_shard_job",
                side_effect=job_results,
            ):
                with patch(
                    "ow_eval.shard_index_runner.merge_evaluation_shard_result_files",
                    return_value=merged_result(),
                ):
                    with patch("subprocess.run") as subprocess_run:
                        with patch(
                            "ow_eval.shard_package_cli.prepare_evaluation_shard_package",
                        ) as prepare_package:
                            with patch(
                                "ow_eval.official_runner.run_official_match",
                            ) as official_runner:
                                result = run_evaluation_shard_job_index(
                                    package.index_path
                                )

            self.assertEqual(result.exit_code, 0)
            subprocess_run.assert_not_called()
            prepare_package.assert_not_called()
            official_runner.assert_not_called()


if __name__ == "__main__":
    unittest.main()
