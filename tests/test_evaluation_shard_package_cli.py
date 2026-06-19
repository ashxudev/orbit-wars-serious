"""Tests for shard job package preparation CLI workflow."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch

from ow_eval import (
    EvaluationShardJobPackageResult,
    EvaluationShardPackageCliResult,
    ShardPlanConfig,
    build_evaluation_shard_jobs,
    build_evaluation_shard_plan,
    prepare_evaluation_shard_package,
    prepare_evaluation_shards_main,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = REPO_ROOT / "experiments" / "manifests"
QUICK_2P = MANIFEST_DIR / "quick-2p-smoke.json"
QUICK_4P = MANIFEST_DIR / "quick-4p-smoke.json"


def package_result_for_plan(plan, index_path: str | Path | None = None):
    jobs = build_evaluation_shard_jobs(plan)
    resolved_index_path = (
        Path(index_path)
        if index_path is not None
        else Path(plan.config.output_root) / "shard-jobs.index.json"
    )
    return EvaluationShardJobPackageResult(
        shard_plan=plan,
        jobs=jobs,
        manifest_paths=tuple(job.manifest_path for job in jobs),
        job_paths=tuple(job.job_path for job in jobs),
        index_path=str(resolved_index_path),
        commands=tuple(job.command for job in jobs),
        summary_text=(
            f"shard_jobs=WRITTEN shards={len(plan.shards)} "
            f"jobs={len(jobs)} index_path={resolved_index_path}"
        ),
    )


class EvaluationShardPackageCliTests(unittest.TestCase):
    def test_module_imports_and_exports_are_available(self) -> None:
        import ow_eval.shard_package_cli as shard_package_cli

        self.assertIs(
            shard_package_cli.EvaluationShardPackageCliResult,
            EvaluationShardPackageCliResult,
        )
        self.assertIs(
            shard_package_cli.prepare_evaluation_shard_package,
            prepare_evaluation_shard_package,
        )
        self.assertIs(shard_package_cli.main, prepare_evaluation_shards_main)

    def test_planning_by_shard_count_calls_package_writer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "package"

            def fake_writer(plan, *, index_path=None, materialize_manifests=True):
                self.assertIsNone(index_path)
                self.assertTrue(materialize_manifests)
                return package_result_for_plan(plan)

            with patch(
                "ow_eval.shard_package_cli.write_evaluation_shard_job_package",
                side_effect=fake_writer,
            ) as writer:
                result = prepare_evaluation_shard_package(
                    (QUICK_2P, QUICK_4P),
                    output_dir=output_dir,
                    shard_count=2,
                    label_prefix="prep",
                )

        writer.assert_called_once()
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.passed)
        self.assertEqual(result.shard_plan.config.shard_count, 2)
        self.assertEqual(tuple(shard.label for shard in result.shard_plan.shards), ("prep-0000", "prep-0001"))
        self.assertEqual(result.package_result.shard_plan, result.shard_plan)
        self.assertEqual(
            result.summary_text,
            (
                f"evaluation_shard_package=PASS manifests=2 shards=2 jobs=2 "
                f"output_dir={output_dir} "
                f"index_path={output_dir / 'shard-jobs.index.json'} exit_code=0"
            ),
        )

    def test_planning_by_matches_per_shard_preserves_chunking(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "package"

            with patch(
                "ow_eval.shard_package_cli.write_evaluation_shard_job_package",
                side_effect=lambda plan, **kwargs: package_result_for_plan(
                    plan,
                    kwargs.get("index_path"),
                ),
            ):
                result = prepare_evaluation_shard_package(
                    (QUICK_2P, QUICK_4P),
                    output_dir=output_dir,
                    matches_per_shard=3,
                    label_prefix="chunk",
                )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.shard_plan.config.matches_per_shard, 3)
        self.assertEqual(tuple(shard.match_count for shard in result.shard_plan.shards), (3, 1))
        self.assertEqual(tuple(job.label for job in result.package_result.jobs), ("chunk-0000", "chunk-0001"))

    def test_output_dir_is_required(self) -> None:
        result = prepare_evaluation_shard_package((QUICK_2P,), shard_count=1)

        self.assertEqual(result.exit_code, 2)
        self.assertFalse(result.passed)
        self.assertIn("output_dir is required", result.error_text)
        self.assertEqual(
            result.summary_text,
            "evaluation_shard_package=ERROR manifests=1 exit_code=2",
        )

    def test_index_path_and_materialization_flag_are_passed_to_writer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "package"
            index_path = Path(temp_dir) / "indexes" / "custom.index.json"

            def fake_writer(plan, *, index_path=None, materialize_manifests=True):
                self.assertEqual(index_path, index_path_arg)
                self.assertFalse(materialize_manifests)
                return package_result_for_plan(plan, index_path)

            index_path_arg = index_path
            with patch(
                "ow_eval.shard_package_cli.write_evaluation_shard_job_package",
                side_effect=fake_writer,
            ) as writer:
                result = prepare_evaluation_shard_package(
                    (QUICK_2P,),
                    output_dir=output_dir,
                    shard_count=1,
                    index_path=index_path,
                    materialize_manifests=False,
                )

        writer.assert_called_once()
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.package_result.index_path, str(index_path))

    def test_result_is_frozen_slotted_validates_and_is_json_safe(self) -> None:
        plan = build_evaluation_shard_plan(
            (QUICK_2P,),
            ShardPlanConfig(shard_count=1, output_root="/tmp/package"),
        )
        package = package_result_for_plan(plan)
        result = EvaluationShardPackageCliResult(
            manifest_paths=(str(QUICK_2P),),
            shard_plan=plan,
            package_result=package,
            exit_code=0,
            summary_text="summary",
        )

        with self.assertRaises(FrozenInstanceError):
            result.exit_code = 1  # type: ignore[misc]
        with self.assertRaises((AttributeError, TypeError)):
            result.extra = "nope"  # type: ignore[attr-defined]
        with self.assertRaisesRegex(ValueError, "manifest_paths"):
            EvaluationShardPackageCliResult(
                manifest_paths=[str(QUICK_2P)],  # type: ignore[arg-type]
                summary_text="summary",
            )
        with self.assertRaisesRegex(ValueError, "package_result"):
            EvaluationShardPackageCliResult(
                manifest_paths=(str(QUICK_2P),),
                package_result="bad",  # type: ignore[arg-type]
                summary_text="summary",
            )

        decoded = json.loads(json.dumps(result.to_dict(), sort_keys=True))
        self.assertEqual(decoded["exit_code"], 0)
        self.assertTrue(decoded["passed"])
        self.assertEqual(decoded["package_result"]["jobs"][0]["job_id"], "job-0000")

    def test_structured_error_handling_for_planning_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = prepare_evaluation_shard_package(
                (QUICK_2P,),
                output_dir=Path(temp_dir),
                shard_count=1,
                matches_per_shard=1,
            )

        self.assertEqual(result.exit_code, 2)
        self.assertFalse(result.passed)
        self.assertIn("ValueError", result.error_text)
        self.assertEqual(
            result.summary_text,
            "evaluation_shard_package=ERROR manifests=1 exit_code=2",
        )

    def test_cli_success_prints_package_and_job_summaries(self) -> None:
        plan = build_evaluation_shard_plan(
            (QUICK_2P,),
            ShardPlanConfig(shard_count=1, output_root="/tmp/package"),
        )
        package = package_result_for_plan(plan)
        cli_result = EvaluationShardPackageCliResult(
            manifest_paths=(str(QUICK_2P),),
            shard_plan=plan,
            package_result=package,
            exit_code=0,
            summary_text=(
                "evaluation_shard_package=PASS manifests=1 shards=1 jobs=1 "
                "output_dir=/tmp/package index_path=/tmp/package/shard-jobs.index.json "
                "exit_code=0"
            ),
        )
        stdout = io.StringIO()

        with patch(
            "ow_eval.shard_package_cli.prepare_evaluation_shard_package",
            return_value=cli_result,
        ):
            with contextlib.redirect_stdout(stdout):
                exit_code = prepare_evaluation_shards_main(
                    [
                        str(QUICK_2P),
                        "--output-dir",
                        "/tmp/package",
                        "--shard-count",
                        "1",
                    ]
                )

        output = stdout.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("evaluation_shard_package=PASS", output)
        self.assertIn("shard_jobs=WRITTEN", output)
        self.assertIn("job_id=job-0000", output)
        self.assertIn("manifest_path=", output)
        self.assertIn("result_path=", output)
        self.assertIn("command=", output)

    def test_cli_help_required_output_dir_and_invalid_sharding_args(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            with self.assertRaises(SystemExit) as help_exit:
                prepare_evaluation_shards_main(["--help"])

        self.assertEqual(help_exit.exception.code, 0)
        self.assertIn("--output-dir", stdout.getvalue())
        self.assertIn("--no-materialize-manifests", stdout.getvalue())

        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as missing_output:
                prepare_evaluation_shards_main([str(QUICK_2P), "--shard-count", "1"])
        self.assertEqual(missing_output.exception.code, 2)
        self.assertIn("--output-dir", stderr.getvalue())

        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as bad_strategy:
                prepare_evaluation_shards_main(
                    [
                        str(QUICK_2P),
                        "--output-dir",
                        "/tmp/package",
                        "--shard-count",
                        "1",
                        "--matches-per-shard",
                        "1",
                    ]
                )
        self.assertEqual(bad_strategy.exception.code, 2)
        self.assertIn("not allowed with argument", stderr.getvalue())

    def test_cli_error_prints_error_text_to_stderr(self) -> None:
        cli_result = EvaluationShardPackageCliResult(
            manifest_paths=(str(QUICK_2P),),
            exit_code=2,
            summary_text="evaluation_shard_package=ERROR manifests=1 exit_code=2",
            error_text="RuntimeError: boom",
        )
        stdout = io.StringIO()
        stderr = io.StringIO()

        with patch(
            "ow_eval.shard_package_cli.prepare_evaluation_shard_package",
            return_value=cli_result,
        ):
            with contextlib.redirect_stdout(stdout):
                with contextlib.redirect_stderr(stderr):
                    exit_code = prepare_evaluation_shards_main(
                        [
                            str(QUICK_2P),
                            "--output-dir",
                            "/tmp/package",
                            "--shard-count",
                            "1",
                        ]
                    )

        self.assertEqual(exit_code, 2)
        self.assertIn("evaluation_shard_package=ERROR", stdout.getvalue())
        self.assertIn("RuntimeError: boom", stderr.getvalue())

    def test_workflow_does_not_run_matches_spawn_subprocesses_or_merge_results(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "package"

            with patch(
                "ow_eval.shard_package_cli.write_evaluation_shard_job_package",
                side_effect=lambda plan, **kwargs: package_result_for_plan(
                    plan,
                    kwargs.get("index_path"),
                ),
            ):
                with patch("ow_eval.official_runner.run_official_match") as official_runner:
                    with patch("ow_eval.shard_runner.run_evaluation_batch") as batch_runner:
                        with patch("ow_eval.shard_merge.merge_evaluation_shard_results") as merge_results:
                            with patch("subprocess.run") as subprocess_run:
                                result = prepare_evaluation_shard_package(
                                    (QUICK_2P,),
                                    output_dir=output_dir,
                                    shard_count=1,
                                )

        self.assertEqual(result.exit_code, 0)
        official_runner.assert_not_called()
        batch_runner.assert_not_called()
        merge_results.assert_not_called()
        subprocess_run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
