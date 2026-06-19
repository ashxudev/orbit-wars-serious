"""Deterministic Daytona client execution reports.

Distributed Evaluation Cycle 17 wraps the injected client executor with a
report contract that preserves the shard execution batch result, client event
trace, and operation plans. It does not import or call Daytona, create real
sandboxes, spawn subprocesses, execute worker argv locally, upload/download real
files, or run matches.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .daytona_client_executor import (
    DaytonaClientExecutionEvent,
    DaytonaClientExecutor,
    DaytonaSandboxClient,
)
from .daytona_executor import (
    DaytonaShardExecutionBatchResult,
    run_daytona_shard_job_plan,
)
from .daytona_jobs import DaytonaShardJobPlan
from .daytona_operations import DaytonaSandboxOperationPlan


@dataclass(frozen=True, slots=True)
class DaytonaClientExecutionReport:
    """Report for one Daytona client execution batch."""

    plan_path: str | None
    batch_result: DaytonaShardExecutionBatchResult
    client_event_trace: tuple[DaytonaClientExecutionEvent, ...]
    operation_plans: tuple[DaytonaSandboxOperationPlan, ...]
    exit_code: int
    summary_text: str
    error_text: str | None = None

    def __post_init__(self) -> None:
        if self.plan_path is not None:
            _validate_nonempty_string(self.plan_path, "plan_path")
        if not isinstance(self.batch_result, DaytonaShardExecutionBatchResult):
            raise ValueError("batch_result must be a DaytonaShardExecutionBatchResult")
        _validate_event_tuple(self.client_event_trace, "client_event_trace")
        _validate_operation_plan_tuple(self.operation_plans, "operation_plans")
        if isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int):
            raise ValueError("exit_code must be an integer")
        _validate_nonempty_string(self.summary_text, "summary_text")
        if self.error_text is not None:
            _validate_nonempty_string(self.error_text, "error_text")

    @property
    def passed(self) -> bool:
        """Return true when the wrapped batch result passed."""

        return self.exit_code == 0

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "plan_path": self.plan_path,
            "batch_result": self.batch_result.to_dict(),
            "client_event_trace": [
                event.to_dict()
                for event in self.client_event_trace
            ],
            "operation_plans": [
                plan.to_dict()
                for plan in self.operation_plans
            ],
            "exit_code": self.exit_code,
            "passed": self.passed,
            "summary_text": self.summary_text,
            "error_text": self.error_text,
        }


def run_daytona_shard_job_plan_with_client_report(
    plan_or_path: DaytonaShardJobPlan | str | Path,
    client: DaytonaSandboxClient,
    *,
    require_upload_paths_exist: bool = True,
    require_unique_sandbox_names: bool = True,
    merge_results: bool = True,
) -> DaytonaClientExecutionReport:
    """Run one Daytona plan through a client executor and return a report."""

    plan_path = str(plan_or_path) if isinstance(plan_or_path, (str, Path)) else None
    executor = DaytonaClientExecutor(client)
    batch_result = run_daytona_shard_job_plan(
        plan_or_path,
        executor,
        require_upload_paths_exist=require_upload_paths_exist,
        require_unique_sandbox_names=require_unique_sandbox_names,
        merge_results=merge_results,
    )
    return DaytonaClientExecutionReport(
        plan_path=plan_path,
        batch_result=batch_result,
        client_event_trace=executor.event_trace,
        operation_plans=tuple(executor.operation_plans),
        exit_code=batch_result.exit_code,
        summary_text=_summary_text(
            plan_path,
            batch_result,
            event_count=len(executor.event_trace),
            operation_plan_count=len(executor.operation_plans),
        ),
        error_text=batch_result.error_text,
    )


def _summary_text(
    plan_path: str | None,
    batch_result: DaytonaShardExecutionBatchResult,
    *,
    event_count: int,
    operation_plan_count: int,
) -> str:
    status = "COMPLETE" if batch_result.exit_code == 0 else "ERROR"
    return (
        f"daytona_client_execution_report={status} plan_path={plan_path} "
        f"jobs={len(batch_result.execution_results)} events={event_count} "
        f"operation_plans={operation_plan_count} exit_code={batch_result.exit_code}"
    )


def _validate_event_tuple(value: object, name: str) -> None:
    if not isinstance(value, tuple):
        raise ValueError(f"{name} must be a tuple")
    for index, item in enumerate(value):
        if not isinstance(item, DaytonaClientExecutionEvent):
            raise ValueError(f"{name}[{index}] must be a DaytonaClientExecutionEvent")


def _validate_operation_plan_tuple(value: object, name: str) -> None:
    if not isinstance(value, tuple):
        raise ValueError(f"{name} must be a tuple")
    for index, item in enumerate(value):
        if not isinstance(item, DaytonaSandboxOperationPlan):
            raise ValueError(f"{name}[{index}] must be a DaytonaSandboxOperationPlan")


def _validate_nonempty_string(value: object, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


__all__ = (
    "DaytonaClientExecutionReport",
    "run_daytona_shard_job_plan_with_client_report",
)
