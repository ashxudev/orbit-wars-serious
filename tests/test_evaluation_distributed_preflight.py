"""Tests for the one-command distributed evaluation preflight."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from ow_eval import (
    DistributedEvaluationPreflightConfig,
    DistributedEvaluationPreflightResult,
    DistributedEvaluationPreflightStageResult,
    run_distributed_evaluation_preflight,
    run_distributed_evaluation_preflight_main,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = REPO_ROOT / "experiments" / "manifests"
QUICK_2P = MANIFEST_DIR / "quick-2p-smoke.json"
QUICK_4P = MANIFEST_DIR / "quick-4p-smoke.json"
EXPECTED_STAGE_NAMES = (
    "shard_package",
    "daytona_plan",
    "daytona_preflight",
    "fake_executor_dry_run",
    "fake_client_report_dry_run",
    "guarded_real_daytona_fail_closed",
)


class DistributedEvaluationPreflightTests(unittest.TestCase):
    def test_module_imports_and_exports_are_available(self) -> None:
        import ow_eval.distributed_preflight as distributed_preflight

        self.assertIs(
            distributed_preflight.DistributedEvaluationPreflightConfig,
            DistributedEvaluationPreflightConfig,
        )
        self.assertIs(
            distributed_preflight.DistributedEvaluationPreflightStageResult,
            DistributedEvaluationPreflightStageResult,
        )
        self.assertIs(
            distributed_preflight.DistributedEvaluationPreflightResult,
            DistributedEvaluationPreflightResult,
        )
        self.assertIs(
            distributed_preflight.run_distributed_evaluation_preflight,
            run_distributed_evaluation_preflight,
        )
        self.assertIs(
            distributed_preflight.main,
            run_distributed_evaluation_preflight_main,
        )

    def test_preflight_succeeds_with_default_smoke_manifests(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            sys.modules.pop("daytona", None)

            result = run_distributed_evaluation_preflight(
                output_dir=temp_dir,
                shard_count=2,
            )

            self.assertEqual(result.exit_code, 0)
            self.assertTrue(result.passed)
            self.assertEqual(
                tuple(stage.name for stage in result.stages),
                EXPECTED_STAGE_NAMES,
            )
            self.assertTrue(all(stage.passed for stage in result.stages))
            self.assertEqual(result.config.manifest_paths, (str(QUICK_2P), str(QUICK_4P)))
            self.assertIn("distributed_evaluation_preflight=PASS", result.summary_text)
            self.assertNotIn("daytona", sys.modules)
            for stage in result.stages:
                for artifact_path in stage.artifact_paths:
                    self.assertTrue(str(artifact_path).startswith(str(temp_dir)))

    def test_matches_per_shard_strategy_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_distributed_evaluation_preflight(
                (QUICK_2P, QUICK_4P),
                output_dir=temp_dir,
                shard_count=None,
                matches_per_shard=1,
            )

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.config.shard_count, None)
            self.assertEqual(result.config.matches_per_shard, 1)

    def test_absent_output_dir_uses_temp_directory_outside_repo(self) -> None:
        result = run_distributed_evaluation_preflight((QUICK_2P,), shard_count=1)

        self.assertEqual(result.exit_code, 0)
        self.assertIn("/ow-distributed-preflight-", result.output_dir)
        self.assertFalse(str(result.output_dir).startswith(str(REPO_ROOT)))

    def test_json_output_is_deterministic_and_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "nested" / "preflight.json"

            result = run_distributed_evaluation_preflight(
                (QUICK_2P,),
                output_dir=Path(temp_dir) / "artifacts",
                shard_count=1,
                json_output=output_path,
            )

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.json_output_path, str(output_path))
            expected = json.dumps(result.to_dict(), sort_keys=True, indent=2) + "\n"
            self.assertEqual(output_path.read_text(encoding="utf-8"), expected)
            self.assertEqual(
                json.loads(output_path.read_text(encoding="utf-8")),
                result.to_dict(),
            )

    def test_invalid_manifest_returns_structured_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_distributed_evaluation_preflight(
                (Path(temp_dir) / "missing.json",),
                output_dir=temp_dir,
                shard_count=1,
            )

            self.assertEqual(result.exit_code, 2)
            self.assertFalse(result.passed)
            self.assertEqual(tuple(stage.name for stage in result.stages), ("shard_package",))
            self.assertFalse(result.stages[0].passed)
            self.assertIn("RuntimeError", result.error_text)

    def test_real_daytona_stage_treats_expected_block_as_success(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_distributed_evaluation_preflight(
                (QUICK_2P,),
                output_dir=temp_dir,
                shard_count=1,
            )

            stage = result.stages[-1]
            self.assertEqual(stage.name, "guarded_real_daytona_fail_closed")
            self.assertTrue(stage.passed)
            self.assertEqual(stage.exit_code, 0)
            self.assertIn("blocked_exit_code=2", stage.summary_text)
            self.assertIn("daytona_imported=False", stage.summary_text)

    def test_cli_success_failure_and_help(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "preflight.json"
            stdout = io.StringIO()
            stderr = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                with contextlib.redirect_stderr(stderr):
                    exit_code = run_distributed_evaluation_preflight_main(
                        [
                            "--shard-count",
                            "2",
                            "--output-dir",
                            str(Path(temp_dir) / "artifacts"),
                            "--json-output",
                            str(output_path),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertIn("distributed_evaluation_preflight=PASS", stdout.getvalue())
            self.assertTrue(output_path.is_file())

            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                with contextlib.redirect_stderr(stderr):
                    exit_code = run_distributed_evaluation_preflight_main(
                        [
                            str(Path(temp_dir) / "missing.json"),
                            "--shard-count",
                            "1",
                            "--output-dir",
                            str(Path(temp_dir) / "bad"),
                        ]
                    )

            self.assertEqual(exit_code, 2)
            self.assertIn("distributed_evaluation_preflight=ERROR", stdout.getvalue())
            self.assertIn("RuntimeError", stderr.getvalue())

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            with self.assertRaises(SystemExit) as raised:
                run_distributed_evaluation_preflight_main(["--help"])
        self.assertEqual(raised.exception.code, 0)
        self.assertIn("distributed evaluation preflight", stdout.getvalue())

    def test_dataclasses_are_frozen_slotted_validated_and_json_safe(self) -> None:
        config = DistributedEvaluationPreflightConfig(
            manifest_paths=(str(QUICK_2P),),
            shard_count=1,
        )
        stage = DistributedEvaluationPreflightStageResult(
            name="stage",
            passed=True,
            exit_code=0,
            summary_text="stage ok",
        )
        result = DistributedEvaluationPreflightResult(
            config=config,
            output_dir="/tmp/preflight",
            stages=(stage,),
            exit_code=0,
            summary_text="preflight ok",
        )

        with self.assertRaises(FrozenInstanceError):
            config.shard_count = 2  # type: ignore[misc]
        with self.assertRaises((AttributeError, TypeError)):
            result.extra = "nope"  # type: ignore[attr-defined]
        with self.assertRaisesRegex(ValueError, "one sharding strategy"):
            DistributedEvaluationPreflightConfig(
                manifest_paths=(str(QUICK_2P),),
                shard_count=None,
                matches_per_shard=None,
            )
        with self.assertRaisesRegex(ValueError, "use shard_count or matches_per_shard"):
            DistributedEvaluationPreflightConfig(
                manifest_paths=(str(QUICK_2P),),
                shard_count=1,
                matches_per_shard=1,
            )

        decoded = json.loads(json.dumps(result.to_dict(), sort_keys=True))
        self.assertTrue(decoded["passed"])
        self.assertEqual(decoded["stages"][0]["name"], "stage")


if __name__ == "__main__":
    unittest.main()
