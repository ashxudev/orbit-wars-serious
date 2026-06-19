"""Deterministic merge contracts for completed evaluation shard results.

Distributed Evaluation Cycle 3 combines completed shard-run results into one
aggregate batch result for existing local analysis flows. It does not run
matches, dispatch workers, call Daytona, add CLI orchestration, or enforce
promotion gates.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .batch_runner import (
    EvaluationBatchResult,
    summarize_match_results,
)
from .shard_persistence import read_evaluation_shard_run_result
from .shard_runner import EvaluationShardRunResult


@dataclass(frozen=True, slots=True)
class EvaluationShardMergeResult:
    """Merged local evaluation result from one or more completed shards."""

    shard_results: tuple[EvaluationShardRunResult, ...]
    batch_result: EvaluationBatchResult
    summary_text: str

    def __post_init__(self) -> None:
        if not isinstance(self.shard_results, tuple):
            raise ValueError("shard_results must be a tuple")
        for result in self.shard_results:
            if not isinstance(result, EvaluationShardRunResult):
                raise ValueError(
                    "shard_results entries must be EvaluationShardRunResult"
                )
        if not isinstance(self.batch_result, EvaluationBatchResult):
            raise ValueError("batch_result must be an EvaluationBatchResult")
        _validate_nonempty_string(self.summary_text, "summary_text")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "shard_results": [
                result.to_dict()
                for result in self.shard_results
            ],
            "batch_result": _batch_result_to_dict(self.batch_result),
            "summary_text": self.summary_text,
        }


def merge_evaluation_shard_results(
    results: Sequence[EvaluationShardRunResult],
) -> EvaluationShardMergeResult:
    """Merge completed shard-run results in deterministic input order."""

    shard_results = _shard_results_tuple(results)
    _validate_unique_shard_ids(shard_results)
    match_results = tuple(
        match_result
        for shard_result in shard_results
        for match_result in shard_result.batch_result.results
    )
    batch_result = EvaluationBatchResult(
        results=match_results,
        summary=summarize_match_results(match_results),
    )
    return EvaluationShardMergeResult(
        shard_results=shard_results,
        batch_result=batch_result,
        summary_text=_summary_text(shard_results, batch_result),
    )


def merge_evaluation_shard_result_files(
    paths: Sequence[str | Path],
) -> EvaluationShardMergeResult:
    """Read persisted shard-run result files and merge them in path order."""

    path_tuple = _paths_tuple(paths)
    return merge_evaluation_shard_results(
        tuple(read_evaluation_shard_run_result(path) for path in path_tuple)
    )


def _shard_results_tuple(
    results: Sequence[EvaluationShardRunResult],
) -> tuple[EvaluationShardRunResult, ...]:
    if isinstance(results, (str, bytes)) or not isinstance(results, Sequence):
        raise ValueError("results must be a non-string sequence")
    if not results:
        raise ValueError("results must contain at least one shard result")
    validated = []
    for index, result in enumerate(results):
        if not isinstance(result, EvaluationShardRunResult):
            raise ValueError(
                f"results[{index}] must be an EvaluationShardRunResult"
            )
        validated.append(result)
    return tuple(validated)


def _paths_tuple(paths: Sequence[str | Path]) -> tuple[str | Path, ...]:
    if isinstance(paths, (str, bytes)) or not isinstance(paths, Sequence):
        raise ValueError("paths must be a non-string sequence")
    if not paths:
        raise ValueError("paths must contain at least one shard result path")
    validated = []
    for index, path in enumerate(paths):
        if not isinstance(path, (str, Path)):
            raise ValueError(f"paths[{index}] must be a path")
        validated.append(path)
    return tuple(validated)


def _validate_unique_shard_ids(
    shard_results: tuple[EvaluationShardRunResult, ...],
) -> None:
    seen = set()
    for result in shard_results:
        shard_id = result.shard.shard_id
        if shard_id in seen:
            raise ValueError(f"duplicate shard_id: {shard_id}")
        seen.add(shard_id)


def _summary_text(
    shard_results: tuple[EvaluationShardRunResult, ...],
    batch_result: EvaluationBatchResult,
) -> str:
    summary = batch_result.summary
    return (
        f"shard_merge=COMPLETE shards={len(shard_results)} "
        f"matches={summary.total_matches} completed={summary.completed_count} "
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


def _validate_nonempty_string(value: object, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


__all__ = (
    "EvaluationShardMergeResult",
    "merge_evaluation_shard_result_files",
    "merge_evaluation_shard_results",
)
