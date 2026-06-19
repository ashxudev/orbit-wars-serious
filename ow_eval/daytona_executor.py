"""Pure Daytona shard executor orchestration boundary.

Distributed Evaluation Cycle 13 proves the control flow for executing a
validated Daytona shard job plan through an injected executor protocol. It does
not import or call Daytona, create sandboxes, spawn subprocesses, execute worker
argv, upload/download files, write reports, or run matches.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .daytona_jobs import DaytonaShardJobPlan, DaytonaShardJobSpec
from .daytona_preflight import (
    DaytonaShardJobPlanValidationResult,
    validate_daytona_shard_job_plan,
)
from .shard_merge import (
    EvaluationShardMergeResult,
    merge_evaluation_shard_result_files,
)


@dataclass(frozen=True, slots=True)
class DaytonaShardExecutionRequest:
    """Structured request handed to an injected Daytona shard job executor."""

    job_id: str
    shard_id: str
    label: str
    sandbox_name: str | None
    worker_argv: tuple[str, ...]
    working_dir: str
    expected_upload_paths: tuple[str, ...]
    expected_download_paths: tuple[str, ...]
    local_shard_result_path: str
    spec: DaytonaShardJobSpec

    def __post_init__(self) -> None:
        _validate_nonempty_string(self.job_id, "job_id")
        _validate_nonempty_string(self.shard_id, "shard_id")
        _validate_nonempty_string(self.label, "label")
        if self.sandbox_name is not None:
            _validate_nonempty_string(self.sandbox_name, "sandbox_name")
        _validate_string_tuple(self.worker_argv, "worker_argv")
        _validate_nonempty_string(self.working_dir, "working_dir")
        _validate_string_tuple(self.expected_upload_paths, "expected_upload_paths")
        _validate_string_tuple(self.expected_download_paths, "expected_download_paths")
        _validate_nonempty_string(
            self.local_shard_result_path,
            "local_shard_result_path",
        )
        if not isinstance(self.spec, DaytonaShardJobSpec):
            raise ValueError("spec must be a DaytonaShardJobSpec")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "job_id": self.job_id,
            "shard_id": self.shard_id,
            "label": self.label,
            "sandbox_name": self.sandbox_name,
            "worker_argv": list(self.worker_argv),
            "working_dir": self.working_dir,
            "expected_upload_paths": list(self.expected_upload_paths),
            "expected_download_paths": list(self.expected_download_paths),
            "local_shard_result_path": self.local_shard_result_path,
            "spec": self.spec.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class DaytonaShardExecutionResult:
    """Result returned by an injected Daytona shard job executor."""

    job_id: str
    shard_id: str
    label: str
    sandbox_name: str | None = None
    shard_result_path: str | None = None
    exit_code: int = 0
    summary_text: str = ""
    error_text: str | None = None

    def __post_init__(self) -> None:
        _validate_nonempty_string(self.job_id, "job_id")
        _validate_nonempty_string(self.shard_id, "shard_id")
        _validate_nonempty_string(self.label, "label")
        if self.sandbox_name is not None:
            _validate_nonempty_string(self.sandbox_name, "sandbox_name")
        if self.shard_result_path is not None:
            _validate_nonempty_string(self.shard_result_path, "shard_result_path")
        if isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int):
            raise ValueError("exit_code must be an integer")
        _validate_nonempty_string(self.summary_text, "summary_text")
        if self.error_text is not None:
            _validate_nonempty_string(self.error_text, "error_text")

    @property
    def passed(self) -> bool:
        """Return true when the executor completed the job successfully."""

        return self.exit_code == 0

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "job_id": self.job_id,
            "shard_id": self.shard_id,
            "label": self.label,
            "sandbox_name": self.sandbox_name,
            "shard_result_path": self.shard_result_path,
            "exit_code": self.exit_code,
            "passed": self.passed,
            "summary_text": self.summary_text,
            "error_text": self.error_text,
        }


class DaytonaShardJobExecutor(Protocol):
    """Protocol for injected future Daytona/local fake shard job executors."""

    def execute(
        self,
        request: DaytonaShardExecutionRequest,
    ) -> DaytonaShardExecutionResult:
        """Execute one structured shard job request."""
        ...


@dataclass(frozen=True, slots=True)
class DaytonaShardExecutionBatchResult:
    """Result from orchestrating one Daytona shard job plan through an executor."""

    plan_path: str | None = None
    plan: DaytonaShardJobPlan | None = None
    preflight_result: DaytonaShardJobPlanValidationResult | None = None
    execution_requests: tuple[DaytonaShardExecutionRequest, ...] = ()
    execution_results: tuple[DaytonaShardExecutionResult, ...] = ()
    shard_result_paths: tuple[str, ...] = ()
    merged_result: EvaluationShardMergeResult | None = None
    exit_code: int = 2
    summary_text: str = ""
    error_text: str | None = None

    def __post_init__(self) -> None:
        if self.plan_path is not None:
            _validate_nonempty_string(self.plan_path, "plan_path")
        if self.plan is not None and not isinstance(self.plan, DaytonaShardJobPlan):
            raise ValueError("plan must be a DaytonaShardJobPlan")
        if self.preflight_result is not None and not isinstance(
            self.preflight_result,
            DaytonaShardJobPlanValidationResult,
        ):
            raise ValueError(
                "preflight_result must be a DaytonaShardJobPlanValidationResult"
            )
        _validate_request_tuple(self.execution_requests, "execution_requests")
        _validate_result_tuple(self.execution_results, "execution_results")
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
        """Return true when all executions, and optional merge, succeeded."""

        return self.exit_code == 0

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "plan_path": self.plan_path,
            "plan": self.plan.to_dict() if self.plan is not None else None,
            "preflight_result": (
                self.preflight_result.to_dict()
                if self.preflight_result is not None
                else None
            ),
            "execution_requests": [
                request.to_dict()
                for request in self.execution_requests
            ],
            "execution_results": [
                result.to_dict()
                for result in self.execution_results
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


def run_daytona_shard_job_plan(
    plan_or_path: DaytonaShardJobPlan | str | Path,
    executor: DaytonaShardJobExecutor,
    *,
    require_upload_paths_exist: bool = True,
    require_unique_sandbox_names: bool = True,
    merge_results: bool = True,
) -> DaytonaShardExecutionBatchResult:
    """Run a validated Daytona shard job plan through an injected executor."""

    plan_path = str(plan_or_path) if isinstance(plan_or_path, (str, Path)) else None
    try:
        preflight_result = validate_daytona_shard_job_plan(
            plan_or_path,
            require_upload_paths_exist=require_upload_paths_exist,
            require_unique_sandbox_names=require_unique_sandbox_names,
        )
    except Exception as exc:  # noqa: BLE001 - orchestration boundary is structured.
        return _error_result(
            plan_path=plan_path,
            plan=None,
            preflight_result=None,
            requests=(),
            results=(),
            paths=(),
            error_text=f"{type(exc).__name__}: {exc}",
            stage="preflight",
        )

    plan = preflight_result.plan
    if preflight_result.exit_code != 0 or plan is None:
        return _error_result(
            plan_path=plan_path,
            plan=plan,
            preflight_result=preflight_result,
            requests=(),
            results=(),
            paths=(),
            error_text=f"preflight failed: {preflight_result.error_text}",
            stage="preflight",
        )
    if not callable(getattr(executor, "execute", None)):
        return _error_result(
            plan_path=plan_path,
            plan=plan,
            preflight_result=preflight_result,
            requests=(),
            results=(),
            paths=(),
            error_text="ValueError: executor must provide execute(request)",
            stage="executor",
        )

    requests = tuple(_request_for_spec(spec) for spec in plan.specs)
    execution_results: list[DaytonaShardExecutionResult] = []
    shard_result_paths: list[str] = []
    for request in requests:
        try:
            execution_result = executor.execute(request)
            if not isinstance(execution_result, DaytonaShardExecutionResult):
                raise ValueError(
                    "executor.execute must return DaytonaShardExecutionResult"
                )
        except Exception as exc:  # noqa: BLE001 - orchestration boundary is structured.
            return _error_result(
                plan_path=plan_path,
                plan=plan,
                preflight_result=preflight_result,
                requests=requests,
                results=tuple(execution_results),
                paths=tuple(shard_result_paths),
                error_text=(
                    f"executor failed for {request.job_id}: "
                    f"{type(exc).__name__}: {exc}"
                ),
                stage="execution",
            )

        execution_results.append(execution_result)
        if execution_result.exit_code != 0:
            return _error_result(
                plan_path=plan_path,
                plan=plan,
                preflight_result=preflight_result,
                requests=requests,
                results=tuple(execution_results),
                paths=tuple(shard_result_paths),
                error_text=(
                    f"execution failed: {execution_result.job_id} "
                    f"exit_code={execution_result.exit_code}"
                    + (
                        f": {execution_result.error_text}"
                        if execution_result.error_text is not None
                        else ""
                    )
                ),
                stage="execution",
            )
        if execution_result.shard_result_path is None:
            return _error_result(
                plan_path=plan_path,
                plan=plan,
                preflight_result=preflight_result,
                requests=requests,
                results=tuple(execution_results),
                paths=tuple(shard_result_paths),
                error_text=(
                    f"execution result missing shard_result_path: "
                    f"{execution_result.job_id}"
                ),
                stage="execution",
            )
        shard_result_paths.append(execution_result.shard_result_path)

    if not merge_results:
        return DaytonaShardExecutionBatchResult(
            plan_path=plan_path,
            plan=plan,
            preflight_result=preflight_result,
            execution_requests=requests,
            execution_results=tuple(execution_results),
            shard_result_paths=tuple(shard_result_paths),
            merged_result=None,
            exit_code=0,
            summary_text=_summary_text(
                "COMPLETE",
                plan_path,
                len(execution_results),
                merged=False,
                exit_code=0,
            ),
        )

    try:
        merged_result = merge_evaluation_shard_result_files(tuple(shard_result_paths))
    except Exception as exc:  # noqa: BLE001 - orchestration boundary is structured.
        return _error_result(
            plan_path=plan_path,
            plan=plan,
            preflight_result=preflight_result,
            requests=requests,
            results=tuple(execution_results),
            paths=tuple(shard_result_paths),
            error_text=f"merge failed: {type(exc).__name__}: {exc}",
            stage="merge",
        )

    return DaytonaShardExecutionBatchResult(
        plan_path=plan_path,
        plan=plan,
        preflight_result=preflight_result,
        execution_requests=requests,
        execution_results=tuple(execution_results),
        shard_result_paths=tuple(shard_result_paths),
        merged_result=merged_result,
        exit_code=0,
        summary_text=_summary_text(
            "COMPLETE",
            plan_path,
            len(execution_results),
            merged=True,
            exit_code=0,
        ),
    )


def _request_for_spec(spec: DaytonaShardJobSpec) -> DaytonaShardExecutionRequest:
    return DaytonaShardExecutionRequest(
        job_id=spec.job_id,
        shard_id=spec.shard_id,
        label=spec.label,
        sandbox_name=spec.sandbox_name,
        worker_argv=spec.worker_argv,
        working_dir=spec.working_dir,
        expected_upload_paths=spec.expected_upload_paths,
        expected_download_paths=spec.expected_download_paths,
        local_shard_result_path=spec.local_shard_result_path,
        spec=spec,
    )


def _error_result(
    *,
    plan_path: str | None,
    plan: DaytonaShardJobPlan | None,
    preflight_result: DaytonaShardJobPlanValidationResult | None,
    requests: tuple[DaytonaShardExecutionRequest, ...],
    results: tuple[DaytonaShardExecutionResult, ...],
    paths: tuple[str, ...],
    error_text: str,
    stage: str,
) -> DaytonaShardExecutionBatchResult:
    return DaytonaShardExecutionBatchResult(
        plan_path=plan_path,
        plan=plan,
        preflight_result=preflight_result,
        execution_requests=requests,
        execution_results=results,
        shard_result_paths=paths,
        merged_result=None,
        exit_code=2,
        summary_text=_summary_text(
            "ERROR",
            plan_path,
            len(results),
            merged=False,
            exit_code=2,
            stage=stage,
        ),
        error_text=error_text,
    )


def _summary_text(
    status: str,
    plan_path: str | None,
    jobs: int,
    *,
    merged: bool,
    exit_code: int,
    stage: str | None = None,
) -> str:
    stage_part = f" stage={stage}" if stage is not None else ""
    return (
        f"daytona_shard_execution={status} plan_path={plan_path} "
        f"jobs={jobs} merged={merged} exit_code={exit_code}{stage_part}"
    )


def _validate_request_tuple(value: object, name: str) -> None:
    if not isinstance(value, tuple):
        raise ValueError(f"{name} must be a tuple")
    for index, item in enumerate(value):
        if not isinstance(item, DaytonaShardExecutionRequest):
            raise ValueError(
                f"{name}[{index}] must be a DaytonaShardExecutionRequest"
            )


def _validate_result_tuple(value: object, name: str) -> None:
    if not isinstance(value, tuple):
        raise ValueError(f"{name} must be a tuple")
    for index, item in enumerate(value):
        if not isinstance(item, DaytonaShardExecutionResult):
            raise ValueError(
                f"{name}[{index}] must be a DaytonaShardExecutionResult"
            )


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
    "DaytonaShardExecutionBatchResult",
    "DaytonaShardExecutionRequest",
    "DaytonaShardExecutionResult",
    "DaytonaShardJobExecutor",
    "run_daytona_shard_job_plan",
)
