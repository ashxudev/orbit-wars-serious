"""Tests for deterministic shard result merge contracts."""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch

from ow_eval import (
    EvaluationBatchResult,
    EvaluationBatchSummary,
    EvaluationShardMergeResult,
    EvaluationShardRunResult,
    EvaluationStatus,
    MatchMetrics,
    MatchResult,
    ShardPlanConfig,
    build_evaluation_shard_plan,
    merge_evaluation_shard_result_files,
    merge_evaluation_shard_results,
    write_evaluation_shard_run_result,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = REPO_ROOT / "experiments" / "manifests"
QUICK_2P = MANIFEST_DIR / "quick-2p-smoke.json"
QUICK_4P = MANIFEST_DIR / "quick-4p-smoke.json"


def planned_shards():
    plan = build_evaluation_shard_plan(
        (QUICK_2P, QUICK_4P),
        ShardPlanConfig(
            shard_count=2,
            output_root="/tmp/ow-shards",
            label_prefix="merge",
        ),
    )
    return plan.shards


def shard_run_result(shard, ranks, statuses) -> EvaluationShardRunResult:
    results = []
    for index, match in enumerate(shard.matches):
        status = statuses[index]
        rank = ranks[index]
        results.append(
            MatchResult(
                config=match,
                status=status,
                metrics=MatchMetrics(
                    final_rank=rank,
                    final_score=float(index + 1) if rank is not None else None,
                    turns_survived=200 if status is EvaluationStatus.COMPLETED else None,
                ),
                error_text=(
                    None
                    if status is EvaluationStatus.COMPLETED
                    else "RuntimeError: synthetic"
                ),
            )
        )
    return EvaluationShardRunResult(
        shard=shard,
        batch_result=EvaluationBatchResult(
            results=tuple(results),
            summary=EvaluationBatchSummary(
                total_matches=99,
                completed_count=0,
                error_count=99,
                status_counts=(("stale", 99),),
                mean_final_rank=99.0,
            ),
        ),
        summary_text=f"stale summary for {shard.shard_id}",
    )


def two_shard_results():
    first, second = planned_shards()
    return (
        shard_run_result(
            first,
            ranks=(2, None),
            statuses=(EvaluationStatus.COMPLETED, EvaluationStatus.UNKNOWN_ERROR),
        ),
        shard_run_result(
            second,
            ranks=(1, 1),
            statuses=(EvaluationStatus.COMPLETED, EvaluationStatus.COMPLETED),
        ),
    )


class EvaluationShardMergeTests(unittest.TestCase):
    def test_module_imports_and_exports_are_available(self) -> None:
        import ow_eval.shard_merge as shard_merge

        self.assertIs(shard_merge.EvaluationShardMergeResult, EvaluationShardMergeResult)
        self.assertIs(
            shard_merge.merge_evaluation_shard_results,
            merge_evaluation_shard_results,
        )
        self.assertIs(
            shard_merge.merge_evaluation_shard_result_files,
            merge_evaluation_shard_result_files,
        )

    def test_merges_in_memory_shard_results_in_input_order(self) -> None:
        first, second = two_shard_results()

        merged = merge_evaluation_shard_results((first, second))

        self.assertEqual(merged.shard_results, (first, second))
        self.assertEqual(
            tuple(result.config.label for result in merged.batch_result.results),
            (
                "quick-2p-seed-7-seat-0",
                "quick-2p-seed-8-seat-0",
                "quick-4p-seed-7-seat-0",
                "quick-4p-seed-8-seat-2",
            ),
        )
        self.assertEqual(
            merged.summary_text,
            "shard_merge=COMPLETE shards=2 matches=4 completed=3 errors=1",
        )

    def test_merged_summary_is_recomputed_from_match_results(self) -> None:
        first, second = two_shard_results()

        merged = merge_evaluation_shard_results((first, second))
        summary = merged.batch_result.summary

        self.assertEqual(summary.total_matches, 4)
        self.assertEqual(summary.completed_count, 3)
        self.assertEqual(summary.error_count, 1)
        self.assertEqual(
            summary.status_counts,
            (("completed", 3), ("unknown_error", 1)),
        )
        self.assertAlmostEqual(summary.mean_final_rank, 4 / 3)
        self.assertEqual(summary.mean_turns_survived, 200.0)
        self.assertNotEqual(summary.status_counts, first.batch_result.summary.status_counts)

    def test_merges_persisted_shard_result_files_in_path_order(self) -> None:
        first, second = two_shard_results()

        with tempfile.TemporaryDirectory() as temp_dir:
            first_path = Path(temp_dir) / "first.json"
            second_path = Path(temp_dir) / "second.json"
            write_evaluation_shard_run_result(first, first_path)
            write_evaluation_shard_run_result(second, second_path)

            merged = merge_evaluation_shard_result_files((second_path, first_path))

        self.assertEqual(
            tuple(result.shard.shard_id for result in merged.shard_results),
            ("shard-0001", "shard-0000"),
        )
        self.assertEqual(
            tuple(result.config.label for result in merged.batch_result.results),
            (
                "quick-4p-seed-7-seat-0",
                "quick-4p-seed-8-seat-2",
                "quick-2p-seed-7-seat-0",
                "quick-2p-seed-8-seat-0",
            ),
        )

    def test_duplicate_shard_ids_are_rejected(self) -> None:
        first, _second = two_shard_results()

        with self.assertRaisesRegex(ValueError, "duplicate shard_id"):
            merge_evaluation_shard_results((first, first))

    def test_invalid_inputs_raise_clear_errors(self) -> None:
        first, _second = two_shard_results()

        with self.assertRaisesRegex(ValueError, "results"):
            merge_evaluation_shard_results(())  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "non-string sequence"):
            merge_evaluation_shard_results("bad")  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "results\\[0\\]"):
            merge_evaluation_shard_results((object(),))  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "paths"):
            merge_evaluation_shard_result_files(())  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "non-string sequence"):
            merge_evaluation_shard_result_files("bad")  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "paths\\[0\\]"):
            merge_evaluation_shard_result_files((object(),))  # type: ignore[arg-type]

        self.assertEqual(
            merge_evaluation_shard_results((first,)).batch_result.summary.total_matches,
            2,
        )

    def test_merge_result_is_frozen_slotted_and_validates(self) -> None:
        first, second = two_shard_results()
        merged = merge_evaluation_shard_results((first, second))

        with self.assertRaises(FrozenInstanceError):
            merged.summary_text = "changed"  # type: ignore[misc]
        with self.assertRaises((AttributeError, TypeError)):
            merged.extra = "nope"  # type: ignore[attr-defined]
        with self.assertRaisesRegex(ValueError, "shard_results"):
            EvaluationShardMergeResult(
                shard_results=[first],  # type: ignore[arg-type]
                batch_result=merged.batch_result,
                summary_text="summary",
            )
        with self.assertRaisesRegex(ValueError, "batch_result"):
            EvaluationShardMergeResult(
                shard_results=(first,),
                batch_result="bad",  # type: ignore[arg-type]
                summary_text="summary",
            )

    def test_to_dict_output_is_json_safe(self) -> None:
        first, second = two_shard_results()
        merged = merge_evaluation_shard_results((first, second))

        decoded = json.loads(json.dumps(merged.to_dict(), sort_keys=True))

        self.assertEqual(decoded["summary_text"], merged.summary_text)
        self.assertEqual(len(decoded["shard_results"]), 2)
        self.assertEqual(decoded["batch_result"]["summary"]["total_matches"], 4)
        self.assertEqual(
            decoded["batch_result"]["results"][0]["config"]["label"],
            "quick-2p-seed-7-seat-0",
        )

    def test_merge_does_not_run_matches_spawn_workers_or_write_files(self) -> None:
        first, second = two_shard_results()

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with patch("ow_eval.official_runner.run_official_match") as official_runner:
                with patch("ow_eval.shard_runner.run_evaluation_batch") as batch_runner:
                    with patch("subprocess.run") as subprocess_run:
                        merged = merge_evaluation_shard_results((first, second))

            self.assertEqual(merged.batch_result.summary.total_matches, 4)
            official_runner.assert_not_called()
            batch_runner.assert_not_called()
            subprocess_run.assert_not_called()
            self.assertEqual(list(root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
