"""Tests for sequential local multi-shard workflow and CLI."""

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
    EvaluationBatchResult,
    EvaluationBatchSummary,
    EvaluationShardCliResult,
    EvaluationShardMergeResult,
    EvaluationShardRunResult,
    EvaluationStatus,
    MatchMetrics,
    MatchResult,
    ShardPlanConfig,
    build_evaluation_shard_plan,
    merge_evaluation_shard_results,
    run_evaluation_shards,
    run_evaluation_shards_main,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = REPO_ROOT / "experiments" / "manifests"
QUICK_2P = MANIFEST_DIR / "quick-2p-smoke.json"
QUICK_4P = MANIFEST_DIR / "quick-4p-smoke.json"


def completed_shard_result(shard) -> EvaluationShardRunResult:
    results = tuple(
        MatchResult(
            config=match,
            status=EvaluationStatus.COMPLETED,
            metrics=MatchMetrics(
                final_rank=1,
                final_score=float(index + 1),
                turns_survived=200,
            ),
        )
        for index, match in enumerate(shard.matches)
    )
    return EvaluationShardRunResult(
        shard=shard,
        batch_result=EvaluationBatchResult(
            results=results,
            summary=EvaluationBatchSummary(
                total_matches=len(results),
                completed_count=len(results),
                error_count=0,
                status_counts=(("completed", len(results)),),
                mean_final_rank=1.0,
                mean_final_score=1.0,
                mean_turns_survived=200.0,
            ),
        ),
        summary_text=(
            f"shard_run=COMPLETE shard_id={shard.shard_id} "
            f"label={shard.label} matches={shard.match_count} "
            f"completed={len(results)} errors=0"
        ),
    )


class EvaluationShardCliTests(unittest.TestCase):
    def test_module_imports_and_exports_are_available(self) -> None:
        import ow_eval.shard_cli as shard_cli

        self.assertIs(shard_cli.EvaluationShardCliResult, EvaluationShardCliResult)
        self.assertIs(shard_cli.run_evaluation_shards, run_evaluation_shards)
        self.assertIs(shard_cli.main, run_evaluation_shards_main)

    def test_planning_by_shard_count_runs_shards_in_plan_order(self) -> None:
        seen_shard_ids = []

        def fake_run(shard):
            seen_shard_ids.append(shard.shard_id)
            return completed_shard_result(shard)

        with patch("ow_eval.shard_cli.run_evaluation_shard", side_effect=fake_run):
            result = run_evaluation_shards(
                (QUICK_2P, QUICK_4P),
                shard_count=2,
                label_prefix="local",
            )

        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.passed)
        self.assertEqual(seen_shard_ids, ["shard-0000", "shard-0001"])
        self.assertEqual(result.shard_plan.config.shard_count, 2)
        self.assertEqual(tuple(shard.label for shard in result.shard_plan.shards), ("local-0000", "local-0001"))
        self.assertEqual(
            tuple(
                shard_result.shard.shard_id
                for shard_result in result.shard_run_results
            ),
            ("shard-0000", "shard-0001"),
        )
        self.assertEqual(result.merged_result.batch_result.summary.total_matches, 4)
        self.assertEqual(result.shard_result_paths, ())
        self.assertEqual(
            result.summary_text,
            (
                "evaluation_shards=PASS manifests=2 shards=2 matches=4 "
                "completed=4 errors=0 output_dir=none exit_code=0"
            ),
        )

    def test_planning_by_matches_per_shard_uses_contiguous_chunks(self) -> None:
        with patch(
            "ow_eval.shard_cli.run_evaluation_shard",
            side_effect=completed_shard_result,
        ):
            result = run_evaluation_shards(
                (QUICK_2P, QUICK_4P),
                matches_per_shard=3,
                label_prefix="chunk",
            )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.shard_plan.config.matches_per_shard, 3)
        self.assertEqual(tuple(shard.match_count for shard in result.shard_plan.shards), (3, 1))
        self.assertEqual(tuple(shard.label for shard in result.shard_plan.shards), ("chunk-0000", "chunk-0001"))

    def test_no_files_are_written_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with patch(
                "ow_eval.shard_cli.run_evaluation_shard",
                side_effect=completed_shard_result,
            ):
                with patch("ow_eval.shard_cli.write_evaluation_shard_run_result") as write_result:
                    result = run_evaluation_shards(
                        (QUICK_2P,),
                        shard_count=1,
                        label_prefix="dry",
                    )

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.shard_result_paths, ())
            write_result.assert_not_called()
            self.assertEqual(list(root.iterdir()), [])

    def test_output_dir_persists_each_shard_result_to_stable_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "shard-results"

            def fake_write(result, path):
                _ = result
                return Path(path)

            with patch(
                "ow_eval.shard_cli.run_evaluation_shard",
                side_effect=completed_shard_result,
            ):
                with patch(
                    "ow_eval.shard_cli.write_evaluation_shard_run_result",
                    side_effect=fake_write,
                ) as write_result:
                    result = run_evaluation_shards(
                        (QUICK_2P, QUICK_4P),
                        shard_count=2,
                        output_dir=output_dir,
                        label_prefix="persist",
                    )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(
            result.shard_result_paths,
            (
                str(output_dir / "persist-0000.shard-result.json"),
                str(output_dir / "persist-0001.shard-result.json"),
            ),
        )
        self.assertEqual(write_result.call_count, 2)
        self.assertEqual(
            tuple(call.args[1] for call in write_result.call_args_list),
            (
                output_dir / "persist-0000.shard-result.json",
                output_dir / "persist-0001.shard-result.json",
            ),
        )

    def test_merged_result_is_built_from_shard_run_results(self) -> None:
        plan = build_evaluation_shard_plan(
            (QUICK_2P,),
            ShardPlanConfig(shard_count=1, label_prefix="merge"),
        )
        shard_result = completed_shard_result(plan.shards[0])
        merged_result = merge_evaluation_shard_results((shard_result,))

        with patch(
            "ow_eval.shard_cli.run_evaluation_shard",
            return_value=shard_result,
        ):
            with patch(
                "ow_eval.shard_cli.merge_evaluation_shard_results",
                return_value=merged_result,
            ) as merge_results:
                result = run_evaluation_shards(
                    (QUICK_2P,),
                    shard_count=1,
                    label_prefix="merge",
                )

        merge_results.assert_called_once_with((shard_result,))
        self.assertIs(result.merged_result, merged_result)

    def test_result_is_frozen_slotted_and_validates(self) -> None:
        plan = build_evaluation_shard_plan((QUICK_2P,), ShardPlanConfig(shard_count=1))
        shard_result = completed_shard_result(plan.shards[0])
        merged_result = merge_evaluation_shard_results((shard_result,))
        result = EvaluationShardCliResult(
            manifest_paths=(str(QUICK_2P),),
            shard_plan=plan,
            shard_run_results=(shard_result,),
            merged_result=merged_result,
            exit_code=0,
            summary_text="summary",
        )

        with self.assertRaises(FrozenInstanceError):
            result.exit_code = 1  # type: ignore[misc]
        with self.assertRaises((AttributeError, TypeError)):
            result.extra = "nope"  # type: ignore[attr-defined]
        with self.assertRaisesRegex(ValueError, "manifest_paths"):
            EvaluationShardCliResult(
                manifest_paths=[str(QUICK_2P)],  # type: ignore[arg-type]
                summary_text="summary",
            )
        with self.assertRaisesRegex(ValueError, "shard_plan"):
            EvaluationShardCliResult(
                manifest_paths=(str(QUICK_2P),),
                shard_plan="bad",  # type: ignore[arg-type]
                summary_text="summary",
            )

    def test_to_dict_output_is_json_safe(self) -> None:
        with patch(
            "ow_eval.shard_cli.run_evaluation_shard",
            side_effect=completed_shard_result,
        ):
            result = run_evaluation_shards((QUICK_2P,), shard_count=1)

        decoded = json.loads(json.dumps(result.to_dict(), sort_keys=True))

        self.assertEqual(decoded["exit_code"], 0)
        self.assertTrue(decoded["passed"])
        self.assertEqual(decoded["shard_plan"]["total_matches"], 2)
        self.assertEqual(decoded["merged_result"]["batch_result"]["summary"]["total_matches"], 2)

    def test_api_returns_structured_error_for_planning_errors(self) -> None:
        result = run_evaluation_shards(
            (QUICK_2P,),
            shard_count=1,
            matches_per_shard=1,
        )

        self.assertEqual(result.exit_code, 2)
        self.assertFalse(result.passed)
        self.assertIn("ValueError", result.error_text)
        self.assertEqual(result.summary_text, "evaluation_shards=ERROR manifests=1 exit_code=2")

    def test_cli_success_prints_top_level_child_and_merge_summaries(self) -> None:
        cli_result = EvaluationShardCliResult(
            manifest_paths=(str(QUICK_2P),),
            shard_run_results=(
                completed_shard_result(
                    build_evaluation_shard_plan(
                        (QUICK_2P,),
                        ShardPlanConfig(shard_count=1),
                    ).shards[0]
                ),
            ),
            merged_result=merge_evaluation_shard_results(
                (
                    completed_shard_result(
                        build_evaluation_shard_plan(
                            (QUICK_2P,),
                            ShardPlanConfig(shard_count=1),
                        ).shards[0]
                    ),
                )
            ),
            exit_code=0,
            summary_text="evaluation_shards=PASS manifests=1 shards=1 matches=2 completed=2 errors=0 output_dir=none exit_code=0",
        )

        stdout = io.StringIO()
        with patch("ow_eval.shard_cli.run_evaluation_shards", return_value=cli_result):
            with contextlib.redirect_stdout(stdout):
                exit_code = run_evaluation_shards_main(
                    [str(QUICK_2P), "--shard-count", "1"],
                )

        self.assertEqual(exit_code, 0)
        output = stdout.getvalue()
        self.assertIn("evaluation_shards=PASS", output)
        self.assertIn("shard_run=COMPLETE", output)
        self.assertIn("shard_merge=COMPLETE", output)

    def test_cli_help_and_invalid_sharding_args(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            with self.assertRaises(SystemExit) as help_exit:
                run_evaluation_shards_main(["--help"])

        self.assertEqual(help_exit.exception.code, 0)
        self.assertIn("--shard-count", stdout.getvalue())
        self.assertIn("--matches-per-shard", stdout.getvalue())

        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as bad_exit:
                run_evaluation_shards_main(
                    [
                        str(QUICK_2P),
                        "--shard-count",
                        "1",
                        "--matches-per-shard",
                        "1",
                    ]
                )

        self.assertEqual(bad_exit.exception.code, 2)
        self.assertIn("not allowed with argument", stderr.getvalue())

    def test_cli_error_prints_error_text_to_stderr(self) -> None:
        cli_result = EvaluationShardCliResult(
            manifest_paths=(str(QUICK_2P),),
            exit_code=2,
            summary_text="evaluation_shards=ERROR manifests=1 exit_code=2",
            error_text="RuntimeError: boom",
        )
        stdout = io.StringIO()
        stderr = io.StringIO()

        with patch("ow_eval.shard_cli.run_evaluation_shards", return_value=cli_result):
            with contextlib.redirect_stdout(stdout):
                with contextlib.redirect_stderr(stderr):
                    exit_code = run_evaluation_shards_main(
                        [str(QUICK_2P), "--shard-count", "1"],
                    )

        self.assertEqual(exit_code, 2)
        self.assertIn("evaluation_shards=ERROR", stdout.getvalue())
        self.assertIn("RuntimeError: boom", stderr.getvalue())

    def test_workflow_does_not_run_official_matches_spawn_subprocesses_or_call_daytona(
        self,
    ) -> None:
        with patch(
            "ow_eval.shard_cli.run_evaluation_shard",
            side_effect=completed_shard_result,
        ):
            with patch("ow_eval.official_runner.run_official_match") as official_runner:
                with patch("subprocess.run") as subprocess_run:
                    result = run_evaluation_shards((QUICK_2P,), shard_count=1)

        self.assertEqual(result.exit_code, 0)
        official_runner.assert_not_called()
        subprocess_run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
