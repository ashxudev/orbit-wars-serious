"""Deterministic scoreboard records for local evaluation batches.

Evaluation Harness Cycle 9 converts existing ``EvaluationBatchResult`` objects
into JSONL-friendly scoreboard records. It does not run matches, inspect
replays, or enforce promotion gates.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .batch_runner import EvaluationBatchResult
from .contracts import EvaluationStatus, MatchResult
from .triage import triage_evaluation_batch


@dataclass(frozen=True, slots=True)
class ScoreboardRecord:
    """Persistent deterministic summary for one evaluated batch."""

    agent_name: str
    agent_version: str | None
    commit: str | None
    scenario_set: str
    match_count: int = 0
    completed_count: int = 0
    win_count: int = 0
    loss_count: int = 0
    error_count: int = 0
    win_rate: float | None = None
    mean_rank: float | None = None
    mean_score: float | None = None
    error_rate: float | None = None
    triage_category_counts: tuple[tuple[str, int], ...] = ()
    notes: tuple[str, ...] = ()
    metadata: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        _validate_nonempty_string(self.agent_name, "agent_name")
        _validate_nonempty_string(self.scenario_set, "scenario_set")
        if self.agent_version is not None:
            _validate_nonempty_string(self.agent_version, "agent_version")
        if self.commit is not None:
            _validate_nonempty_string(self.commit, "commit")
        _validate_nonnegative_int(self.match_count, "match_count")
        _validate_nonnegative_int(self.completed_count, "completed_count")
        _validate_nonnegative_int(self.win_count, "win_count")
        _validate_nonnegative_int(self.loss_count, "loss_count")
        _validate_nonnegative_int(self.error_count, "error_count")
        _validate_optional_rate(self.win_rate, "win_rate")
        _validate_optional_rate(self.error_rate, "error_rate")
        _validate_optional_number(self.mean_rank, "mean_rank")
        _validate_optional_number(self.mean_score, "mean_score")
        _validate_category_counts(self.triage_category_counts)
        _validate_string_tuple(self.notes, "notes")
        _validate_metadata(self.metadata)

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic plain dictionary representation."""

        return {
            "agent_name": self.agent_name,
            "agent_version": self.agent_version,
            "commit": self.commit,
            "scenario_set": self.scenario_set,
            "match_count": self.match_count,
            "completed_count": self.completed_count,
            "win_count": self.win_count,
            "loss_count": self.loss_count,
            "error_count": self.error_count,
            "win_rate": self.win_rate,
            "mean_rank": self.mean_rank,
            "mean_score": self.mean_score,
            "error_rate": self.error_rate,
            "triage_category_counts": [
                {"category": category, "count": count}
                for category, count in self.triage_category_counts
            ],
            "notes": list(self.notes),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> ScoreboardRecord:
        """Create a ``ScoreboardRecord`` from a plain dictionary."""

        return cls(
            agent_name=_string_or_raise(data.get("agent_name"), "agent_name"),
            agent_version=_optional_string(data.get("agent_version"), "agent_version"),
            commit=_optional_string(data.get("commit"), "commit"),
            scenario_set=_string_or_raise(data.get("scenario_set"), "scenario_set"),
            match_count=_int_or_default(data.get("match_count"), "match_count", 0),
            completed_count=_int_or_default(
                data.get("completed_count"),
                "completed_count",
                0,
            ),
            win_count=_int_or_default(data.get("win_count"), "win_count", 0),
            loss_count=_int_or_default(data.get("loss_count"), "loss_count", 0),
            error_count=_int_or_default(data.get("error_count"), "error_count", 0),
            win_rate=_optional_float(data.get("win_rate"), "win_rate"),
            mean_rank=_optional_float(data.get("mean_rank"), "mean_rank"),
            mean_score=_optional_float(data.get("mean_score"), "mean_score"),
            error_rate=_optional_float(data.get("error_rate"), "error_rate"),
            triage_category_counts=_category_counts_from_data(
                data.get("triage_category_counts", ()),
            ),
            notes=_string_tuple_from_data(data.get("notes", ()), "notes"),
            metadata=_metadata_from_mapping(data.get("metadata")),
        )


def build_scoreboard_record(
    batch: EvaluationBatchResult,
    *,
    agent_name: str,
    scenario_set: str,
    agent_version: str | None = None,
    commit: str | None = None,
    notes: Sequence[str] = (),
    metadata: Mapping[str, str] | tuple[tuple[str, str], ...] = (),
) -> ScoreboardRecord:
    """Build a deterministic scoreboard record from an evaluated batch."""

    results = batch.results
    match_count = len(results)
    completed_count = sum(
        1
        for result in results
        if result.status is EvaluationStatus.COMPLETED
    )
    win_count = sum(1 for result in results if _is_win(result))
    loss_count = sum(1 for result in results if _is_loss(result))
    error_count = sum(
        1
        for result in results
        if result.status is not EvaluationStatus.COMPLETED
    )
    triage_report = triage_evaluation_batch(batch)
    return ScoreboardRecord(
        agent_name=agent_name,
        agent_version=agent_version,
        commit=commit,
        scenario_set=scenario_set,
        match_count=match_count,
        completed_count=completed_count,
        win_count=win_count,
        loss_count=loss_count,
        error_count=error_count,
        win_rate=_ratio(win_count, match_count),
        mean_rank=_mean(result.metrics.final_rank for result in results),
        mean_score=_mean(result.metrics.final_score for result in results),
        error_rate=_ratio(error_count, match_count),
        triage_category_counts=triage_report.category_counts,
        notes=_string_tuple_from_data(notes, "notes"),
        metadata=_metadata_from_mapping(metadata),
    )


def write_scoreboard_record(
    record: ScoreboardRecord,
    path: str | Path,
) -> Path:
    """Write one scoreboard record as deterministic JSONL, replacing ``path``."""

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        _json_line(record),
        encoding="utf-8",
    )
    return output_path


def append_scoreboard_record(
    record: ScoreboardRecord,
    path: str | Path,
) -> Path:
    """Append one scoreboard record as deterministic JSONL."""

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as file:
        file.write(_json_line(record))
    return output_path


def read_scoreboard_records(path: str | Path) -> tuple[ScoreboardRecord, ...]:
    """Read scoreboard records from JSONL in file order."""

    input_path = Path(path)
    records = []
    with input_path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            if not isinstance(payload, Mapping):
                raise ValueError(f"line {line_number} must contain a JSON object")
            records.append(ScoreboardRecord.from_dict(payload))
    return tuple(records)


def _json_line(record: ScoreboardRecord) -> str:
    return json.dumps(record.to_dict(), sort_keys=True, indent=None) + "\n"


def _is_win(result: MatchResult) -> bool:
    final_rank = result.metrics.final_rank
    return (
        result.status is EvaluationStatus.COMPLETED
        and _is_number(final_rank)
        and float(final_rank) == 1.0
    )


def _is_loss(result: MatchResult) -> bool:
    final_rank = result.metrics.final_rank
    return (
        result.status is EvaluationStatus.COMPLETED
        and _is_number(final_rank)
        and float(final_rank) > 1.0
    )


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def _mean(values: Sequence[int | float | None] | Any) -> float | None:
    numeric_values = tuple(
        float(value)
        for value in values
        if _is_number(value)
    )
    if not numeric_values:
        return None
    return sum(numeric_values) / len(numeric_values)


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate_nonempty_string(value: object, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


def _string_or_raise(value: object, name: str) -> str:
    _validate_nonempty_string(value, name)
    return value


def _optional_string(value: object, name: str) -> str | None:
    if value is None:
        return None
    _validate_nonempty_string(value, name)
    return value


def _validate_nonnegative_int(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")


def _int_or_default(value: object, name: str, default: int) -> int:
    if value is None:
        return default
    _validate_nonnegative_int(value, name)
    return value


def _validate_optional_number(value: object, name: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number or None")


def _optional_float(value: object, name: str) -> float | None:
    if value is None:
        return None
    _validate_optional_number(value, name)
    return float(value)


def _validate_optional_rate(value: object, name: str) -> None:
    _validate_optional_number(value, name)
    if value is not None and not (0.0 <= float(value) <= 1.0):
        raise ValueError(f"{name} must be between 0.0 and 1.0")


def _validate_category_counts(value: tuple[tuple[str, int], ...]) -> None:
    if not isinstance(value, tuple):
        raise ValueError("triage_category_counts must be a tuple")
    for item in value:
        if not isinstance(item, tuple) or len(item) != 2:
            raise ValueError("triage_category_counts entries must be tuples")
        _validate_nonempty_string(item[0], "triage category")
        _validate_nonnegative_int(item[1], "triage category count")


def _category_counts_from_data(value: object) -> tuple[tuple[str, int], ...]:
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError("triage_category_counts must be a sequence")
    counts = []
    for index, item in enumerate(value):
        if isinstance(item, Mapping):
            category = _string_or_raise(
                item.get("category"),
                f"triage_category_counts[{index}].category",
            )
            count = item.get("count")
        elif isinstance(item, Sequence) and not isinstance(item, (str, bytes)):
            if len(item) != 2:
                raise ValueError("triage_category_counts entries must have length 2")
            category = _string_or_raise(item[0], "triage category")
            count = item[1]
        else:
            raise ValueError("triage_category_counts entries must be mappings")
        _validate_nonnegative_int(count, "triage category count")
        counts.append((category, count))
    return tuple(counts)


def _validate_string_tuple(value: tuple[str, ...], name: str) -> None:
    if not isinstance(value, tuple):
        raise ValueError(f"{name} must be a tuple")
    for item in value:
        _validate_nonempty_string(item, name)


def _string_tuple_from_data(value: object, name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{name} must be a sequence")
    result = tuple(value)
    _validate_string_tuple(result, name)
    return result


def _validate_metadata(metadata: tuple[tuple[str, str], ...]) -> None:
    if not isinstance(metadata, tuple):
        raise ValueError("metadata must be a tuple")
    for item in metadata:
        if not isinstance(item, tuple) or len(item) != 2:
            raise ValueError("metadata entries must be key/value tuples")
        _validate_nonempty_string(item[0], "metadata key")
        if not isinstance(item[1], str):
            raise ValueError("metadata values must be strings")


def _metadata_from_mapping(
    value: Mapping[str, str] | tuple[tuple[str, str], ...] | object,
) -> tuple[tuple[str, str], ...]:
    if value is None:
        return ()
    if isinstance(value, tuple):
        _validate_metadata(value)
        return value
    if not isinstance(value, Mapping):
        raise ValueError("metadata must be a mapping")
    return tuple(sorted((str(key), str(item)) for key, item in value.items()))


__all__ = (
    "ScoreboardRecord",
    "append_scoreboard_record",
    "build_scoreboard_record",
    "read_scoreboard_records",
    "write_scoreboard_record",
)
