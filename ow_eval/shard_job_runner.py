"""Run one local evaluation shard job from a packaged job JSON file.

Distributed Evaluation Cycle 8 creates the local worker boundary for one shard
job. It reads a typed shard job, reconstructs the shard from its materialized
manifest, runs the in-process shard runner, and writes the shard result. It
does not execute job command strings, spawn workers, call Daytona, or merge
results.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .experiment_manifest import ExperimentManifest, manifest_to_match_configs
from .shard_jobs import EvaluationShardJob
from .shard_persistence import write_evaluation_shard_run_result
from .shard_runner import EvaluationShardRunResult, run_evaluation_shard
from .sharding import EvaluationShard


@dataclass(frozen=True, slots=True)
class EvaluationShardJobRunResult:
    """Outcome from running one packaged local shard job."""

    job_path: str
    job: EvaluationShardJob | None = None
    shard: EvaluationShard | None = None
    shard_run_result: EvaluationShardRunResult | None = None
    shard_result_path: str | None = None
    exit_code: int = 2
    summary_text: str = ""
    error_text: str | None = None

    def __post_init__(self) -> None:
        _validate_nonempty_string(self.job_path, "job_path")
        if self.job is not None and not isinstance(self.job, EvaluationShardJob):
            raise ValueError("job must be an EvaluationShardJob")
        if self.shard is not None and not isinstance(self.shard, EvaluationShard):
            raise ValueError("shard must be an EvaluationShard")
        if self.shard_run_result is not None and not isinstance(
            self.shard_run_result,
            EvaluationShardRunResult,
        ):
            raise ValueError("shard_run_result must be an EvaluationShardRunResult")
        if self.shard_result_path is not None:
            _validate_nonempty_string(self.shard_result_path, "shard_result_path")
        if isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int):
            raise ValueError("exit_code must be an integer")
        _validate_nonempty_string(self.summary_text, "summary_text")
        if self.error_text is not None:
            _validate_nonempty_string(self.error_text, "error_text")

    @property
    def passed(self) -> bool:
        """Return true when the job completed and persisted a shard result."""

        return self.exit_code == 0

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "job_path": self.job_path,
            "job": self.job.to_dict() if self.job is not None else None,
            "shard": self.shard.to_dict() if self.shard is not None else None,
            "shard_run_result": (
                self.shard_run_result.to_dict()
                if self.shard_run_result is not None
                else None
            ),
            "shard_result_path": self.shard_result_path,
            "exit_code": self.exit_code,
            "passed": self.passed,
            "summary_text": self.summary_text,
            "error_text": self.error_text,
        }


def read_evaluation_shard_job(path: str | Path) -> EvaluationShardJob:
    """Read one deterministic shard job JSON file into a typed object."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("shard job JSON must be an object")
    return _job_from_dict(payload)


def evaluation_shard_from_job(job: EvaluationShardJob) -> EvaluationShard:
    """Reconstruct an ``EvaluationShard`` from ``job`` and its manifest."""

    if not isinstance(job, EvaluationShardJob):
        raise ValueError("job must be an EvaluationShardJob")
    payload = json.loads(Path(job.manifest_path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("job manifest JSON must be an object")
    manifest = ExperimentManifest.from_dict(payload)
    matches = manifest_to_match_configs(manifest)
    _validate_job_match_metadata(job, matches)
    return EvaluationShard(
        shard_id=job.shard_id,
        label=job.label,
        source_manifest_refs=job.source_manifest_refs,
        match_labels=job.match_labels,
        seeds=job.seeds,
        matches=matches,
        planned_manifest_path=job.manifest_path,
        planned_report_path=job.report_path,
        command=job.command,
    )


def run_evaluation_shard_job(job_path: str | Path) -> EvaluationShardJobRunResult:
    """Run one packaged shard job and persist its shard result."""

    job_path_text = str(job_path)
    try:
        job = read_evaluation_shard_job(job_path)
        shard = evaluation_shard_from_job(job)
        shard_run_result = run_evaluation_shard(shard)
        written_path = write_evaluation_shard_run_result(
            shard_run_result,
            job.shard_result_path,
        )
        return EvaluationShardJobRunResult(
            job_path=job_path_text,
            job=job,
            shard=shard,
            shard_run_result=shard_run_result,
            shard_result_path=str(written_path),
            exit_code=0,
            summary_text=(
                f"shard_job=COMPLETE job_id={job.job_id} "
                f"shard_id={job.shard_id} result_path={written_path} "
                "exit_code=0"
            ),
        )
    except Exception as exc:  # noqa: BLE001 - worker CLI boundary is structured.
        return EvaluationShardJobRunResult(
            job_path=job_path_text,
            exit_code=2,
            summary_text=f"shard_job=ERROR job_path={job_path_text} exit_code=2",
            error_text=f"{type(exc).__name__}: {exc}",
        )


def main(argv: Sequence[str] | None = None) -> int:
    """Run one packaged shard job from command-line arguments."""

    parser = argparse.ArgumentParser(
        description="Run one local evaluation shard job JSON file.",
    )
    parser.add_argument("job", help="Path to one shard job JSON file.")
    args = parser.parse_args(argv)

    result = run_evaluation_shard_job(args.job)
    print(result.summary_text)
    if result.shard_run_result is not None:
        print(result.shard_run_result.summary_text)
    if result.error_text is not None:
        print(result.error_text, file=sys.stderr)
    return result.exit_code


def _job_from_dict(data: Mapping[str, object]) -> EvaluationShardJob:
    return EvaluationShardJob(
        job_id=_string_or_raise(data.get("job_id"), "job_id"),
        shard_id=_string_or_raise(data.get("shard_id"), "shard_id"),
        label=_string_or_raise(data.get("label"), "label"),
        manifest_path=_string_or_raise(data.get("manifest_path"), "manifest_path"),
        report_path=_string_or_raise(data.get("report_path"), "report_path"),
        shard_result_path=_string_or_raise(
            data.get("shard_result_path"),
            "shard_result_path",
        ),
        job_path=_string_or_raise(data.get("job_path"), "job_path"),
        command=_string_or_raise(data.get("command"), "command"),
        source_manifest_refs=_string_tuple_from_data(
            data.get("source_manifest_refs"),
            "source_manifest_refs",
        ),
        match_labels=_string_tuple_from_data(
            data.get("match_labels"),
            "match_labels",
        ),
        seeds=_int_tuple_from_data(data.get("seeds"), "seeds"),
    )


def _validate_job_match_metadata(
    job: EvaluationShardJob,
    matches: tuple[object, ...],
) -> None:
    match_labels = tuple(
        match.label if match.label is not None else f"match-{index:04d}"
        for index, match in enumerate(matches)
    )
    if match_labels != job.match_labels:
        raise ValueError("job match_labels do not match manifest")
    seeds = tuple(match.seed for match in matches)
    if seeds != job.seeds:
        raise ValueError("job seeds do not match manifest")


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


def _string_or_raise(value: object, name: str) -> str:
    _validate_nonempty_string(value, name)
    return value


def _validate_nonempty_string(value: object, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


__all__ = (
    "EvaluationShardJobRunResult",
    "evaluation_shard_from_job",
    "main",
    "read_evaluation_shard_job",
    "run_evaluation_shard_job",
)
