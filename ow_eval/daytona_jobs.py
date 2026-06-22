"""Pure Daytona-ready shard job spec contracts.

Distributed Evaluation Cycle 10 converts an existing local shard job index into
deterministic worker job specs. It does not import or call Daytona, spawn
subprocesses, execute commands, upload files, download files, or run matches.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .shard_index_runner import EvaluationShardJobIndex, read_evaluation_shard_job_index


DEFAULT_WORKING_DIR = "/workspace/orbit-wars-serious"
DEFAULT_PYTHON_COMMAND = ".venv/bin/python"
DEFAULT_RUNNER_SCRIPT = "scripts/run_evaluation_shard_job.py"
DEFAULT_SANDBOX_NAME_PREFIX = "ow-eval-shard"


@dataclass(frozen=True, slots=True)
class DaytonaShardJobPlanConfig:
    """Deterministic defaults for Daytona shard worker job specs."""

    working_dir: str = DEFAULT_WORKING_DIR
    python_command: str = DEFAULT_PYTHON_COMMAND
    runner_script: str = DEFAULT_RUNNER_SCRIPT
    sandbox_name_prefix: str | None = DEFAULT_SANDBOX_NAME_PREFIX

    def __post_init__(self) -> None:
        _validate_nonempty_string(self.working_dir, "working_dir")
        _validate_nonempty_string(self.python_command, "python_command")
        _validate_nonempty_string(self.runner_script, "runner_script")
        if self.sandbox_name_prefix is not None:
            _validate_nonempty_string(
                self.sandbox_name_prefix,
                "sandbox_name_prefix",
            )

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "working_dir": self.working_dir,
            "python_command": self.python_command,
            "runner_script": self.runner_script,
            "sandbox_name_prefix": self.sandbox_name_prefix,
        }


@dataclass(frozen=True, slots=True)
class DaytonaShardJobSpec:
    """One deterministic Daytona-ready worker job spec for a shard job."""

    job_id: str
    shard_id: str
    label: str
    local_job_path: str
    local_manifest_path: str
    local_shard_result_path: str
    worker_argv: tuple[str, ...]
    working_dir: str
    runner_script: str
    sandbox_name: str | None
    expected_upload_paths: tuple[str, ...]
    expected_download_paths: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_nonempty_string(self.job_id, "job_id")
        _validate_nonempty_string(self.shard_id, "shard_id")
        _validate_nonempty_string(self.label, "label")
        _validate_nonempty_string(self.local_job_path, "local_job_path")
        _validate_nonempty_string(self.local_manifest_path, "local_manifest_path")
        _validate_nonempty_string(
            self.local_shard_result_path,
            "local_shard_result_path",
        )
        _validate_string_tuple(self.worker_argv, "worker_argv")
        _validate_nonempty_string(self.working_dir, "working_dir")
        _validate_nonempty_string(self.runner_script, "runner_script")
        if self.sandbox_name is not None:
            _validate_nonempty_string(self.sandbox_name, "sandbox_name")
        _validate_string_tuple(self.expected_upload_paths, "expected_upload_paths")
        _validate_string_tuple(self.expected_download_paths, "expected_download_paths")
        if not self.expected_upload_paths:
            raise ValueError("expected_upload_paths must contain at least one path")
        if not self.expected_download_paths:
            raise ValueError("expected_download_paths must contain at least one path")
        if self.runner_script not in self.worker_argv:
            raise ValueError("worker_argv must include runner_script")
        if self.local_job_path not in self.worker_argv:
            raise ValueError("worker_argv must include local_job_path")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "job_id": self.job_id,
            "shard_id": self.shard_id,
            "label": self.label,
            "local_job_path": self.local_job_path,
            "local_manifest_path": self.local_manifest_path,
            "local_shard_result_path": self.local_shard_result_path,
            "worker_argv": list(self.worker_argv),
            "working_dir": self.working_dir,
            "runner_script": self.runner_script,
            "sandbox_name": self.sandbox_name,
            "expected_upload_paths": list(self.expected_upload_paths),
            "expected_download_paths": list(self.expected_download_paths),
        }


@dataclass(frozen=True, slots=True)
class DaytonaShardJobPlan:
    """Deterministic Daytona-ready plan for all jobs in one shard index."""

    index_path: str
    config: DaytonaShardJobPlanConfig
    job_index: EvaluationShardJobIndex
    specs: tuple[DaytonaShardJobSpec, ...]
    summary_text: str

    def __post_init__(self) -> None:
        _validate_nonempty_string(self.index_path, "index_path")
        if not isinstance(self.config, DaytonaShardJobPlanConfig):
            raise ValueError("config must be a DaytonaShardJobPlanConfig")
        if not isinstance(self.job_index, EvaluationShardJobIndex):
            raise ValueError("job_index must be an EvaluationShardJobIndex")
        if not isinstance(self.specs, tuple):
            raise ValueError("specs must be a tuple")
        if not self.specs:
            raise ValueError("specs must contain at least one job spec")
        for index, spec in enumerate(self.specs):
            if not isinstance(spec, DaytonaShardJobSpec):
                raise ValueError(f"specs[{index}] must be a DaytonaShardJobSpec")
        _validate_nonempty_string(self.summary_text, "summary_text")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "index_path": self.index_path,
            "config": self.config.to_dict(),
            "job_index": self.job_index.to_dict(),
            "specs": [spec.to_dict() for spec in self.specs],
            "summary_text": self.summary_text,
        }


def build_daytona_shard_job_plan(
    index_path: str | Path,
    config: DaytonaShardJobPlanConfig | None = None,
) -> DaytonaShardJobPlan:
    """Build deterministic Daytona-ready worker specs from a shard job index."""

    if not isinstance(index_path, (str, Path)):
        raise ValueError("index_path must be a path")
    effective_config = config if config is not None else DaytonaShardJobPlanConfig()
    if not isinstance(effective_config, DaytonaShardJobPlanConfig):
        raise ValueError("config must be a DaytonaShardJobPlanConfig")

    index_path_text = str(index_path)
    job_index = read_evaluation_shard_job_index(index_path)
    specs = tuple(
        _spec_for_job(job_index.jobs[index], index, effective_config)
        for index in range(len(job_index.jobs))
    )
    return DaytonaShardJobPlan(
        index_path=index_path_text,
        config=effective_config,
        job_index=job_index,
        specs=specs,
        summary_text=(
            f"daytona_shard_jobs=READY index_path={index_path_text} "
            f"jobs={len(specs)} working_dir={effective_config.working_dir}"
        ),
    )


def _spec_for_job(
    job,
    index: int,
    config: DaytonaShardJobPlanConfig,
) -> DaytonaShardJobSpec:
    sandbox_name = (
        None
        if config.sandbox_name_prefix is None
        else f"{config.sandbox_name_prefix}-{index:04d}-{job.label}"
    )
    worker_argv = (
        config.python_command,
        config.runner_script,
        job.job_path,
    )
    return DaytonaShardJobSpec(
        job_id=job.job_id,
        shard_id=job.shard_id,
        label=job.label,
        local_job_path=job.job_path,
        local_manifest_path=job.manifest_path,
        local_shard_result_path=job.shard_result_path,
        worker_argv=worker_argv,
        working_dir=config.working_dir,
        runner_script=config.runner_script,
        sandbox_name=sandbox_name,
        expected_upload_paths=(
            job.job_path,
            job.manifest_path,
            *job.extra_upload_paths,
        ),
        expected_download_paths=(
            job.shard_result_path,
            *_default_artifact_download_paths(job),
        ),
    )


def _default_artifact_download_paths(job) -> tuple[str, ...]:
    artifact_dir = Path(job.manifest_path).parent / f"{job.label}.artifacts"
    paths: list[str] = []
    for index in range(len(job.match_labels)):
        base_name = f"{job.label}-match-{index:04d}"
        paths.append(str(artifact_dir / f"{base_name}-replay.json"))
        paths.append(str(artifact_dir / f"{base_name}-result.json"))
    return tuple(paths)


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
    "DaytonaShardJobPlan",
    "DaytonaShardJobPlanConfig",
    "DaytonaShardJobSpec",
    "build_daytona_shard_job_plan",
)
