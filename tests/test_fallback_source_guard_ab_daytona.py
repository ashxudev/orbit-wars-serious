"""Tests for fallback source-guard A/B Daytona packaging."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

from ow_eval import EvaluationBatchResult, EvaluationBatchSummary
from ow_eval.contracts import EvaluationStatus, MatchMetrics, MatchResult
from ow_eval.shard_persistence import write_evaluation_shard_run_result
from ow_eval.shard_runner import EvaluationShardRunResult
from ow_eval.shard_index_runner import read_evaluation_shard_job_index


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PREPARE_SCRIPT = _load_script(
    "prepare_fallback_source_guard_ab_daytona_package",
    REPO_ROOT / "scripts" / "prepare_fallback_source_guard_ab_daytona_package.py",
)
ANALYZE_SCRIPT = _load_script(
    "analyze_fallback_source_guard_ab_daytona",
    REPO_ROOT / "scripts" / "analyze_fallback_source_guard_ab_daytona.py",
)


class FallbackSourceGuardABDaytonaTests(unittest.TestCase):
    def test_package_contains_two_cells_and_twelve_full_horizon_matches(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "ab"

            summary = PREPARE_SCRIPT.prepare_fallback_source_guard_ab_package(
                output_root,
            )
            index = read_evaluation_shard_job_index(summary["index_path"])

            self.assertEqual(summary["jobs"], 4)
            self.assertEqual(summary["matches"], 12)
            self.assertEqual(summary["episode_steps"], ["500"])
            self.assertEqual(len(index.jobs), 4)
            self.assertEqual([len(job.match_labels) for job in index.jobs], [3, 3, 3, 3])

            manifest_text = "\n".join(
                Path(job.manifest_path).read_text(encoding="utf-8")
                for job in index.jobs
            )

            self.assertIn("historical_opponents/agents/claude_v3_wide_search_forecast.py", manifest_text)
            self.assertIn("agents.fallback_source_guard", manifest_text)
            self.assertIn("fallback_source_guard_ab_cell", manifest_text)
            self.assertIn("base-historical-gauntlet-2p-500", manifest_text)
            self.assertIn("source-guard-historical-gauntlet-4p-500", manifest_text)

    def test_analyzer_summarizes_shard_results_by_cell(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "ab"
            summary = PREPARE_SCRIPT.prepare_fallback_source_guard_ab_package(
                output_root,
            )
            index = read_evaluation_shard_job_index(summary["index_path"])
            shard = index.jobs[0]
            from ow_eval.shard_job_runner import evaluation_shard_from_job

            reconstructed = evaluation_shard_from_job(shard)
            result = EvaluationShardRunResult(
                shard=reconstructed,
                batch_result=EvaluationBatchResult(
                    results=tuple(
                        MatchResult(
                            config=match,
                            status=EvaluationStatus.COMPLETED,
                            metrics=MatchMetrics(
                                final_rank=2,
                                final_production=0,
                                turns_survived=160,
                                no_action_count=5,
                                no_action_with_owned_production_count=2,
                                enemy_target_action_count=3,
                                neutral_target_action_count=4,
                                own_transfer_action_count=1,
                                production_collapse=True,
                            ),
                        )
                        for match in reconstructed.matches
                    ),
                    summary=EvaluationBatchSummary(
                        total_matches=3,
                        completed_count=3,
                        error_count=0,
                        status_counts=(("completed", 3),),
                        mean_final_rank=2.0,
                        mean_turns_survived=160.0,
                    ),
                ),
                summary_text="shard_run=COMPLETE matches=3 completed=3 errors=0",
            )
            write_evaluation_shard_run_result(result, shard.shard_result_path)

            analysis = ANALYZE_SCRIPT.analyze_fallback_source_guard_ab_daytona(
                output_root,
            )

            self.assertEqual(
                analysis["summary_text"],
                "fallback_source_guard_ab_analysis matches=3 cells=1 shards=1",
            )
            aggregate = analysis["aggregate_by_cell"]
            self.assertIn("base", aggregate)
            self.assertEqual(aggregate["base"]["match_count"], 3)
            self.assertEqual(aggregate["base"]["production_collapse_count"], 3)
            self.assertEqual(aggregate["base"]["total_own_transfer_action_count"], 3)


if __name__ == "__main__":
    unittest.main()
