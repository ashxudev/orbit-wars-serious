"""Deterministic job packages for planned evaluation shards.

Distributed Evaluation Cycle 6 turns an ``EvaluationShardPlan`` into portable
per-shard job specs plus one deterministic index. It does not run matches,
execute commands, spawn workers, call Daytona, or add parallel orchestration.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .shard_manifests import write_evaluation_shard_manifests
from .sharding import EvaluationShard, EvaluationShardPlan


@dataclass(frozen=True, slots=True)
class EvaluationShardJob:
    """Portable local job spec for one planned evaluation shard."""

    job_id: str
    shard_id: str
    label: str
    manifest_path: str
    report_path: str
    shard_result_path: str
    job_path: str
    command: str
    source_manifest_refs: tuple[str, ...]
    match_labels: tuple[str, ...]
    seeds: tuple[int, ...]

    def __post_init__(self) -> None:
        _validate_nonempty_string(self.job_id, "job_id")
        _validate_nonempty_string(self.shard_id, "shard_id")
        _validate_nonempty_string(self.label, "label")
        _validate_nonempty_string(self.manifest_path, "manifest_path")
        _validate_nonempty_string(self.report_path, "report_path")
        _validate_nonempty_string(self.shard_result_path, "shard_result_path")
        _validate_nonempty_string(self.job_path, "job_path")
        _validate_nonempty_string(self.command, "command")
        _validate_string_tuple(self.source_manifest_refs, "source_manifest_refs")
        _validate_string_tuple(self.match_labels, "match_labels")
        _validate_int_tuple(self.seeds, "seeds")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "job_id": self.job_id,
            "shard_id": self.shard_id,
            "label": self.label,
            "manifest_path": self.manifest_path,
            "report_path": self.report_path,
            "shard_result_path": self.shard_result_path,
            "job_path": self.job_path,
            "command": self.command,
            "source_manifest_refs": list(self.source_manifest_refs),
            "match_labels": list(self.match_labels),
            "seeds": list(self.seeds),
        }


@dataclass(frozen=True, slots=True)
class EvaluationShardJobPackageResult:
    """Result from writing one deterministic shard job package."""

    shard_plan: EvaluationShardPlan
    jobs: tuple[EvaluationShardJob, ...]
    manifest_paths: tuple[str, ...]
    job_paths: tuple[str, ...]
    index_path: str
    commands: tuple[str, ...]
    summary_text: str

    def __post_init__(self) -> None:
        if not isinstance(self.shard_plan, EvaluationShardPlan):
            raise ValueError("shard_plan must be an EvaluationShardPlan")
        if not isinstance(self.jobs, tuple):
            raise ValueError("jobs must be a tuple")
        for job in self.jobs:
            if not isinstance(job, EvaluationShardJob):
                raise ValueError("jobs entries must be EvaluationShardJob")
        _validate_string_tuple(self.manifest_paths, "manifest_paths")
        _validate_string_tuple(self.job_paths, "job_paths")
        _validate_nonempty_string(self.index_path, "index_path")
        _validate_string_tuple(self.commands, "commands")
        _validate_nonempty_string(self.summary_text, "summary_text")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "shard_plan": self.shard_plan.to_dict(),
            "jobs": [
                job.to_dict()
                for job in self.jobs
            ],
            "manifest_paths": list(self.manifest_paths),
            "job_paths": list(self.job_paths),
            "index_path": self.index_path,
            "commands": list(self.commands),
            "summary_text": self.summary_text,
        }


def build_evaluation_shard_jobs(
    plan: EvaluationShardPlan,
) -> tuple[EvaluationShardJob, ...]:
    """Build deterministic job specs for every shard in ``plan``."""

    if not isinstance(plan, EvaluationShardPlan):
        raise ValueError("plan must be an EvaluationShardPlan")
    return tuple(
        _job_for_shard(index, shard)
        for index, shard in enumerate(plan.shards)
    )


def write_evaluation_shard_job_package(
    plan: EvaluationShardPlan,
    *,
    index_path: str | Path | None = None,
    materialize_manifests: bool = True,
) -> EvaluationShardJobPackageResult:
    """Write per-shard job specs and one deterministic package index."""

    if not isinstance(plan, EvaluationShardPlan):
        raise ValueError("plan must be an EvaluationShardPlan")
    if not isinstance(materialize_manifests, bool):
        raise ValueError("materialize_manifests must be a boolean")

    jobs = build_evaluation_shard_jobs(plan)
    if materialize_manifests:
        manifest_paths = write_evaluation_shard_manifests(plan).manifest_paths
    else:
        manifest_paths = tuple(job.manifest_path for job in jobs)

    for job in jobs:
        _write_json(job.to_dict(), job.job_path)

    resolved_index_path = (
        Path(index_path)
        if index_path is not None
        else Path(plan.config.output_root) / "shard-jobs.index.json"
    )
    result = EvaluationShardJobPackageResult(
        shard_plan=plan,
        jobs=jobs,
        manifest_paths=manifest_paths,
        job_paths=tuple(job.job_path for job in jobs),
        index_path=str(resolved_index_path),
        commands=tuple(job.command for job in jobs),
        summary_text=(
            f"shard_jobs=WRITTEN shards={len(plan.shards)} "
            f"jobs={len(jobs)} index_path={resolved_index_path}"
        ),
    )
    _write_json(result.to_dict(), resolved_index_path)
    return result


def _job_for_shard(index: int, shard: EvaluationShard) -> EvaluationShardJob:
    output_dir = Path(shard.planned_manifest_path).parent
    return EvaluationShardJob(
        job_id=f"job-{index:04d}",
        shard_id=shard.shard_id,
        label=shard.label,
        manifest_path=shard.planned_manifest_path,
        report_path=shard.planned_report_path,
        shard_result_path=str(output_dir / f"{shard.label}.shard-result.json"),
        job_path=str(output_dir / f"{shard.label}.job.json"),
        command=shard.command,
        source_manifest_refs=shard.source_manifest_refs,
        match_labels=shard.match_labels,
        seeds=shard.seeds,
    )


def _write_json(payload: object, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_nonempty_string(value: object, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


def _validate_string_tuple(value: object, name: str) -> None:
    if not isinstance(value, tuple):
        raise ValueError(f"{name} must be a tuple")
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item:
            raise ValueError(f"{name}[{index}] must be a non-empty string")


def _validate_int_tuple(value: object, name: str) -> None:
    if not isinstance(value, tuple):
        raise ValueError(f"{name} must be a tuple")
    for index, item in enumerate(value):
        if isinstance(item, bool) or not isinstance(item, int):
            raise ValueError(f"{name}[{index}] must be an integer")


__all__ = (
    "EvaluationShardJob",
    "EvaluationShardJobPackageResult",
    "build_evaluation_shard_jobs",
    "write_evaluation_shard_job_package",
)
