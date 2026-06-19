"""Run a packaged local evaluation shard job index sequentially.

Distributed Evaluation Cycle 9 proves a shard job package can run through the
same index/job boundary intended for later local parallel or Daytona workers.
It reads the package index, runs each typed shard job in index order, and merges
persisted shard result files only when every job succeeds. It does not execute
job command strings, spawn workers, call Daytona, or prepare packages.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .shard_job_runner import EvaluationShardJobRunResult, run_evaluation_shard_job
from .shard_jobs import EvaluationShardJob
from .shard_merge import EvaluationShardMergeResult, merge_evaluation_shard_result_files


@dataclass(frozen=True, slots=True)
class EvaluationShardJobIndex:
    """Typed view of a deterministic shard job package index."""

    index_path: str
    jobs: tuple[EvaluationShardJob, ...]
    job_paths: tuple[str, ...]
    manifest_paths: tuple[str, ...]
    commands: tuple[str, ...]
    summary_text: str

    def __post_init__(self) -> None:
        _validate_nonempty_string(self.index_path, "index_path")
        if not isinstance(self.jobs, tuple):
            raise ValueError("jobs must be a tuple")
        if not self.jobs:
            raise ValueError("jobs must contain at least one job")
        for index, job in enumerate(self.jobs):
            if not isinstance(job, EvaluationShardJob):
                raise ValueError(f"jobs[{index}] must be an EvaluationShardJob")
        _validate_string_tuple(self.job_paths, "job_paths")
        _validate_string_tuple(self.manifest_paths, "manifest_paths")
        _validate_string_tuple(self.commands, "commands")
        _validate_nonempty_string(self.summary_text, "summary_text")
        _validate_aligned_metadata(self)

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "index_path": self.index_path,
            "jobs": [job.to_dict() for job in self.jobs],
            "job_paths": list(self.job_paths),
            "manifest_paths": list(self.manifest_paths),
            "commands": list(self.commands),
            "summary_text": self.summary_text,
        }


@dataclass(frozen=True, slots=True)
class EvaluationShardIndexRunResult:
    """Outcome from running one packaged shard job index."""

    index_path: str
    index: EvaluationShardJobIndex | None = None
    job_run_results: tuple[EvaluationShardJobRunResult, ...] = ()
    shard_result_paths: tuple[str, ...] = ()
    merged_result: EvaluationShardMergeResult | None = None
    exit_code: int = 2
    summary_text: str = ""
    error_text: str | None = None

    def __post_init__(self) -> None:
        _validate_nonempty_string(self.index_path, "index_path")
        if self.index is not None and not isinstance(
            self.index,
            EvaluationShardJobIndex,
        ):
            raise ValueError("index must be an EvaluationShardJobIndex")
        if not isinstance(self.job_run_results, tuple):
            raise ValueError("job_run_results must be a tuple")
        for index, result in enumerate(self.job_run_results):
            if not isinstance(result, EvaluationShardJobRunResult):
                raise ValueError(
                    f"job_run_results[{index}] must be an EvaluationShardJobRunResult"
                )
        _validate_string_tuple(self.shard_result_paths, "shard_result_paths")
        if self.merged_result is not None and not isinstance(
            self.merged_result,
            EvaluationShardMergeResult,
        ):
            raise ValueError("merged_result must be an EvaluationShardMergeResult")
        if isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int):
            raise ValueError("exit_code must be an integer")
        _validate_nonempty_string(self.summary_text, "summary_text")
        if self.error_text is not None:
            _validate_nonempty_string(self.error_text, "error_text")

    @property
    def passed(self) -> bool:
        """Return true when every job passed and shard results were merged."""

        return self.exit_code == 0

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "index_path": self.index_path,
            "index": self.index.to_dict() if self.index is not None else None,
            "job_run_results": [
                result.to_dict()
                for result in self.job_run_results
            ],
            "shard_result_paths": list(self.shard_result_paths),
            "merged_result": (
                self.merged_result.to_dict()
                if self.merged_result is not None
                else None
            ),
            "exit_code": self.exit_code,
            "passed": self.passed,
            "summary_text": self.summary_text,
            "error_text": self.error_text,
        }


def read_evaluation_shard_job_index(path: str | Path) -> EvaluationShardJobIndex:
    """Read one deterministic shard job package index into typed jobs."""

    path_text = str(path)
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("shard job index JSON must be an object")
    return _index_from_dict(payload, path_text)


def run_evaluation_shard_job_index(
    index_path: str | Path,
) -> EvaluationShardIndexRunResult:
    """Run every shard job from ``index_path`` and merge successful results."""

    index_path_text = str(index_path)
    parsed_index: EvaluationShardJobIndex | None = None
    job_run_results: list[EvaluationShardJobRunResult] = []
    shard_result_paths: list[str] = []
    try:
        parsed_index = read_evaluation_shard_job_index(index_path)
        for job in parsed_index.jobs:
            job_result = run_evaluation_shard_job(job.job_path)
            job_run_results.append(job_result)
            if job_result.exit_code != 0:
                return _error_result(
                    index_path_text,
                    parsed_index,
                    tuple(job_run_results),
                    tuple(shard_result_paths),
                    _job_failure_text(job, job_result),
                )
            if job_result.shard_result_path is None:
                raise ValueError(f"job {job.job_id} did not produce shard_result_path")
            shard_result_paths.append(job_result.shard_result_path)

        merged_result = merge_evaluation_shard_result_files(tuple(shard_result_paths))
        return EvaluationShardIndexRunResult(
            index_path=index_path_text,
            index=parsed_index,
            job_run_results=tuple(job_run_results),
            shard_result_paths=tuple(shard_result_paths),
            merged_result=merged_result,
            exit_code=0,
            summary_text=(
                f"shard_index=COMPLETE index_path={index_path_text} "
                f"jobs={len(job_run_results)} "
                f"merged_matches={merged_result.batch_result.summary.total_matches} "
                "exit_code=0"
            ),
        )
    except Exception as exc:  # noqa: BLE001 - CLI boundary returns structured errors.
        return _error_result(
            index_path_text,
            parsed_index,
            tuple(job_run_results),
            tuple(shard_result_paths),
            f"{type(exc).__name__}: {exc}",
        )


def main(argv: Sequence[str] | None = None) -> int:
    """Run one packaged shard job index from command-line arguments."""

    parser = argparse.ArgumentParser(
        description="Run one local evaluation shard job package index.",
    )
    parser.add_argument("index", help="Path to one shard job package index JSON file.")
    args = parser.parse_args(argv)

    result = run_evaluation_shard_job_index(args.index)
    print(result.summary_text)
    for job_result in result.job_run_results:
        print(job_result.summary_text)
    if result.merged_result is not None:
        print(result.merged_result.summary_text)
    if result.error_text is not None:
        print(result.error_text, file=sys.stderr)
    return result.exit_code


def _index_from_dict(
    data: Mapping[str, object],
    source_path: str,
) -> EvaluationShardJobIndex:
    jobs = _jobs_from_data(data.get("jobs"))
    job_paths = _optional_string_tuple(data.get("job_paths"), "job_paths")
    manifest_paths = _optional_string_tuple(data.get("manifest_paths"), "manifest_paths")
    commands = _optional_string_tuple(data.get("commands"), "commands")
    index_path = _optional_nonempty_string(data.get("index_path"), "index_path")
    summary_text = _optional_nonempty_string(data.get("summary_text"), "summary_text")

    return EvaluationShardJobIndex(
        index_path=index_path if index_path is not None else source_path,
        jobs=jobs,
        job_paths=job_paths if job_paths is not None else tuple(job.job_path for job in jobs),
        manifest_paths=(
            manifest_paths
            if manifest_paths is not None
            else tuple(job.manifest_path for job in jobs)
        ),
        commands=commands if commands is not None else tuple(job.command for job in jobs),
        summary_text=(
            summary_text
            if summary_text is not None
            else f"shard_jobs=INDEX jobs={len(jobs)} index_path={source_path}"
        ),
    )


def _jobs_from_data(value: object) -> tuple[EvaluationShardJob, ...]:
    items = _sequence_or_raise(value, "jobs")
    if not items:
        raise ValueError("jobs must contain at least one job")
    jobs = []
    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            raise ValueError(f"jobs[{index}] must be a mapping")
        jobs.append(_job_from_dict(item, index))
    return tuple(jobs)


def _job_from_dict(data: Mapping[str, object], index: int) -> EvaluationShardJob:
    return EvaluationShardJob(
        job_id=_string_or_raise(data.get("job_id"), f"jobs[{index}].job_id"),
        shard_id=_string_or_raise(data.get("shard_id"), f"jobs[{index}].shard_id"),
        label=_string_or_raise(data.get("label"), f"jobs[{index}].label"),
        manifest_path=_string_or_raise(
            data.get("manifest_path"),
            f"jobs[{index}].manifest_path",
        ),
        report_path=_string_or_raise(
            data.get("report_path"),
            f"jobs[{index}].report_path",
        ),
        shard_result_path=_string_or_raise(
            data.get("shard_result_path"),
            f"jobs[{index}].shard_result_path",
        ),
        job_path=_string_or_raise(data.get("job_path"), f"jobs[{index}].job_path"),
        command=_string_or_raise(data.get("command"), f"jobs[{index}].command"),
        source_manifest_refs=_string_tuple_from_data(
            data.get("source_manifest_refs"),
            f"jobs[{index}].source_manifest_refs",
        ),
        match_labels=_string_tuple_from_data(
            data.get("match_labels"),
            f"jobs[{index}].match_labels",
        ),
        seeds=_int_tuple_from_data(data.get("seeds"), f"jobs[{index}].seeds"),
    )


def _validate_aligned_metadata(index: EvaluationShardJobIndex) -> None:
    expected_len = len(index.jobs)
    _validate_length(index.job_paths, expected_len, "job_paths")
    _validate_length(index.manifest_paths, expected_len, "manifest_paths")
    _validate_length(index.commands, expected_len, "commands")
    for item_index, job in enumerate(index.jobs):
        if index.job_paths[item_index] != job.job_path:
            raise ValueError(
                f"job_paths[{item_index}] must match jobs[{item_index}].job_path"
            )
        if index.manifest_paths[item_index] != job.manifest_path:
            raise ValueError(
                f"manifest_paths[{item_index}] must match "
                f"jobs[{item_index}].manifest_path"
            )
        if index.commands[item_index] != job.command:
            raise ValueError(
                f"commands[{item_index}] must match jobs[{item_index}].command"
            )


def _validate_length(value: tuple[object, ...], expected_len: int, name: str) -> None:
    if len(value) != expected_len:
        raise ValueError(f"{name} must match jobs length")


def _job_failure_text(
    job: EvaluationShardJob,
    job_result: EvaluationShardJobRunResult,
) -> str:
    text = f"shard job failed: {job.job_id} exit_code={job_result.exit_code}"
    if job_result.error_text is not None:
        return f"{text} error={job_result.error_text}"
    return text


def _error_result(
    index_path: str,
    parsed_index: EvaluationShardJobIndex | None,
    job_run_results: tuple[EvaluationShardJobRunResult, ...],
    shard_result_paths: tuple[str, ...],
    error_text: str,
) -> EvaluationShardIndexRunResult:
    return EvaluationShardIndexRunResult(
        index_path=index_path,
        index=parsed_index,
        job_run_results=job_run_results,
        shard_result_paths=shard_result_paths,
        exit_code=2,
        summary_text=(
            f"shard_index=ERROR index_path={index_path} "
            f"jobs_attempted={len(job_run_results)} exit_code=2"
        ),
        error_text=error_text,
    )


def _optional_string_tuple(value: object, name: str) -> tuple[str, ...] | None:
    if value is None:
        return None
    return _string_tuple_from_data(value, name)


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


def _sequence_or_raise(value: object, name: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(f"{name} must be a sequence")
    return value


def _optional_nonempty_string(value: object, name: str) -> str | None:
    if value is None:
        return None
    return _string_or_raise(value, name)


def _string_or_raise(value: object, name: str) -> str:
    _validate_nonempty_string(value, name)
    return value


def _validate_string_tuple(value: object, name: str) -> None:
    if not isinstance(value, tuple):
        raise ValueError(f"{name} must be a tuple")
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item:
            raise ValueError(f"{name}[{index}] must be a non-empty string")


def _validate_nonempty_string(value: object, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


__all__ = (
    "EvaluationShardIndexRunResult",
    "EvaluationShardJobIndex",
    "main",
    "read_evaluation_shard_job_index",
    "run_evaluation_shard_job_index",
)
