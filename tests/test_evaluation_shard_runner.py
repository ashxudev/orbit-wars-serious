"""Tests for local single-shard evaluation runner contracts."""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch

from ow_eval import (
    EvaluationArtifactConfig,
    EvaluationBatchConfig,
    EvaluationBatchResult,
    EvaluationBatchSummary,
    EvaluationShardRunConfig,
    EvaluationShardRunResult,
    EvaluationStatus,
    MatchResult,
    ShardPlanConfig,
    build_evaluation_shard_plan,
    run_evaluation_shard,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
QUICK_2P = REPO_ROOT / "experiments" / "manifests" / "quick-2p-smoke.json"


def planned_shard(output_root: str | Path = "/tmp/ow-shards"):
    plan = build_evaluation_shard_plan(
        (QUICK_2P,),
        ShardPlanConfig(
            shard_count=1,
            output_root=output_root,
            label_prefix="single",
        ),
    )
    return plan.shards[0]


def completed_batch_result(shard) -> EvaluationBatchResult:
    return EvaluationBatchResult(
        results=(
            MatchResult(
                config=shard.matches[0],
                status=EvaluationStatus.COMPLETED,
            ),
        ),
        summary=EvaluationBatchSummary(
            total_matches=shard.match_count,
            completed_count=1,
            error_count=1,
            status_counts=(("completed", 1), ("unknown_error", 1)),
            mean_final_rank=1.0,
            mean_final_score=0.0,
            mean_turns_survived=200.0,
        ),
    )


class EvaluationShardRunnerTests(unittest.TestCase):
    def test_module_imports_and_exports_are_available(self) -> None:
        import ow_eval.shard_runner as shard_runner

        self.assertIs(shard_runner.EvaluationShardRunConfig, EvaluationShardRunConfig)
        self.assertIs(shard_runner.EvaluationShardRunResult, EvaluationShardRunResult)
        self.assertIs(shard_runner.run_evaluation_shard, run_evaluation_shard)

    def test_runner_passes_exact_shard_matches_to_batch_runner(self) -> None:
        shard = planned_shard()
        batch_result = completed_batch_result(shard)

        with patch(
            "ow_eval.shard_runner.run_evaluation_batch",
            return_value=batch_result,
        ) as run_batch:
            result = run_evaluation_shard(shard)

        run_batch.assert_called_once()
        batch_config = run_batch.call_args.args[0]
        self.assertIsInstance(batch_config, EvaluationBatchConfig)
        self.assertIs(batch_config.matches, shard.matches)
        self.assertIsNone(batch_config.artifacts)
        self.assertIsNone(batch_config.artifact_prefix)
        self.assertIs(result.shard, shard)
        self.assertIs(result.batch_result, batch_result)
        self.assertEqual(
            result.summary_text,
            (
                "shard_run=COMPLETE shard_id=shard-0000 label=single-0000 "
                "matches=2 completed=1 errors=1"
            ),
        )

    def test_default_run_writes_no_artifacts_and_ignores_planned_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "planned-output"
            shard = planned_shard(output_root)

            with patch(
                "ow_eval.shard_runner.run_evaluation_batch",
                return_value=completed_batch_result(shard),
            ) as run_batch:
                run_evaluation_shard(shard)

            batch_config = run_batch.call_args.args[0]
            self.assertIsNone(batch_config.artifacts)
            self.assertIsNone(batch_config.artifact_prefix)
            self.assertFalse(output_root.exists())

    def test_artifact_config_uses_shard_label_as_default_prefix(self) -> None:
        shard = planned_shard()
        artifacts = EvaluationArtifactConfig(
            output_dir="/tmp/ow-shard-artifacts",
            prefix="caller-prefix",
        )

        with patch(
            "ow_eval.shard_runner.run_evaluation_batch",
            return_value=completed_batch_result(shard),
        ) as run_batch:
            run_evaluation_shard(
                shard,
                EvaluationShardRunConfig(artifacts=artifacts),
            )

        batch_config = run_batch.call_args.args[0]
        self.assertIs(batch_config.artifacts, artifacts)
        self.assertEqual(batch_config.artifact_prefix, shard.label)

    def test_explicit_artifact_prefix_overrides_shard_label(self) -> None:
        shard = planned_shard()
        artifacts = EvaluationArtifactConfig(output_dir="/tmp/ow-shard-artifacts")

        with patch(
            "ow_eval.shard_runner.run_evaluation_batch",
            return_value=completed_batch_result(shard),
        ) as run_batch:
            run_evaluation_shard(
                shard,
                EvaluationShardRunConfig(
                    artifacts=artifacts,
                    artifact_prefix="custom-shard-prefix",
                ),
            )

        batch_config = run_batch.call_args.args[0]
        self.assertIs(batch_config.artifacts, artifacts)
        self.assertEqual(batch_config.artifact_prefix, "custom-shard-prefix")

    def test_invalid_inputs_raise_clear_errors(self) -> None:
        shard = planned_shard()

        with self.assertRaisesRegex(ValueError, "shard"):
            run_evaluation_shard("bad")  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "config"):
            run_evaluation_shard(shard, object())  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "artifacts"):
            EvaluationShardRunConfig(artifacts="bad")  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "artifact_prefix"):
            EvaluationShardRunConfig(artifact_prefix=5)  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "artifact_prefix"):
            EvaluationShardRunConfig(artifact_prefix="")
        with self.assertRaisesRegex(ValueError, "batch_result"):
            EvaluationShardRunResult(
                shard=shard,
                batch_result="bad",  # type: ignore[arg-type]
                summary_text="summary",
            )

    def test_config_and_result_are_frozen_slotted(self) -> None:
        shard = planned_shard()
        config = EvaluationShardRunConfig()
        result = EvaluationShardRunResult(
            shard=shard,
            batch_result=completed_batch_result(shard),
            summary_text="summary",
        )

        with self.assertRaises(FrozenInstanceError):
            config.artifact_prefix = "changed"  # type: ignore[misc]
        with self.assertRaises((AttributeError, TypeError)):
            config.extra = "nope"  # type: ignore[attr-defined]
        with self.assertRaises(FrozenInstanceError):
            result.summary_text = "changed"  # type: ignore[misc]
        with self.assertRaises((AttributeError, TypeError)):
            result.extra = "nope"  # type: ignore[attr-defined]

    def test_to_dict_output_is_json_safe(self) -> None:
        shard = planned_shard()
        artifacts = EvaluationArtifactConfig(
            output_dir="/tmp/ow-shard-artifacts",
            write_replay=False,
        )
        config = EvaluationShardRunConfig(
            artifacts=artifacts,
            artifact_prefix="prefix",
        )
        result = EvaluationShardRunResult(
            shard=shard,
            batch_result=completed_batch_result(shard),
            summary_text="summary",
        )

        encoded_config = json.dumps(config.to_dict(), sort_keys=True)
        encoded_result = json.dumps(result.to_dict(), sort_keys=True)

        self.assertEqual(json.loads(encoded_config)["artifact_prefix"], "prefix")
        self.assertEqual(
            json.loads(encoded_config)["artifacts"]["output_dir"],
            "/tmp/ow-shard-artifacts",
        )
        decoded_result = json.loads(encoded_result)
        self.assertEqual(decoded_result["summary_text"], "summary")
        self.assertEqual(decoded_result["shard"]["match_count"], 2)
        self.assertEqual(decoded_result["batch_result"]["summary"]["total_matches"], 2)


if __name__ == "__main__":
    unittest.main()
