"""Tests for deterministic Daytona shard job plan writer and CLI."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch

from ow_eval import (
    DaytonaShardJobPlanWriteResult,
    ShardPlanConfig,
    build_daytona_shard_job_plan,
    build_evaluation_shard_plan,
    prepare_daytona_shard_job_plan,
    prepare_daytona_shard_jobs_main,
    write_evaluation_shard_job_package,
    write_daytona_shard_job_plan,
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
            label_prefix="daytona-plan",
        ),
    )
    return write_evaluation_shard_job_package(plan)


class DaytonaPlanCliTests(unittest.TestCase):
    def test_module_imports_and_exports_are_available(self) -> None:
        import ow_eval.daytona_plan_cli as daytona_plan_cli

        self.assertIs(
            daytona_plan_cli.DaytonaShardJobPlanWriteResult,
            DaytonaShardJobPlanWriteResult,
        )
        self.assertIs(
            daytona_plan_cli.prepare_daytona_shard_job_plan,
            prepare_daytona_shard_job_plan,
        )
        self.assertIs(
            daytona_plan_cli.write_daytona_shard_job_plan,
            write_daytona_shard_job_plan,
        )
        self.assertIs(daytona_plan_cli.main, prepare_daytona_shard_jobs_main)

    def test_write_plan_json_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = packaged_index(temp_dir)
            plan = build_daytona_shard_job_plan(package.index_path)
            output_path = Path(temp_dir) / "nested" / "daytona-plan.json"

            written_path = write_daytona_shard_job_plan(plan, output_path)

            self.assertEqual(written_path, output_path)
            expected = json.dumps(plan.to_dict(), sort_keys=True, indent=2) + "\n"
            self.assertEqual(output_path.read_text(encoding="utf-8"), expected)
            decoded = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(
                [spec["job_id"] for spec in decoded["specs"]],
                [job.job_id for job in package.jobs],
            )
            self.assertEqual(
                decoded["specs"][0]["worker_argv"][1],
                "scripts/run_evaluation_shard_job.py",
            )

    def test_prepare_writes_plan_with_custom_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = packaged_index(temp_dir)
            output_path = Path(temp_dir) / "daytona" / "plan.json"

            result = prepare_daytona_shard_job_plan(
                package.index_path,
                output_path=output_path,
                working_dir="/workspace/custom",
                python_command="python3",
                runner_script="scripts/run_evaluation_shard_job.py",
                sandbox_name_prefix="custom-sandbox",
            )

            self.assertEqual(result.exit_code, 0)
            self.assertTrue(result.passed)
            self.assertEqual(result.output_path, str(output_path))
            self.assertEqual(result.config.working_dir, "/workspace/custom")
            self.assertEqual(result.plan.specs[0].worker_argv[0], "python3")
            self.assertEqual(
                result.plan.specs[0].sandbox_name,
                f"custom-sandbox-0000-{package.jobs[0].label}",
            )
            decoded = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(decoded["config"]["working_dir"], "/workspace/custom")
            self.assertEqual(decoded["specs"][0]["worker_argv"][0], "python3")

    def test_no_sandbox_prefix_produces_null_sandbox_names(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = packaged_index(temp_dir)
            output_path = Path(temp_dir) / "plan.json"

            result = prepare_daytona_shard_job_plan(
                package.index_path,
                output_path=output_path,
                sandbox_name_prefix=None,
            )

            self.assertEqual(result.exit_code, 0)
            decoded = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertIsNone(decoded["config"]["sandbox_name_prefix"])
            self.assertIsNone(decoded["specs"][0]["sandbox_name"])

    def test_invalid_output_path_config_and_index_return_structured_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = packaged_index(temp_dir)

            result = prepare_daytona_shard_job_plan(
                package.index_path,
                output_path="",
            )
            self.assertEqual(result.exit_code, 2)
            self.assertIn("output_path", result.error_text)

            result = prepare_daytona_shard_job_plan(
                package.index_path,
                output_path=Path(temp_dir) / "plan.json",
                working_dir="",
            )
            self.assertEqual(result.exit_code, 2)
            self.assertIn("working_dir", result.error_text)

            result = prepare_daytona_shard_job_plan(
                Path(temp_dir) / "missing.index.json",
                output_path=Path(temp_dir) / "plan.json",
            )
            self.assertEqual(result.exit_code, 2)
            self.assertIn("FileNotFoundError", result.error_text)

    def test_write_rejects_invalid_plan_and_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = packaged_index(temp_dir)
            plan = build_daytona_shard_job_plan(package.index_path)

            with self.assertRaisesRegex(ValueError, "plan"):
                write_daytona_shard_job_plan("bad", Path(temp_dir) / "plan.json")  # type: ignore[arg-type]
            with self.assertRaisesRegex(ValueError, "path"):
                write_daytona_shard_job_plan(plan, "")  # type: ignore[arg-type]

    def test_cli_success_prints_summary_and_writes_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = packaged_index(temp_dir)
            output_path = Path(temp_dir) / "cli-plan.json"
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = prepare_daytona_shard_jobs_main(
                    [
                        package.index_path,
                        "--output-path",
                        str(output_path),
                        "--working-dir",
                        "/workspace/cli",
                        "--python-command",
                        "python3",
                        "--runner-script",
                        "scripts/run_evaluation_shard_job.py",
                        "--sandbox-name-prefix",
                        "cli-sandbox",
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertIn("daytona_shard_job_plan=WRITTEN", stdout.getvalue())
            decoded = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(decoded["config"]["working_dir"], "/workspace/cli")
            self.assertEqual(decoded["specs"][0]["worker_argv"][0], "python3")
            self.assertTrue(decoded["specs"][0]["sandbox_name"].startswith("cli-sandbox"))

    def test_cli_no_sandbox_prefix_writes_null_sandbox_names(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = packaged_index(temp_dir)
            output_path = Path(temp_dir) / "cli-plan.json"
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = prepare_daytona_shard_jobs_main(
                    [
                        package.index_path,
                        "--output-path",
                        str(output_path),
                        "--no-sandbox-name-prefix",
                    ]
                )

            self.assertEqual(exit_code, 0)
            decoded = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertIsNone(decoded["config"]["sandbox_name_prefix"])
            self.assertIsNone(decoded["specs"][0]["sandbox_name"])

    def test_cli_errors_print_to_stderr(self) -> None:
        cli_result = DaytonaShardJobPlanWriteResult(
            index_path="/tmp/missing.index.json",
            output_path="/tmp/plan.json",
            exit_code=2,
            summary_text=(
                "daytona_shard_job_plan=ERROR "
                "index_path=/tmp/missing.index.json output_path=/tmp/plan.json "
                "exit_code=2"
            ),
            error_text="FileNotFoundError: missing",
        )
        stdout = io.StringIO()
        stderr = io.StringIO()

        with patch(
            "ow_eval.daytona_plan_cli.prepare_daytona_shard_job_plan",
            return_value=cli_result,
        ):
            with contextlib.redirect_stdout(stdout):
                with contextlib.redirect_stderr(stderr):
                    exit_code = prepare_daytona_shard_jobs_main(
                        [
                            "/tmp/missing.index.json",
                            "--output-path",
                            "/tmp/plan.json",
                        ]
                    )

        self.assertEqual(exit_code, 2)
        self.assertIn("daytona_shard_job_plan=ERROR", stdout.getvalue())
        self.assertIn("FileNotFoundError: missing", stderr.getvalue())

    def test_cli_help_exits_zero(self) -> None:
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            with self.assertRaises(SystemExit) as raised:
                prepare_daytona_shard_jobs_main(["--help"])

        self.assertEqual(raised.exception.code, 0)
        self.assertIn("Daytona shard job plan", stdout.getvalue())

    def test_result_is_frozen_slotted_and_json_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = packaged_index(temp_dir)
            result = prepare_daytona_shard_job_plan(
                package.index_path,
                output_path=Path(temp_dir) / "plan.json",
            )

            with self.assertRaises(FrozenInstanceError):
                result.exit_code = 2  # type: ignore[misc]
            with self.assertRaises((AttributeError, TypeError)):
                result.extra = "nope"  # type: ignore[attr-defined]
            with self.assertRaisesRegex(ValueError, "exit_code"):
                DaytonaShardJobPlanWriteResult(
                    index_path="/tmp/index.json",
                    output_path="/tmp/plan.json",
                    exit_code=True,  # type: ignore[arg-type]
                    summary_text="summary",
                )

            decoded = json.loads(json.dumps(result.to_dict(), sort_keys=True))
            self.assertTrue(decoded["passed"])
            self.assertEqual(decoded["config"]["python_command"], ".venv/bin/python")
            self.assertEqual(len(decoded["plan"]["specs"]), 2)

    def test_prepare_does_not_call_execution_or_daytona_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = packaged_index(temp_dir)
            output_path = Path(temp_dir) / "plan.json"
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
                            result = prepare_daytona_shard_job_plan(
                                package.index_path,
                                output_path=output_path,
                            )

            self.assertEqual(result.exit_code, 0)
            subprocess_run.assert_not_called()
            run_job.assert_not_called()
            run_index.assert_not_called()
            official_runner.assert_not_called()
            self.assertNotIn("daytona", sys.modules)
            self.assertEqual(
                sorted(path.name for path in Path(temp_dir).iterdir()),
                ["package", "plan.json"],
            )


if __name__ == "__main__":
    unittest.main()
