"""Tests for deterministic shard-run result JSON persistence."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ow_eval import (
    EvaluationBatchResult,
    EvaluationBatchSummary,
    EvaluationShardRunResult,
    EvaluationStatus,
    MatchMetrics,
    MatchResult,
    ShardPlanConfig,
    build_evaluation_shard_plan,
    read_evaluation_shard_run_result,
    write_evaluation_shard_run_result,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
QUICK_2P = REPO_ROOT / "experiments" / "manifests" / "quick-2p-smoke.json"


def planned_shard(output_root: str | Path = "/tmp/ow-shards"):
    plan = build_evaluation_shard_plan(
        (QUICK_2P,),
        ShardPlanConfig(
            shard_count=1,
            output_root=output_root,
            label_prefix="persist",
        ),
    )
    return plan.shards[0]


def shard_run_result(output_root: str | Path = "/tmp/ow-shards") -> EvaluationShardRunResult:
    shard = planned_shard(output_root)
    batch_result = EvaluationBatchResult(
        results=(
            MatchResult(
                config=shard.matches[0],
                status=EvaluationStatus.COMPLETED,
                metrics=MatchMetrics(
                    final_rank=1,
                    final_score=12.5,
                    final_planets=4,
                    final_ships=81,
                    final_production=6,
                    turns_survived=200,
                    no_action_count=3,
                    error_count=0,
                    invalid_action_count=0,
                    timeout_count=0,
                ),
                replay_path="/tmp/replay-a.json",
                artifact_path="/tmp/result-a.json",
                metadata=(("selected", "minimum_capture"),),
            ),
            MatchResult(
                config=shard.matches[1],
                status=EvaluationStatus.UNKNOWN_ERROR,
                error_text="RuntimeError: boom",
                metadata=(("failure", "synthetic"),),
            ),
        ),
        summary=EvaluationBatchSummary(
            total_matches=2,
            completed_count=1,
            error_count=1,
            status_counts=(("completed", 1), ("unknown_error", 1)),
            mean_final_rank=1.0,
            mean_final_score=12.5,
            mean_turns_survived=200.0,
        ),
    )
    return EvaluationShardRunResult(
        shard=shard,
        batch_result=batch_result,
        summary_text=(
            "shard_run=COMPLETE shard_id=shard-0000 label=persist-0000 "
            "matches=2 completed=1 errors=1"
        ),
    )


def write_payload(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")


class EvaluationShardPersistenceTests(unittest.TestCase):
    def test_module_imports_and_exports_are_available(self) -> None:
        import ow_eval.shard_persistence as shard_persistence

        self.assertIs(
            shard_persistence.write_evaluation_shard_run_result,
            write_evaluation_shard_run_result,
        )
        self.assertIs(
            shard_persistence.read_evaluation_shard_run_result,
            read_evaluation_shard_run_result,
        )

    def test_write_uses_deterministic_json_format_and_trailing_newline(self) -> None:
        result = shard_run_result()

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "nested" / "shard-result.json"

            returned_path = write_evaluation_shard_run_result(result, output_path)

            self.assertEqual(returned_path, output_path)
            self.assertEqual(
                output_path.read_text(encoding="utf-8"),
                json.dumps(result.to_dict(), sort_keys=True, indent=2) + "\n",
            )
            self.assertTrue(output_path.read_text(encoding="utf-8").endswith("\n"))

    def test_read_reconstructs_typed_objects_and_round_trips_to_dict(self) -> None:
        result = shard_run_result()

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "shard-result.json"
            write_evaluation_shard_run_result(result, output_path)

            loaded = read_evaluation_shard_run_result(output_path)

        self.assertIsInstance(loaded, EvaluationShardRunResult)
        self.assertEqual(loaded.to_dict(), result.to_dict())
        self.assertEqual(loaded.shard.matches[0].label, "quick-2p-seed-7-seat-0")
        self.assertEqual(
            loaded.batch_result.results[0].metrics.final_production,
            6,
        )
        self.assertEqual(
            loaded.batch_result.summary.status_counts,
            (("completed", 1), ("unknown_error", 1)),
        )

    def test_parent_directories_are_created_only_for_requested_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            planned_output_root = root / "planned-output"
            output_path = root / "requested" / "result.json"
            result = shard_run_result(planned_output_root)

            write_evaluation_shard_run_result(result, output_path)

            self.assertTrue(output_path.is_file())
            self.assertFalse(planned_output_root.exists())
            self.assertEqual(
                sorted(
                    path.relative_to(root).as_posix()
                    for path in root.rglob("*")
                    if path.is_file()
                ),
                ["requested/result.json"],
            )

    def test_malformed_top_level_payloads_raise_clear_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "bad.json"

            write_payload(path, [])
            with self.assertRaisesRegex(ValueError, "object"):
                read_evaluation_shard_run_result(path)

            write_payload(path, {"batch_result": {}, "summary_text": "summary"})
            with self.assertRaisesRegex(ValueError, "shard"):
                read_evaluation_shard_run_result(path)

            write_payload(path, {"shard": {}, "summary_text": "summary"})
            with self.assertRaisesRegex(ValueError, "batch_result"):
                read_evaluation_shard_run_result(path)

    def test_malformed_nested_shard_payloads_raise_clear_errors(self) -> None:
        payload = shard_run_result().to_dict()

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "bad.json"

            bad_matches = dict(payload)
            bad_matches["shard"] = dict(payload["shard"])
            bad_matches["shard"]["matches"] = "bad"
            write_payload(path, bad_matches)
            with self.assertRaisesRegex(ValueError, "shard.matches"):
                read_evaluation_shard_run_result(path)

            bad_count = dict(payload)
            bad_count["shard"] = dict(payload["shard"])
            bad_count["shard"]["match_count"] = 99
            write_payload(path, bad_count)
            with self.assertRaisesRegex(ValueError, "match_count"):
                read_evaluation_shard_run_result(path)

            bad_seed = dict(payload)
            bad_seed["shard"] = dict(payload["shard"])
            bad_seed["shard"]["seeds"] = [True]
            write_payload(path, bad_seed)
            with self.assertRaisesRegex(ValueError, "seeds"):
                read_evaluation_shard_run_result(path)

    def test_malformed_nested_batch_payloads_raise_clear_errors(self) -> None:
        payload = shard_run_result().to_dict()

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "bad.json"

            bad_results = dict(payload)
            bad_results["batch_result"] = dict(payload["batch_result"])
            bad_results["batch_result"]["results"] = ["bad"]
            write_payload(path, bad_results)
            with self.assertRaisesRegex(ValueError, "batch_result.results"):
                read_evaluation_shard_run_result(path)

            bad_summary = dict(payload)
            bad_summary["batch_result"] = dict(payload["batch_result"])
            bad_summary["batch_result"]["summary"] = "bad"
            write_payload(path, bad_summary)
            with self.assertRaisesRegex(ValueError, "summary"):
                read_evaluation_shard_run_result(path)

            bad_status_counts = dict(payload)
            bad_status_counts["batch_result"] = dict(payload["batch_result"])
            bad_status_counts["batch_result"]["summary"] = dict(
                payload["batch_result"]["summary"]
            )
            bad_status_counts["batch_result"]["summary"]["status_counts"] = [
                ["completed"]
            ]
            write_payload(path, bad_status_counts)
            with self.assertRaisesRegex(ValueError, "status_counts"):
                read_evaluation_shard_run_result(path)

    def test_persistence_does_not_run_matches_or_write_non_requested_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            result = shard_run_result(root / "planned-output")
            output_path = root / "requested" / "result.json"

            with patch("ow_eval.official_runner.run_official_match") as official_runner:
                with patch("ow_eval.shard_runner.run_evaluation_batch") as batch_runner:
                    write_evaluation_shard_run_result(result, output_path)
                    loaded = read_evaluation_shard_run_result(output_path)

            self.assertEqual(loaded.to_dict(), result.to_dict())
            official_runner.assert_not_called()
            batch_runner.assert_not_called()
            self.assertFalse((root / "planned-output").exists())


if __name__ == "__main__":
    unittest.main()
