"""Pure Daytona sandbox operation-plan contracts.

Distributed Evaluation Cycle 15 converts structured Daytona shard execution
requests into explicit upload/command/download operation plans for a future real
executor. It does not import or call Daytona, create sandboxes, execute
commands, upload files, download files, spawn subprocesses, or run matches.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .daytona_executor import DaytonaShardExecutionRequest


@dataclass(frozen=True, slots=True)
class DaytonaUploadOperation:
    """One deterministic file upload operation for a sandbox."""

    local_path: str
    sandbox_path: str

    def __post_init__(self) -> None:
        _validate_nonempty_string(self.local_path, "local_path")
        _validate_nonempty_string(self.sandbox_path, "sandbox_path")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "local_path": self.local_path,
            "sandbox_path": self.sandbox_path,
        }


@dataclass(frozen=True, slots=True)
class DaytonaCommandOperation:
    """One deterministic command operation for a sandbox."""

    worker_argv: tuple[str, ...]
    working_dir: str

    def __post_init__(self) -> None:
        _validate_string_tuple(self.worker_argv, "worker_argv")
        if not self.worker_argv:
            raise ValueError("worker_argv must contain at least one argument")
        _validate_nonempty_string(self.working_dir, "working_dir")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "worker_argv": list(self.worker_argv),
            "working_dir": self.working_dir,
        }


@dataclass(frozen=True, slots=True)
class DaytonaDownloadOperation:
    """One deterministic file download operation for a sandbox."""

    sandbox_path: str
    local_path: str

    def __post_init__(self) -> None:
        _validate_nonempty_string(self.sandbox_path, "sandbox_path")
        _validate_nonempty_string(self.local_path, "local_path")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "sandbox_path": self.sandbox_path,
            "local_path": self.local_path,
        }


@dataclass(frozen=True, slots=True)
class DaytonaSandboxOperationPlan:
    """Operation plan for one Daytona shard execution request."""

    sandbox_name: str | None
    job_id: str
    shard_id: str
    label: str
    working_dir: str
    upload_operations: tuple[DaytonaUploadOperation, ...]
    command_operation: DaytonaCommandOperation
    download_operations: tuple[DaytonaDownloadOperation, ...]
    local_shard_result_path: str
    request: DaytonaShardExecutionRequest
    summary_text: str

    def __post_init__(self) -> None:
        if self.sandbox_name is not None:
            _validate_nonempty_string(self.sandbox_name, "sandbox_name")
        _validate_nonempty_string(self.job_id, "job_id")
        _validate_nonempty_string(self.shard_id, "shard_id")
        _validate_nonempty_string(self.label, "label")
        _validate_nonempty_string(self.working_dir, "working_dir")
        _validate_upload_tuple(self.upload_operations, "upload_operations")
        if not isinstance(self.command_operation, DaytonaCommandOperation):
            raise ValueError("command_operation must be a DaytonaCommandOperation")
        _validate_download_tuple(self.download_operations, "download_operations")
        _validate_nonempty_string(
            self.local_shard_result_path,
            "local_shard_result_path",
        )
        if not isinstance(self.request, DaytonaShardExecutionRequest):
            raise ValueError("request must be a DaytonaShardExecutionRequest")
        _validate_nonempty_string(self.summary_text, "summary_text")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "sandbox_name": self.sandbox_name,
            "job_id": self.job_id,
            "shard_id": self.shard_id,
            "label": self.label,
            "working_dir": self.working_dir,
            "upload_operations": [
                operation.to_dict()
                for operation in self.upload_operations
            ],
            "command_operation": self.command_operation.to_dict(),
            "download_operations": [
                operation.to_dict()
                for operation in self.download_operations
            ],
            "local_shard_result_path": self.local_shard_result_path,
            "request": self.request.to_dict(),
            "summary_text": self.summary_text,
        }


@dataclass(frozen=True, slots=True)
class DaytonaBatchOperationPlan:
    """Operation plans for an ordered batch of Daytona shard requests."""

    operation_plans: tuple[DaytonaSandboxOperationPlan, ...]
    summary_text: str

    def __post_init__(self) -> None:
        if not isinstance(self.operation_plans, tuple):
            raise ValueError("operation_plans must be a tuple")
        if not self.operation_plans:
            raise ValueError("operation_plans must contain at least one plan")
        for index, plan in enumerate(self.operation_plans):
            if not isinstance(plan, DaytonaSandboxOperationPlan):
                raise ValueError(
                    f"operation_plans[{index}] must be a DaytonaSandboxOperationPlan"
                )
        _validate_nonempty_string(self.summary_text, "summary_text")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "operation_plans": [
                plan.to_dict()
                for plan in self.operation_plans
            ],
            "summary_text": self.summary_text,
        }


def build_daytona_sandbox_operation_plan(
    request: DaytonaShardExecutionRequest,
) -> DaytonaSandboxOperationPlan:
    """Build a deterministic operation plan for one execution request."""

    if not isinstance(request, DaytonaShardExecutionRequest):
        raise ValueError("request must be a DaytonaShardExecutionRequest")
    upload_operations = tuple(
        DaytonaUploadOperation(local_path=path, sandbox_path=path)
        for path in request.expected_upload_paths
    )
    download_operations = tuple(
        DaytonaDownloadOperation(sandbox_path=path, local_path=path)
        for path in request.expected_download_paths
    )
    return DaytonaSandboxOperationPlan(
        sandbox_name=request.sandbox_name,
        job_id=request.job_id,
        shard_id=request.shard_id,
        label=request.label,
        working_dir=request.working_dir,
        upload_operations=upload_operations,
        command_operation=DaytonaCommandOperation(
            worker_argv=request.worker_argv,
            working_dir=request.working_dir,
        ),
        download_operations=download_operations,
        local_shard_result_path=request.local_shard_result_path,
        request=request,
        summary_text=(
            "daytona_sandbox_operations=READY "
            f"job_id={request.job_id} uploads={len(upload_operations)} "
            f"downloads={len(download_operations)}"
        ),
    )


def build_daytona_batch_operation_plan(
    requests: Sequence[DaytonaShardExecutionRequest],
) -> DaytonaBatchOperationPlan:
    """Build deterministic operation plans in request input order."""

    request_tuple = _request_sequence(requests)
    operation_plans = tuple(
        build_daytona_sandbox_operation_plan(request)
        for request in request_tuple
    )
    return DaytonaBatchOperationPlan(
        operation_plans=operation_plans,
        summary_text=(
            "daytona_batch_operations=READY "
            f"jobs={len(operation_plans)} "
            f"uploads={sum(len(plan.upload_operations) for plan in operation_plans)} "
            f"downloads={sum(len(plan.download_operations) for plan in operation_plans)}"
        ),
    )


def _request_sequence(
    value: Sequence[DaytonaShardExecutionRequest],
) -> tuple[DaytonaShardExecutionRequest, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError("requests must be a non-string sequence")
    if not value:
        raise ValueError("requests must contain at least one request")
    result = []
    for index, item in enumerate(value):
        if not isinstance(item, DaytonaShardExecutionRequest):
            raise ValueError(f"requests[{index}] must be a DaytonaShardExecutionRequest")
        result.append(item)
    return tuple(result)


def _validate_upload_tuple(value: object, name: str) -> None:
    if not isinstance(value, tuple):
        raise ValueError(f"{name} must be a tuple")
    for index, item in enumerate(value):
        if not isinstance(item, DaytonaUploadOperation):
            raise ValueError(f"{name}[{index}] must be a DaytonaUploadOperation")


def _validate_download_tuple(value: object, name: str) -> None:
    if not isinstance(value, tuple):
        raise ValueError(f"{name} must be a tuple")
    for index, item in enumerate(value):
        if not isinstance(item, DaytonaDownloadOperation):
            raise ValueError(f"{name}[{index}] must be a DaytonaDownloadOperation")


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
    "DaytonaBatchOperationPlan",
    "DaytonaCommandOperation",
    "DaytonaDownloadOperation",
    "DaytonaSandboxOperationPlan",
    "DaytonaUploadOperation",
    "build_daytona_batch_operation_plan",
    "build_daytona_sandbox_operation_plan",
)
