"""Local experiment-manifest runner.

Evaluation Harness Cycle 13 expands an ``ExperimentManifest`` into match
configs, runs them through the existing local batch harness, and returns
scoreboard plus planner-analysis summaries. It does not enforce promotion
decisions or submit to live Kaggle.
"""

from __future__ import annotations

from dataclasses import dataclass

from .analysis_pack import PlannerAnalysisPack, build_planner_analysis_pack
from .artifacts import EvaluationArtifactConfig
from .batch_runner import (
    EvaluationBatchConfig,
    EvaluationBatchResult,
    run_evaluation_batch,
)
from .contracts import MatchConfig
from .experiment_manifest import ExperimentManifest, manifest_to_match_configs
from .scoreboard import ScoreboardRecord, build_scoreboard_record


@dataclass(frozen=True, slots=True)
class ExperimentRunConfig:
    """Config for executing one local experiment manifest."""

    commit: str | None = None
    notes: tuple[str, ...] = ()
    artifacts: EvaluationArtifactConfig | None = None
    artifact_prefix: str | None = None

    def __post_init__(self) -> None:
        if self.commit is not None:
            _validate_nonempty_string(self.commit, "commit")
        _validate_string_tuple(self.notes, "notes")
        if self.artifacts is not None and not isinstance(
            self.artifacts,
            EvaluationArtifactConfig,
        ):
            raise ValueError("artifacts must be an EvaluationArtifactConfig")
        if self.artifact_prefix is not None:
            _validate_nonempty_string(self.artifact_prefix, "artifact_prefix")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "commit": self.commit,
            "notes": list(self.notes),
            "artifacts": _artifact_config_to_dict(self.artifacts),
            "artifact_prefix": self.artifact_prefix,
        }


@dataclass(frozen=True, slots=True)
class ExperimentRunResult:
    """Structured result from executing one local experiment manifest."""

    manifest: ExperimentManifest
    matches: tuple[MatchConfig, ...]
    batch_result: EvaluationBatchResult
    scoreboard_record: ScoreboardRecord
    analysis_pack: PlannerAnalysisPack
    summary_text: str

    def __post_init__(self) -> None:
        if not isinstance(self.manifest, ExperimentManifest):
            raise ValueError("manifest must be an ExperimentManifest")
        if not isinstance(self.matches, tuple):
            raise ValueError("matches must be a tuple")
        for match in self.matches:
            if not isinstance(match, MatchConfig):
                raise ValueError("matches entries must be MatchConfig objects")
        if not isinstance(self.batch_result, EvaluationBatchResult):
            raise ValueError("batch_result must be an EvaluationBatchResult")
        if not isinstance(self.scoreboard_record, ScoreboardRecord):
            raise ValueError("scoreboard_record must be a ScoreboardRecord")
        if not isinstance(self.analysis_pack, PlannerAnalysisPack):
            raise ValueError("analysis_pack must be a PlannerAnalysisPack")
        _validate_nonempty_string(self.summary_text, "summary_text")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "manifest": self.manifest.to_dict(),
            "matches": [
                match.to_dict()
                for match in self.matches
            ],
            "batch_result": _batch_result_to_dict(self.batch_result),
            "scoreboard_record": self.scoreboard_record.to_dict(),
            "analysis_pack": self.analysis_pack.to_dict(),
            "summary_text": self.summary_text,
        }


def run_experiment_manifest(
    manifest: ExperimentManifest,
    config: ExperimentRunConfig | None = None,
) -> ExperimentRunResult:
    """Run ``manifest`` through the local batch harness and summarize it."""

    if not isinstance(manifest, ExperimentManifest):
        raise ValueError("manifest must be an ExperimentManifest")
    effective_config = ExperimentRunConfig() if config is None else config
    matches = manifest_to_match_configs(manifest)
    batch_result = run_evaluation_batch(
        EvaluationBatchConfig(
            matches=matches,
            artifacts=effective_config.artifacts,
            artifact_prefix=effective_config.artifact_prefix,
        )
    )
    scoreboard_record = build_scoreboard_record(
        batch_result,
        agent_name=manifest.candidate_agent.name,
        agent_version=manifest.version,
        commit=effective_config.commit,
        scenario_set=manifest.name,
        notes=effective_config.notes,
        metadata=manifest.metadata,
    )
    analysis_pack = build_planner_analysis_pack(batch_result)
    summary_text = _summary_text(
        manifest=manifest,
        scoreboard_record=scoreboard_record,
        analysis_pack=analysis_pack,
    )
    return ExperimentRunResult(
        manifest=manifest,
        matches=matches,
        batch_result=batch_result,
        scoreboard_record=scoreboard_record,
        analysis_pack=analysis_pack,
        summary_text=summary_text,
    )


def _summary_text(
    *,
    manifest: ExperimentManifest,
    scoreboard_record: ScoreboardRecord,
    analysis_pack: PlannerAnalysisPack,
) -> str:
    return (
        f"experiment={manifest.name} matches={scoreboard_record.match_count} "
        f"completed={scoreboard_record.completed_count} "
        f"errors={scoreboard_record.error_count} "
        f"win_rate={_format_optional_float(scoreboard_record.win_rate)} "
        f"mean_rank={_format_optional_float(scoreboard_record.mean_rank)} "
        f"analysis_items={analysis_pack.included_count}"
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
                {"status": status, "count": count}
                for status, count in batch_result.summary.status_counts
            ],
            "mean_final_rank": batch_result.summary.mean_final_rank,
            "mean_final_score": batch_result.summary.mean_final_score,
            "mean_turns_survived": batch_result.summary.mean_turns_survived,
        },
    }


def _artifact_config_to_dict(
    artifact_config: EvaluationArtifactConfig | None,
) -> dict[str, object] | None:
    if artifact_config is None:
        return None
    return {
        "output_dir": str(artifact_config.output_dir),
        "write_replay": artifact_config.write_replay,
        "write_result": artifact_config.write_result,
        "prefix": artifact_config.prefix,
    }


def _format_optional_float(value: float | None) -> str:
    if value is None:
        return "none"
    return f"{value:.6g}"


def _validate_nonempty_string(value: object, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


def _validate_string_tuple(value: tuple[str, ...], name: str) -> None:
    if not isinstance(value, tuple):
        raise ValueError(f"{name} must be a tuple")
    for item in value:
        _validate_nonempty_string(item, name)


__all__ = (
    "ExperimentRunConfig",
    "ExperimentRunResult",
    "run_experiment_manifest",
)
