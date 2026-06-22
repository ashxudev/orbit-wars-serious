"""Read and preflight deterministic Daytona shard job plans.

Distributed Evaluation Cycle 12 validates the local JSON plan produced by the
Daytona plan writer before any future sandbox executor can use it. It does not
call Daytona, spawn subprocesses, execute worker argv, upload/download files,
write result files, or run matches.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .daytona_jobs import (
    DaytonaShardJobPlan,
    DaytonaShardJobPlanConfig,
    DaytonaShardJobSpec,
)
from .shard_index_runner import EvaluationShardJobIndex
from .shard_jobs import EvaluationShardJob


@dataclass(frozen=True, slots=True)
class DaytonaShardJobPlanValidationResult:
    """Validation result for a typed Daytona shard job plan."""

    plan_path: str | None = None
    plan: DaytonaShardJobPlan | None = None
    missing_upload_paths: tuple[str, ...] = ()
    duplicate_sandbox_names: tuple[str, ...] = ()
    warning_text: str | None = None
    error_text: str | None = None
    exit_code: int = 2
    summary_text: str = ""

    def __post_init__(self) -> None:
        if self.plan_path is not None:
            _validate_nonempty_string(self.plan_path, "plan_path")
        if self.plan is not None and not isinstance(self.plan, DaytonaShardJobPlan):
            raise ValueError("plan must be a DaytonaShardJobPlan")
        _validate_string_tuple(self.missing_upload_paths, "missing_upload_paths")
        _validate_string_tuple(self.duplicate_sandbox_names, "duplicate_sandbox_names")
        if self.warning_text is not None:
            _validate_nonempty_string(self.warning_text, "warning_text")
        if self.error_text is not None:
            _validate_nonempty_string(self.error_text, "error_text")
        if isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int):
            raise ValueError("exit_code must be an integer")
        _validate_nonempty_string(self.summary_text, "summary_text")

    @property
    def passed(self) -> bool:
        """Return true when the plan passed preflight validation."""

        return self.exit_code == 0

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "plan_path": self.plan_path,
            "plan": self.plan.to_dict() if self.plan is not None else None,
            "missing_upload_paths": list(self.missing_upload_paths),
            "duplicate_sandbox_names": list(self.duplicate_sandbox_names),
            "warning_text": self.warning_text,
            "error_text": self.error_text,
            "exit_code": self.exit_code,
            "passed": self.passed,
            "summary_text": self.summary_text,
        }


def read_daytona_shard_job_plan(path: str | Path) -> DaytonaShardJobPlan:
    """Read deterministic Daytona shard job plan JSON into typed objects."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("Daytona shard job plan JSON must be an object")
    plan = _plan_from_dict(payload)
    _validate_plan_alignment(plan)
    return plan


def validate_daytona_shard_job_plan(
    plan_or_path: DaytonaShardJobPlan | str | Path,
    *,
    require_upload_paths_exist: bool = True,
    require_unique_sandbox_names: bool = True,
) -> DaytonaShardJobPlanValidationResult:
    """Validate a Daytona shard job plan or plan JSON path."""

    plan_path = str(plan_or_path) if isinstance(plan_or_path, (str, Path)) else None
    try:
        if isinstance(plan_or_path, DaytonaShardJobPlan):
            plan = plan_or_path
        elif isinstance(plan_or_path, (str, Path)):
            plan = read_daytona_shard_job_plan(plan_or_path)
        else:
            raise ValueError("plan_or_path must be a DaytonaShardJobPlan or path")
    except Exception as exc:  # noqa: BLE001 - CLI boundary returns structured errors.
        return DaytonaShardJobPlanValidationResult(
            plan_path=plan_path,
            exit_code=2,
            summary_text=(
                "daytona_shard_job_plan_validation=ERROR "
                f"plan_path={plan_path} specs=0 exit_code=2"
            ),
            error_text=f"{type(exc).__name__}: {exc}",
        )

    missing_upload_paths = (
        _missing_upload_paths(plan)
        if require_upload_paths_exist
        else ()
    )
    duplicate_sandbox_names = _duplicate_sandbox_names(plan)
    blocking_duplicates = (
        duplicate_sandbox_names
        if require_unique_sandbox_names
        else ()
    )
    error_parts = []
    if missing_upload_paths:
        error_parts.append(
            "missing upload paths: " + ", ".join(missing_upload_paths)
        )
    if blocking_duplicates:
        error_parts.append(
            "duplicate sandbox names: " + ", ".join(blocking_duplicates)
        )

    passed = not error_parts
    return DaytonaShardJobPlanValidationResult(
        plan_path=plan_path,
        plan=plan,
        missing_upload_paths=missing_upload_paths,
        duplicate_sandbox_names=duplicate_sandbox_names,
        exit_code=0 if passed else 2,
        summary_text=_summary_text(plan_path, plan, passed, missing_upload_paths, duplicate_sandbox_names),
        error_text="; ".join(error_parts) if error_parts else None,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Validate one Daytona shard job plan JSON from command-line arguments."""

    parser = argparse.ArgumentParser(
        description="Validate a deterministic Daytona shard job plan JSON file.",
    )
    parser.add_argument("plan", help="Daytona shard job plan JSON path.")
    parser.add_argument(
        "--no-upload-path-existence-check",
        action="store_true",
        help="Do not require expected upload paths to exist locally.",
    )
    parser.add_argument(
        "--allow-duplicate-sandbox-names",
        action="store_true",
        help="Allow duplicate non-null sandbox names.",
    )
    args = parser.parse_args(argv)

    result = validate_daytona_shard_job_plan(
        args.plan,
        require_upload_paths_exist=not args.no_upload_path_existence_check,
        require_unique_sandbox_names=not args.allow_duplicate_sandbox_names,
    )
    print(result.summary_text)
    if result.error_text is not None:
        print(result.error_text, file=sys.stderr)
    return result.exit_code


def _plan_from_dict(data: Mapping[str, object]) -> DaytonaShardJobPlan:
    config_data = data.get("config")
    if not isinstance(config_data, Mapping):
        raise ValueError("config must be a mapping")
    job_index_data = data.get("job_index")
    if not isinstance(job_index_data, Mapping):
        raise ValueError("job_index must be a mapping")
    specs_data = _sequence_or_raise(data.get("specs"), "specs")
    if not specs_data:
        raise ValueError("specs must contain at least one spec")
    specs = []
    for index, item in enumerate(specs_data):
        if not isinstance(item, Mapping):
            raise ValueError(f"specs[{index}] must be a mapping")
        specs.append(_spec_from_dict(item, index))
    return DaytonaShardJobPlan(
        index_path=_string_or_raise(data.get("index_path"), "index_path"),
        config=_config_from_dict(config_data),
        job_index=_job_index_from_dict(job_index_data),
        specs=tuple(specs),
        summary_text=_string_or_raise(data.get("summary_text"), "summary_text"),
    )


def _config_from_dict(data: Mapping[str, object]) -> DaytonaShardJobPlanConfig:
    return DaytonaShardJobPlanConfig(
        working_dir=_string_or_raise(data.get("working_dir"), "config.working_dir"),
        python_command=_string_or_raise(
            data.get("python_command"),
            "config.python_command",
        ),
        runner_script=_string_or_raise(data.get("runner_script"), "config.runner_script"),
        sandbox_name_prefix=_optional_string(
            data.get("sandbox_name_prefix"),
            "config.sandbox_name_prefix",
        ),
        source_mode=_string_or_raise(data.get("source_mode"), "config.source_mode"),
        github_repo=_string_or_raise(data.get("github_repo"), "config.github_repo"),
        git_ref=_string_or_raise(data.get("git_ref"), "config.git_ref"),
        github_token_env_var=_optional_string(
            data.get("github_token_env_var"),
            "config.github_token_env_var",
        ),
    )


def _job_index_from_dict(data: Mapping[str, object]) -> EvaluationShardJobIndex:
    jobs_data = _sequence_or_raise(data.get("jobs"), "job_index.jobs")
    if not jobs_data:
        raise ValueError("job_index.jobs must contain at least one job")
    jobs = []
    for index, item in enumerate(jobs_data):
        if not isinstance(item, Mapping):
            raise ValueError(f"job_index.jobs[{index}] must be a mapping")
        jobs.append(_job_from_dict(item, index))
    return EvaluationShardJobIndex(
        index_path=_string_or_raise(data.get("index_path"), "job_index.index_path"),
        jobs=tuple(jobs),
        job_paths=_string_tuple_from_data(data.get("job_paths"), "job_index.job_paths"),
        manifest_paths=_string_tuple_from_data(
            data.get("manifest_paths"),
            "job_index.manifest_paths",
        ),
        commands=_string_tuple_from_data(data.get("commands"), "job_index.commands"),
        summary_text=_string_or_raise(
            data.get("summary_text"),
            "job_index.summary_text",
        ),
    )


def _job_from_dict(data: Mapping[str, object], index: int) -> EvaluationShardJob:
    return EvaluationShardJob(
        job_id=_string_or_raise(data.get("job_id"), f"job_index.jobs[{index}].job_id"),
        shard_id=_string_or_raise(
            data.get("shard_id"),
            f"job_index.jobs[{index}].shard_id",
        ),
        label=_string_or_raise(data.get("label"), f"job_index.jobs[{index}].label"),
        manifest_path=_string_or_raise(
            data.get("manifest_path"),
            f"job_index.jobs[{index}].manifest_path",
        ),
        report_path=_string_or_raise(
            data.get("report_path"),
            f"job_index.jobs[{index}].report_path",
        ),
        shard_result_path=_string_or_raise(
            data.get("shard_result_path"),
            f"job_index.jobs[{index}].shard_result_path",
        ),
        job_path=_string_or_raise(
            data.get("job_path"),
            f"job_index.jobs[{index}].job_path",
        ),
        command=_string_or_raise(
            data.get("command"),
            f"job_index.jobs[{index}].command",
        ),
        source_manifest_refs=_string_tuple_from_data(
            data.get("source_manifest_refs"),
            f"job_index.jobs[{index}].source_manifest_refs",
        ),
        match_labels=_string_tuple_from_data(
            data.get("match_labels"),
            f"job_index.jobs[{index}].match_labels",
        ),
        seeds=_int_tuple_from_data(data.get("seeds"), f"job_index.jobs[{index}].seeds"),
    )


def _spec_from_dict(data: Mapping[str, object], index: int) -> DaytonaShardJobSpec:
    return DaytonaShardJobSpec(
        job_id=_string_or_raise(data.get("job_id"), f"specs[{index}].job_id"),
        shard_id=_string_or_raise(data.get("shard_id"), f"specs[{index}].shard_id"),
        label=_string_or_raise(data.get("label"), f"specs[{index}].label"),
        local_job_path=_string_or_raise(
            data.get("local_job_path"),
            f"specs[{index}].local_job_path",
        ),
        local_manifest_path=_string_or_raise(
            data.get("local_manifest_path"),
            f"specs[{index}].local_manifest_path",
        ),
        local_shard_result_path=_string_or_raise(
            data.get("local_shard_result_path"),
            f"specs[{index}].local_shard_result_path",
        ),
        worker_argv=_string_tuple_from_data(
            data.get("worker_argv"),
            f"specs[{index}].worker_argv",
        ),
        working_dir=_string_or_raise(
            data.get("working_dir"),
            f"specs[{index}].working_dir",
        ),
        runner_script=_string_or_raise(
            data.get("runner_script"),
            f"specs[{index}].runner_script",
        ),
        sandbox_name=_optional_string(data.get("sandbox_name"), f"specs[{index}].sandbox_name"),
        expected_upload_paths=_string_tuple_from_data(
            data.get("expected_upload_paths"),
            f"specs[{index}].expected_upload_paths",
        ),
        expected_download_paths=_string_tuple_from_data(
            data.get("expected_download_paths"),
            f"specs[{index}].expected_download_paths",
        ),
        source_mode=_string_or_raise(data.get("source_mode"), f"specs[{index}].source_mode"),
        github_repo=_string_or_raise(data.get("github_repo"), f"specs[{index}].github_repo"),
        git_ref=_string_or_raise(data.get("git_ref"), f"specs[{index}].git_ref"),
        github_token_env_var=_optional_string(
            data.get("github_token_env_var"),
            f"specs[{index}].github_token_env_var",
        ),
    )


def _validate_plan_alignment(plan: DaytonaShardJobPlan) -> None:
    if len(plan.specs) != len(plan.job_index.jobs):
        raise ValueError("specs must match job_index jobs length")
    for index, (spec, job) in enumerate(zip(plan.specs, plan.job_index.jobs, strict=True)):
        if spec.job_id != job.job_id:
            raise ValueError(f"specs[{index}].job_id must match job_index job_id")
        if spec.shard_id != job.shard_id:
            raise ValueError(f"specs[{index}].shard_id must match job_index shard_id")
        if spec.local_job_path != job.job_path:
            raise ValueError(f"specs[{index}].local_job_path must match job_path")
        if spec.local_manifest_path != job.manifest_path:
            raise ValueError(
                f"specs[{index}].local_manifest_path must match manifest_path"
            )
        if spec.local_shard_result_path != job.shard_result_path:
            raise ValueError(
                f"specs[{index}].local_shard_result_path must match shard_result_path"
            )


def _missing_upload_paths(plan: DaytonaShardJobPlan) -> tuple[str, ...]:
    missing = []
    seen = set()
    for spec in plan.specs:
        for path in spec.expected_upload_paths:
            if path in seen:
                continue
            seen.add(path)
            if not Path(path).exists():
                missing.append(path)
    return tuple(missing)


def _duplicate_sandbox_names(plan: DaytonaShardJobPlan) -> tuple[str, ...]:
    seen = set()
    duplicates = []
    for spec in plan.specs:
        if spec.sandbox_name is None:
            continue
        if spec.sandbox_name in seen and spec.sandbox_name not in duplicates:
            duplicates.append(spec.sandbox_name)
        seen.add(spec.sandbox_name)
    return tuple(duplicates)


def _summary_text(
    plan_path: str | None,
    plan: DaytonaShardJobPlan,
    passed: bool,
    missing_upload_paths: tuple[str, ...],
    duplicate_sandbox_names: tuple[str, ...],
) -> str:
    status = "PASS" if passed else "ERROR"
    return (
        f"daytona_shard_job_plan_validation={status} "
        f"plan_path={plan_path} specs={len(plan.specs)} "
        f"missing_upload_paths={len(missing_upload_paths)} "
        f"duplicate_sandbox_names={len(duplicate_sandbox_names)} "
        f"exit_code={0 if passed else 2}"
    )


def _optional_string(value: object, name: str) -> str | None:
    if value is None:
        return None
    return _string_or_raise(value, name)


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
    "DaytonaShardJobPlanValidationResult",
    "main",
    "read_daytona_shard_job_plan",
    "validate_daytona_shard_job_plan",
)
