"""Tests for Evaluation Harness Cycle 6 sequential batch runner."""

from __future__ import annotations

import importlib
import sys
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch

from ow_eval import (
    BaselineName,
    DEFAULT_EVALUATION_ARTIFACT_DIR,
    EvaluationArtifactConfig,
    EvaluationBatchConfig,
    EvaluationBatchResult,
    EvaluationBatchSummary,
    EvaluationStatus,
    MatchConfig,
    MatchMetrics,
    MatchResult,
    OpponentSpec,
    PlayerCount,
    builtin_baseline_spec,
    run_evaluation_batch,
    summarize_match_results,
)


def batch_match_config(seed: int, label: str | None = None) -> MatchConfig:
    return MatchConfig(
        seed=seed,
        player_count=PlayerCount.TWO_PLAYER,
        controlled_seat=0,
        candidate_agent=builtin_baseline_spec(BaselineName.NOOP, name="candidate-noop"),
        opponent_agents=(
            OpponentSpec(
                builtin_baseline_spec(BaselineName.NOOP, name="opponent-noop")
            ),
        ),
        label=label or f"batch-{seed}",
    )


class EvaluationBatchRunnerTests(unittest.TestCase):
    def tearDown(self) -> None:
        for module_name in tuple(sys.modules):
            if module_name == "kaggle_environments" or module_name.startswith(
                "kaggle_environments."
            ):
                sys.modules.pop(module_name, None)

    def test_batch_module_imports_and_package_exports_are_available(self) -> None:
        module = importlib.import_module("ow_eval.batch_runner")

        self.assertIs(module.EvaluationBatchConfig, EvaluationBatchConfig)
        self.assertIs(module.EvaluationBatchResult, EvaluationBatchResult)
        self.assertIs(module.EvaluationBatchSummary, EvaluationBatchSummary)
        self.assertIs(module.run_evaluation_batch, run_evaluation_batch)
        self.assertIs(module.summarize_match_results, summarize_match_results)

    def test_batch_contracts_are_frozen_slotted_and_validate(self) -> None:
        config = EvaluationBatchConfig(matches=(batch_match_config(7),))
        result = EvaluationBatchResult()
        summary = EvaluationBatchSummary()

        with self.assertRaises(FrozenInstanceError):
            config.matches = ()  # type: ignore[misc]
        with self.assertRaises((AttributeError, TypeError)):
            result.extra = "nope"  # type: ignore[attr-defined]
        with self.assertRaises(FrozenInstanceError):
            summary.total_matches = 1  # type: ignore[misc]
        with self.assertRaisesRegex(ValueError, "matches must be a tuple"):
            EvaluationBatchConfig(matches=[batch_match_config(7)])  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "matches entries must be MatchConfig"):
            EvaluationBatchConfig(matches=("bad",))  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "artifact_prefix must be non-empty"):
            EvaluationBatchConfig(matches=(), artifact_prefix="")

    def test_summarize_match_results_counts_statuses_and_means_stably(self) -> None:
        completed = MatchResult(
            config=batch_match_config(7),
            status=EvaluationStatus.COMPLETED,
            metrics=MatchMetrics(
                final_rank=1,
                final_score=10.0,
                turns_survived=100,
            ),
        )
        import_error = MatchResult(
            config=batch_match_config(8),
            status=EvaluationStatus.IMPORT_ERROR,
            error_text="ImportError: missing",
        )
        agent_error = MatchResult(
            config=batch_match_config(9),
            status=EvaluationStatus.AGENT_ERROR,
            metrics=MatchMetrics(
                final_rank=3,
                final_score=4.0,
                turns_survived=50,
            ),
            error_text="AgentExecutionError: boom",
        )

        summary = summarize_match_results((completed, import_error, agent_error))

        self.assertEqual(summary.total_matches, 3)
        self.assertEqual(summary.completed_count, 1)
        self.assertEqual(summary.error_count, 2)
        self.assertEqual(
            summary.status_counts,
            (
                ("completed", 1),
                ("import_error", 1),
                ("agent_error", 1),
            ),
        )
        self.assertEqual(summary.mean_final_rank, 2.0)
        self.assertEqual(summary.mean_final_score, 7.0)
        self.assertEqual(summary.mean_turns_survived, 75.0)

    def test_summarize_match_results_returns_none_means_when_metrics_missing(self) -> None:
        summary = summarize_match_results(
            (
                MatchResult(
                    config=batch_match_config(7),
                    status=EvaluationStatus.IMPORT_ERROR,
                    error_text="ImportError: missing",
                ),
            )
        )

        self.assertIsNone(summary.mean_final_rank)
        self.assertIsNone(summary.mean_final_score)
        self.assertIsNone(summary.mean_turns_survived)

    def test_run_evaluation_batch_preserves_order_and_continues_failures(self) -> None:
        matches = (
            batch_match_config(7),
            batch_match_config(8),
            batch_match_config(9),
        )
        returned_results = (
            MatchResult(
                config=matches[0],
                status=EvaluationStatus.COMPLETED,
                metrics=MatchMetrics(final_rank=1),
            ),
            MatchResult(
                config=matches[1],
                status=EvaluationStatus.IMPORT_ERROR,
                error_text="ImportError: missing",
            ),
            MatchResult(
                config=matches[2],
                status=EvaluationStatus.COMPLETED,
                metrics=MatchMetrics(final_rank=2),
            ),
        )
        calls: list[tuple[MatchConfig, object]] = []

        def fake_run(match_config: MatchConfig, artifacts: object = None) -> MatchResult:
            calls.append((match_config, artifacts))
            return returned_results[len(calls) - 1]

        with patch("ow_eval.batch_runner.run_official_match", side_effect=fake_run):
            batch_result = run_evaluation_batch(EvaluationBatchConfig(matches=matches))

        self.assertEqual(batch_result.results, returned_results)
        self.assertEqual([call[0] for call in calls], list(matches))
        artifacts_seen = [call[1] for call in calls]
        self.assertTrue(
            all(isinstance(artifact, EvaluationArtifactConfig) for artifact in artifacts_seen)
        )
        self.assertEqual(
            tuple(artifact.prefix for artifact in artifacts_seen),
            ("batch-match-0000", "batch-match-0001", "batch-match-0002"),
        )
        self.assertTrue(
            all(
                artifact.output_dir == DEFAULT_EVALUATION_ARTIFACT_DIR
                for artifact in artifacts_seen
            )
        )
        self.assertEqual(batch_result.summary.total_matches, 3)
        self.assertEqual(batch_result.summary.completed_count, 2)
        self.assertEqual(batch_result.summary.error_count, 1)

    def test_run_evaluation_batch_converts_unexpected_runner_exception(self) -> None:
        match = batch_match_config(7)

        with patch(
            "ow_eval.batch_runner.run_official_match",
            side_effect=RuntimeError("unexpected"),
        ):
            batch_result = run_evaluation_batch(
                EvaluationBatchConfig(matches=(match,))
            )

        self.assertEqual(len(batch_result.results), 1)
        result = batch_result.results[0]
        self.assertIs(result.config, match)
        self.assertEqual(result.status, EvaluationStatus.UNKNOWN_ERROR)
        self.assertEqual(result.error_text, "RuntimeError: unexpected")
        self.assertEqual(batch_result.summary.error_count, 1)

    def test_artifact_prefixes_are_collision_free_and_passed_per_match(self) -> None:
        matches = (
            batch_match_config(7, label="duplicate"),
            batch_match_config(8, label="duplicate"),
        )
        artifact_config = EvaluationArtifactConfig(
            output_dir="/tmp/ow-eval-batch",
            prefix="base",
        )
        artifacts_seen: list[EvaluationArtifactConfig] = []

        def fake_run(
            match_config: MatchConfig,
            artifacts: EvaluationArtifactConfig | None = None,
        ) -> MatchResult:
            assert artifacts is not None
            artifacts_seen.append(artifacts)
            return MatchResult(config=match_config, status=EvaluationStatus.COMPLETED)

        with patch("ow_eval.batch_runner.run_official_match", side_effect=fake_run):
            run_evaluation_batch(
                EvaluationBatchConfig(
                    matches=matches,
                    artifacts=artifact_config,
                )
            )

        self.assertEqual(
            tuple(artifact.prefix for artifact in artifacts_seen),
            ("base-match-0000", "base-match-0001"),
        )
        self.assertTrue(all(artifact.output_dir == artifact_config.output_dir for artifact in artifacts_seen))
        self.assertTrue(all(artifact.write_replay for artifact in artifacts_seen))
        self.assertTrue(all(artifact.write_result for artifact in artifacts_seen))

    def test_batch_artifact_prefix_overrides_artifact_config_prefix(self) -> None:
        match = batch_match_config(7)
        artifact_config = EvaluationArtifactConfig(
            output_dir="/tmp/ow-eval-batch",
            prefix="ignored",
        )
        artifacts_seen: list[EvaluationArtifactConfig] = []

        def fake_run(
            match_config: MatchConfig,
            artifacts: EvaluationArtifactConfig | None = None,
        ) -> MatchResult:
            assert artifacts is not None
            artifacts_seen.append(artifacts)
            return MatchResult(config=match_config, status=EvaluationStatus.COMPLETED)

        with patch("ow_eval.batch_runner.run_official_match", side_effect=fake_run):
            run_evaluation_batch(
                EvaluationBatchConfig(
                    matches=(match,),
                    artifacts=artifact_config,
                    artifact_prefix="override",
                )
            )

        self.assertEqual(artifacts_seen[0].prefix, "override-match-0000")

    def test_real_small_official_batch_completes(self) -> None:
        matches = (
            batch_match_config(7),
            batch_match_config(8),
        )

        batch_result = run_evaluation_batch(EvaluationBatchConfig(matches=matches))

        self.assertEqual(tuple(result.config for result in batch_result.results), matches)
        self.assertEqual(batch_result.summary.total_matches, 2)
        self.assertEqual(batch_result.summary.completed_count, 2)
        self.assertEqual(batch_result.summary.error_count, 0)
        self.assertEqual(batch_result.summary.status_counts, (("completed", 2),))
        self.assertIsNotNone(batch_result.summary.mean_final_rank)
        self.assertIsNotNone(batch_result.summary.mean_final_score)
        self.assertIsNotNone(batch_result.summary.mean_turns_survived)

    def test_real_batch_artifacts_are_written_under_temp_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            matches = (
                batch_match_config(7, label="duplicate"),
                batch_match_config(8, label="duplicate"),
            )

            batch_result = run_evaluation_batch(
                EvaluationBatchConfig(
                    matches=matches,
                    artifacts=EvaluationArtifactConfig(output_dir=tmp),
                )
            )

            artifact_names = sorted(path.name for path in Path(tmp).iterdir())

        self.assertEqual(batch_result.summary.completed_count, 2)
        self.assertEqual(
            artifact_names,
            [
                "batch-match-0000-replay.json",
                "batch-match-0000-result.json",
                "batch-match-0001-replay.json",
                "batch-match-0001-result.json",
            ],
        )


if __name__ == "__main__":
    unittest.main()
