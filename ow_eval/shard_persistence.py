"""Deterministic JSON persistence for completed shard-run results.

Distributed Evaluation Cycle 2 makes one ``EvaluationShardRunResult`` durable
for later merge cycles. It does not run matches, dispatch workers, call
Daytona, add CLI orchestration, or merge shard results.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path

from .batch_runner import EvaluationBatchResult, EvaluationBatchSummary
from .contracts import MatchConfig, MatchResult
from .shard_runner import EvaluationShardRunResult
from .sharding import EvaluationShard


def write_evaluation_shard_run_result(
    result: EvaluationShardRunResult,
    path: str | Path,
) -> Path:
    """Write ``result`` as deterministic UTF-8 JSON and return the path."""

    if not isinstance(result, EvaluationShardRunResult):
        raise ValueError("result must be an EvaluationShardRunResult")
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result.to_dict(), sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def read_evaluation_shard_run_result(path: str | Path) -> EvaluationShardRunResult:
    """Read a deterministic JSON shard-run result from ``path``."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("shard run result JSON must be an object")
    return _shard_run_result_from_dict(payload)


def _shard_run_result_from_dict(
    data: Mapping[str, object],
) -> EvaluationShardRunResult:
    shard_data = data.get("shard")
    if not isinstance(shard_data, Mapping):
        raise ValueError("shard must be a mapping")
    batch_result_data = data.get("batch_result")
    if not isinstance(batch_result_data, Mapping):
        raise ValueError("batch_result must be a mapping")
    return EvaluationShardRunResult(
        shard=_shard_from_dict(shard_data),
        batch_result=_batch_result_from_dict(batch_result_data),
        summary_text=_string_or_raise(data.get("summary_text"), "summary_text"),
    )


def _shard_from_dict(data: Mapping[str, object]) -> EvaluationShard:
    matches_data = _sequence_or_raise(data.get("matches"), "shard.matches")
    matches = []
    for index, match_data in enumerate(matches_data):
        if not isinstance(match_data, Mapping):
            raise ValueError(f"shard.matches[{index}] must be a mapping")
        matches.append(MatchConfig.from_dict(match_data))

    match_count = data.get("match_count")
    if match_count is not None:
        expected_count = _nonnegative_int_or_raise(
            match_count,
            "shard.match_count",
        )
        if expected_count != len(matches):
            raise ValueError("shard.match_count does not match matches")

    return EvaluationShard(
        shard_id=_string_or_raise(data.get("shard_id"), "shard.shard_id"),
        label=_string_or_raise(data.get("label"), "shard.label"),
        source_manifest_refs=_string_tuple_from_data(
            data.get("source_manifest_refs"),
            "shard.source_manifest_refs",
        ),
        match_labels=_string_tuple_from_data(
            data.get("match_labels"),
            "shard.match_labels",
        ),
        seeds=_int_tuple_from_data(data.get("seeds"), "shard.seeds"),
        matches=tuple(matches),
        planned_manifest_path=_string_or_raise(
            data.get("planned_manifest_path"),
            "shard.planned_manifest_path",
        ),
        planned_report_path=_string_or_raise(
            data.get("planned_report_path"),
            "shard.planned_report_path",
        ),
        command=_string_or_raise(data.get("command"), "shard.command"),
    )


def _batch_result_from_dict(data: Mapping[str, object]) -> EvaluationBatchResult:
    results_data = _sequence_or_raise(data.get("results"), "batch_result.results")
    results = []
    for index, result_data in enumerate(results_data):
        if not isinstance(result_data, Mapping):
            raise ValueError(f"batch_result.results[{index}] must be a mapping")
        results.append(MatchResult.from_dict(result_data))

    summary_data = data.get("summary")
    if not isinstance(summary_data, Mapping):
        raise ValueError("batch_result.summary must be a mapping")

    return EvaluationBatchResult(
        results=tuple(results),
        summary=_batch_summary_from_dict(summary_data),
    )


def _batch_summary_from_dict(data: Mapping[str, object]) -> EvaluationBatchSummary:
    return EvaluationBatchSummary(
        total_matches=_nonnegative_int_or_default(
            data.get("total_matches"),
            "batch_result.summary.total_matches",
            0,
        ),
        completed_count=_nonnegative_int_or_default(
            data.get("completed_count"),
            "batch_result.summary.completed_count",
            0,
        ),
        error_count=_nonnegative_int_or_default(
            data.get("error_count"),
            "batch_result.summary.error_count",
            0,
        ),
        status_counts=_status_counts_from_data(data.get("status_counts")),
        mean_final_rank=_optional_float(
            data.get("mean_final_rank"),
            "batch_result.summary.mean_final_rank",
        ),
        mean_final_score=_optional_float(
            data.get("mean_final_score"),
            "batch_result.summary.mean_final_score",
        ),
        mean_turns_survived=_optional_float(
            data.get("mean_turns_survived"),
            "batch_result.summary.mean_turns_survived",
        ),
    )


def _sequence_or_raise(value: object, name: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(f"{name} must be a sequence")
    return value


def _string_tuple_from_data(value: object, name: str) -> tuple[str, ...]:
    items = _sequence_or_raise(value, name)
    result = []
    for index, item in enumerate(items):
        if not isinstance(item, str) or not item:
            raise ValueError(f"{name}[{index}] must be a non-empty string")
        result.append(item)
    return tuple(result)


def _int_tuple_from_data(value: object, name: str) -> tuple[int, ...]:
    items = _sequence_or_raise(value, name)
    result = []
    for index, item in enumerate(items):
        if isinstance(item, bool) or not isinstance(item, int):
            raise ValueError(f"{name}[{index}] must be an integer")
        result.append(item)
    return tuple(result)


def _status_counts_from_data(value: object) -> tuple[tuple[str, int], ...]:
    if value is None:
        return ()
    items = _sequence_or_raise(value, "batch_result.summary.status_counts")
    result = []
    for index, item in enumerate(items):
        pair = _sequence_or_raise(
            item,
            f"batch_result.summary.status_counts[{index}]",
        )
        if len(pair) != 2:
            raise ValueError(
                f"batch_result.summary.status_counts[{index}] must have two items"
            )
        status = pair[0]
        count = pair[1]
        if not isinstance(status, str) or not status:
            raise ValueError(
                f"batch_result.summary.status_counts[{index}][0] "
                "must be a non-empty string"
            )
        result.append(
            (
                status,
                _nonnegative_int_or_raise(
                    count,
                    f"batch_result.summary.status_counts[{index}][1]",
                ),
            )
        )
    return tuple(result)


def _string_or_raise(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _nonnegative_int_or_raise(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _nonnegative_int_or_default(
    value: object,
    name: str,
    default: int,
) -> int:
    if value is None:
        return default
    return _nonnegative_int_or_raise(value, name)


def _optional_float(value: object, name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError(f"{name} must be a number")
    return float(value)


__all__ = (
    "read_evaluation_shard_run_result",
    "write_evaluation_shard_run_result",
)
