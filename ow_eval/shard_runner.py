"""Local single-shard execution through the existing batch runner.

Distributed Evaluation Cycle 1 proves one planned ``EvaluationShard`` is
self-contained and runnable locally. It does not add Daytona execution,
parallelism, CLI orchestration, persistence, or merge behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .artifacts import EvaluationArtifactConfig, default_evaluation_artifact_config
from .batch_runner import (
    EvaluationBatchConfig,
    EvaluationBatchResult,
    run_evaluation_batch,
)
from .sharding import EvaluationShard


@dataclass(frozen=True, slots=True)
class EvaluationShardRunConfig:
    """Configuration for running exactly one local evaluation shard."""

    artifacts: EvaluationArtifactConfig | None = None
    artifact_prefix: str | None = None

    def __post_init__(self) -> None:
        if self.artifacts is not None and not isinstance(
            self.artifacts,
            EvaluationArtifactConfig,
        ):
            raise ValueError("artifacts must be an EvaluationArtifactConfig")
        if self.artifact_prefix is not None and not isinstance(
            self.artifact_prefix,
            str,
        ):
            raise ValueError("artifact_prefix must be a string")
        if self.artifact_prefix == "":
            raise ValueError("artifact_prefix must be non-empty when provided")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "artifacts": (
                _artifact_config_to_dict(self.artifacts)
                if self.artifacts is not None
                else None
            ),
            "artifact_prefix": self.artifact_prefix,
        }


@dataclass(frozen=True, slots=True)
class EvaluationShardRunResult:
    """Result for running one planned evaluation shard locally."""

    shard: EvaluationShard
    batch_result: EvaluationBatchResult
    summary_text: str

    def __post_init__(self) -> None:
        if not isinstance(self.shard, EvaluationShard):
            raise ValueError("shard must be an EvaluationShard")
        if not isinstance(self.batch_result, EvaluationBatchResult):
            raise ValueError("batch_result must be an EvaluationBatchResult")
        _validate_nonempty_string(self.summary_text, "summary_text")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "shard": self.shard.to_dict(),
            "batch_result": _batch_result_to_dict(self.batch_result),
            "summary_text": self.summary_text,
        }


def run_evaluation_shard(
    shard: EvaluationShard,
    config: EvaluationShardRunConfig | None = None,
) -> EvaluationShardRunResult:
    """Run exactly one ``EvaluationShard`` through ``run_evaluation_batch``."""

    if not isinstance(shard, EvaluationShard):
        raise ValueError("shard must be an EvaluationShard")
    effective_config = (
        config if config is not None else EvaluationShardRunConfig()
    )
    if not isinstance(effective_config, EvaluationShardRunConfig):
        raise ValueError("config must be an EvaluationShardRunConfig")

    artifacts = effective_config.artifacts or default_evaluation_artifact_config(
        output_dir=_default_artifact_output_dir_for_shard(shard),
    )
    batch_config = EvaluationBatchConfig(
        matches=shard.matches,
        artifacts=artifacts,
        artifact_prefix=_artifact_prefix_for_shard(shard, effective_config),
    )
    batch_result = run_evaluation_batch(batch_config)
    return EvaluationShardRunResult(
        shard=shard,
        batch_result=batch_result,
        summary_text=_summary_text(shard, batch_result),
    )


def _artifact_prefix_for_shard(
    shard: EvaluationShard,
    config: EvaluationShardRunConfig,
) -> str | None:
    if config.artifact_prefix is not None:
        return config.artifact_prefix
    return shard.label


def _default_artifact_output_dir_for_shard(shard: EvaluationShard) -> Path:
    return Path(shard.planned_manifest_path).parent / f"{shard.label}.artifacts"


def _summary_text(
    shard: EvaluationShard,
    batch_result: EvaluationBatchResult,
) -> str:
    summary = batch_result.summary
    return (
        f"shard_run=COMPLETE shard_id={shard.shard_id} label={shard.label} "
        f"matches={shard.match_count} completed={summary.completed_count} "
        f"errors={summary.error_count}"
    )


def _batch_result_to_dict(batch_result: EvaluationBatchResult) -> dict[str, object]:
    return {
        "results": [
            result.to_dict()
            for result in batch_result.results
        ],
        "summary": {
            "total_matches": batch_result.summary.total_matches,
            "completed_count": batch_result.summary.completed_count,
            "error_count": batch_result.summary.error_count,
            "status_counts": [
                list(item)
                for item in batch_result.summary.status_counts
            ],
            "mean_final_rank": batch_result.summary.mean_final_rank,
            "mean_final_score": batch_result.summary.mean_final_score,
            "mean_turns_survived": batch_result.summary.mean_turns_survived,
        },
    }


def _artifact_config_to_dict(
    artifact_config: EvaluationArtifactConfig,
) -> dict[str, object]:
    return {
        "output_dir": str(artifact_config.output_dir),
        "write_replay": artifact_config.write_replay,
        "write_result": artifact_config.write_result,
        "prefix": artifact_config.prefix,
    }


def _validate_nonempty_string(value: object, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


__all__ = (
    "EvaluationShardRunConfig",
    "EvaluationShardRunResult",
    "run_evaluation_shard",
)
