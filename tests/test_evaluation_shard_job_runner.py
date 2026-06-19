"""Tests for local single-shard job runner contracts."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from unittest.mock import patch

from ow_eval import (
    EvaluationBatchResult,
    EvaluationBatchSummary,
    EvaluationShardJob,
    EvaluationShardJobRunResult,
    EvaluationShardRunResult,
    EvaluationStatus,
    MatchMetrics,
    MatchResult,
    ShardPlanConfig,
    build_evaluation_shard_plan,
    evaluation_shard_from_job,
    read_evaluation_shard_job,
    run_evaluation_shard_job,
    run_evaluation_shard_job_main,
    write_evaluation_shard_job_package,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
QUICK_2P = REPO_ROOT / "experiments" / "manifests" / "quick-2p-smoke.json"


def packaged_job(temp_dir: str | Path):
    plan = build_evaluation_shard_plan(
        (QUICK_2P,),
        ShardPlanConfig(
            shard_count=1,
            output_root=Path(temp_dir) / "package",
            label_prefix="job-runner",
        ),
    )
    package = write_evaluation_shard_job_package(plan)
    return plan, package, package.jobs[0]


def completed_shard_run_result(shard) -> EvaluationShardRunResult:
    batch_result = EvaluationBatchResult(
        results=(
            MatchResult(
                config=shard.matches[0],
                status=EvaluationStatus.COMPLETED,
                metrics=MatchMetrics(
                    final_rank=1,
                    final_score=3.0,
                    turns_survived=200,
                ),
            ),
        ),
        summary=EvaluationBatchSummary(
            total_matches=shard.match_count,
            completed_count=1,
            error_count=0,
            status_counts=(("completed", 1),),
            mean_final_rank=1.0,
            mean_final_score=3.0,
            mean_turns_survived=200.0,
        ),
    )
    return EvaluationShardRunResult(
        shard=shard,
        batch_result=batch_result,
        summary_text=(
            f"shard_run=COMPLETE shard_id={shard.shard_id} label={shard.label} "
            f"matches={shard.match_count} completed=1 errors=0"
        ),
    )


class EvaluationShardJobRunnerTests(unittest.TestCase):
    def test_module_imports_and_exports_are_available(self) -> None:
        import ow_eval.shard_job_runner as shard_job_runner

        self.assertIs(
            shard_job_runner.EvaluationShardJobRunResult,
            EvaluationShardJobRunResult,
        )
        self.assertIs(
            shard_job_runner.read_evaluation_shard_job,
            read_evaluation_shard_job,
        )
        self.assertIs(
            shard_job_runner.evaluation_shard_from_job,
            evaluation_shard_from_job,
        )
        self.assertIs(
            shard_job_runner.run_evaluation_shard_job,
            run_evaluation_shard_job,
        )
        self.assertIs(shard_job_runner.main, run_evaluation_shard_job_main)

    def test_reads_job_json_into_typed_job(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _, _, job = packaged_job(temp_dir)

            loaded = read_evaluation_shard_job(job.job_path)

            self.assertIsInstance(loaded, EvaluationShardJob)
            self.assertEqual(loaded.to_dict(), job.to_dict())

    def test_reconstructs_shard_from_materialized_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _, _, job = packaged_job(temp_dir)

            shard = evaluation_shard_from_job(job)

            self.assertEqual(shard.shard_id, job.shard_id)
            self.assertEqual(shard.label, job.label)
            self.assertEqual(shard.source_manifest_refs, job.source_manifest_refs)
            self.assertEqual(shard.match_labels, job.match_labels)
            self.assertEqual(shard.seeds, job.seeds)
            self.assertEqual(shard.planned_manifest_path, job.manifest_path)
            self.assertEqual(shard.planned_report_path, job.report_path)
            self.assertEqual(shard.command, job.command)
            self.assertEqual(tuple(match.label for match in shard.matches), job.match_labels)
            self.assertEqual(tuple(match.seed for match in shard.matches), job.seeds)

    def test_reconstruction_rejects_metadata_mismatches(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _, _, job = packaged_job(temp_dir)

            bad_label_job = replace(
                job,
                match_labels=("bad-label",) + job.match_labels[1:],
            )
            with self.assertRaisesRegex(ValueError, "match_labels"):
                evaluation_shard_from_job(bad_label_job)

            bad_seed_job = replace(job, seeds=(999,) + job.seeds[1:])
            with self.assertRaisesRegex(ValueError, "seeds"):
                evaluation_shard_from_job(bad_seed_job)

    def test_successful_job_execution_runs_shard_and_persists_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _, _, job = packaged_job(temp_dir)
            expected_shard = evaluation_shard_from_job(job)
            shard_run_result = completed_shard_run_result(expected_shard)

            with patch(
                "ow_eval.shard_job_runner.run_evaluation_shard",
                return_value=shard_run_result,
            ) as run_shard:
                with patch(
                    "ow_eval.shard_job_runner.write_evaluation_shard_run_result",
                    return_value=Path(job.shard_result_path),
                ) as write_result:
                    result = run_evaluation_shard_job(job.job_path)

            self.assertEqual(result.exit_code, 0)
            self.assertTrue(result.passed)
            self.assertEqual(result.job.to_dict(), job.to_dict())
            self.assertEqual(result.shard.to_dict(), expected_shard.to_dict())
            self.assertIs(result.shard_run_result, shard_run_result)
            self.assertEqual(result.shard_result_path, job.shard_result_path)
            self.assertIn("shard_job=COMPLETE", result.summary_text)
            run_shard.assert_called_once()
            self.assertEqual(run_shard.call_args.args[0].to_dict(), expected_shard.to_dict())
            write_result.assert_called_once_with(shard_run_result, job.shard_result_path)

    def test_job_errors_return_structured_result(self) -> None:
        missing_path = "/tmp/ow-missing-shard-job.json"

        result = run_evaluation_shard_job(missing_path)

        self.assertEqual(result.exit_code, 2)
        self.assertFalse(result.passed)
        self.assertEqual(
            result.summary_text,
            f"shard_job=ERROR job_path={missing_path} exit_code=2",
        )
        self.assertIn("FileNotFoundError", result.error_text)

    def test_read_rejects_malformed_job_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir) / "bad.job.json"
            temp_path.write_text("[]\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "object"):
                read_evaluation_shard_job(temp_path)

            temp_path.write_text(json.dumps({"job_id": "job-0000"}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "shard_id"):
                read_evaluation_shard_job(temp_path)

    def test_cli_success_prints_job_and_shard_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _, _, job = packaged_job(temp_dir)
            shard = evaluation_shard_from_job(job)
            shard_run_result = completed_shard_run_result(shard)
            cli_result = EvaluationShardJobRunResult(
                job_path=job.job_path,
                job=job,
                shard=shard,
                shard_run_result=shard_run_result,
                shard_result_path=job.shard_result_path,
                exit_code=0,
                summary_text="shard_job=COMPLETE job_id=job-0000 exit_code=0",
            )

            stdout = io.StringIO()
            with patch(
                "ow_eval.shard_job_runner.run_evaluation_shard_job",
                return_value=cli_result,
            ) as run_job:
                with contextlib.redirect_stdout(stdout):
                    exit_code = run_evaluation_shard_job_main([job.job_path])

            self.assertEqual(exit_code, 0)
            run_job.assert_called_once_with(job.job_path)
            output = stdout.getvalue()
            self.assertIn("shard_job=COMPLETE", output)
            self.assertIn("shard_run=COMPLETE", output)

    def test_cli_errors_print_to_stderr(self) -> None:
        cli_result = EvaluationShardJobRunResult(
            job_path="/tmp/bad.job.json",
            exit_code=2,
            summary_text="shard_job=ERROR job_path=/tmp/bad.job.json exit_code=2",
            error_text="ValueError: bad job",
        )
        stdout = io.StringIO()
        stderr = io.StringIO()

        with patch(
            "ow_eval.shard_job_runner.run_evaluation_shard_job",
            return_value=cli_result,
        ):
            with contextlib.redirect_stdout(stdout):
                with contextlib.redirect_stderr(stderr):
                    exit_code = run_evaluation_shard_job_main(["/tmp/bad.job.json"])

        self.assertEqual(exit_code, 2)
        self.assertIn("shard_job=ERROR", stdout.getvalue())
        self.assertIn("ValueError: bad job", stderr.getvalue())

    def test_cli_help_exits_zero(self) -> None:
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            with self.assertRaises(SystemExit) as raised:
                run_evaluation_shard_job_main(["--help"])

        self.assertEqual(raised.exception.code, 0)
        self.assertIn("shard job JSON", stdout.getvalue())

    def test_result_is_frozen_slotted_validates_and_is_json_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _, _, job = packaged_job(temp_dir)
            shard = evaluation_shard_from_job(job)
            shard_run_result = completed_shard_run_result(shard)
            result = EvaluationShardJobRunResult(
                job_path=job.job_path,
                job=job,
                shard=shard,
                shard_run_result=shard_run_result,
                shard_result_path=job.shard_result_path,
                exit_code=0,
                summary_text="summary",
            )

            with self.assertRaises(FrozenInstanceError):
                result.exit_code = 2  # type: ignore[misc]
            with self.assertRaises((AttributeError, TypeError)):
                result.extra = "nope"  # type: ignore[attr-defined]
            with self.assertRaisesRegex(ValueError, "job"):
                EvaluationShardJobRunResult(
                    job_path="/tmp/job.json",
                    job="bad",  # type: ignore[arg-type]
                    summary_text="summary",
                )
            with self.assertRaisesRegex(ValueError, "exit_code"):
                EvaluationShardJobRunResult(
                    job_path="/tmp/job.json",
                    exit_code=True,  # type: ignore[arg-type]
                    summary_text="summary",
                )
            with self.assertRaisesRegex(ValueError, "summary_text"):
                EvaluationShardJobRunResult(job_path="/tmp/job.json")

            decoded = json.loads(json.dumps(result.to_dict(), sort_keys=True))
            self.assertTrue(decoded["passed"])
            self.assertEqual(decoded["job"]["job_id"], job.job_id)
            self.assertEqual(decoded["shard"]["shard_id"], shard.shard_id)
            self.assertEqual(decoded["shard_run_result"]["summary_text"], shard_run_result.summary_text)

    def test_runner_does_not_execute_commands_or_other_workflows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _, _, job = packaged_job(temp_dir)
            shard = evaluation_shard_from_job(job)
            shard_run_result = completed_shard_run_result(shard)

            with patch(
                "ow_eval.shard_job_runner.run_evaluation_shard",
                return_value=shard_run_result,
            ):
                with patch(
                    "ow_eval.shard_job_runner.write_evaluation_shard_run_result",
                    return_value=Path(job.shard_result_path),
                ):
                    with patch("subprocess.run") as subprocess_run:
                        with patch(
                            "ow_eval.shard_merge.merge_evaluation_shard_results",
                        ) as merge_results:
                            with patch(
                                "ow_eval.shard_package_cli.prepare_evaluation_shard_package",
                            ) as prepare_package:
                                with patch(
                                    "ow_eval.official_runner.run_official_match",
                                ) as official_runner:
                                    result = run_evaluation_shard_job(job.job_path)

            self.assertEqual(result.exit_code, 0)
            subprocess_run.assert_not_called()
            merge_results.assert_not_called()
            prepare_package.assert_not_called()
            official_runner.assert_not_called()


if __name__ == "__main__":
    unittest.main()
