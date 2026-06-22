"""Injected Daytona-like client executor adapter.

Distributed Evaluation Cycle 16 adapts Cycle 15 operation plans to an injected
client protocol. It proves future Daytona control flow with fake/recording
clients only; it does not import Daytona, create real sandboxes, spawn
subprocesses, execute worker argv locally, upload/download real files, or run
matches.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .daytona_executor import (
    DaytonaShardExecutionRequest,
    DaytonaShardExecutionResult,
    run_daytona_shard_job_plan,
)
from .daytona_jobs import DaytonaShardJobPlan
from .daytona_operations import (
    DaytonaCommandOperation,
    DaytonaDownloadOperation,
    DaytonaSandboxOperationPlan,
    DaytonaUploadOperation,
    build_daytona_sandbox_operation_plan,
)
from .daytona_runtime_snapshot import DAYTONA_RUNTIME_COMMIT_MARKER


@dataclass(frozen=True, slots=True)
class DaytonaSandboxHandle:
    """Typed handle returned by an injected Daytona-like sandbox client."""

    sandbox_name: str | None
    working_dir: str
    handle_id: str

    def __post_init__(self) -> None:
        if self.sandbox_name is not None:
            _validate_nonempty_string(self.sandbox_name, "sandbox_name")
        _validate_nonempty_string(self.working_dir, "working_dir")
        _validate_nonempty_string(self.handle_id, "handle_id")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "sandbox_name": self.sandbox_name,
            "working_dir": self.working_dir,
            "handle_id": self.handle_id,
        }


@dataclass(frozen=True, slots=True)
class DaytonaClientCommandResult:
    """Result returned by an injected client command operation."""

    exit_code: int = 0
    stdout: str | None = None
    stderr: str | None = None
    summary_text: str = "daytona_client_command=COMPLETE exit_code=0"

    def __post_init__(self) -> None:
        if isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int):
            raise ValueError("exit_code must be an integer")
        if self.stdout is not None and not isinstance(self.stdout, str):
            raise ValueError("stdout must be a string when provided")
        if self.stderr is not None and not isinstance(self.stderr, str):
            raise ValueError("stderr must be a string when provided")
        _validate_nonempty_string(self.summary_text, "summary_text")

    @property
    def passed(self) -> bool:
        """Return true when the client command exited successfully."""

        return self.exit_code == 0

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "exit_code": self.exit_code,
            "passed": self.passed,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "summary_text": self.summary_text,
        }


@dataclass(frozen=True, slots=True)
class DaytonaClientExecutionEvent:
    """Structured event for one attempted client executor step."""

    job_id: str
    shard_id: str
    label: str
    sandbox_name: str | None
    step: str
    status: str
    detail: str
    exit_code: int | None = None
    error_text: str | None = None

    def __post_init__(self) -> None:
        _validate_nonempty_string(self.job_id, "job_id")
        _validate_nonempty_string(self.shard_id, "shard_id")
        _validate_nonempty_string(self.label, "label")
        if self.sandbox_name is not None:
            _validate_nonempty_string(self.sandbox_name, "sandbox_name")
        _validate_nonempty_string(self.step, "step")
        _validate_nonempty_string(self.status, "status")
        _validate_nonempty_string(self.detail, "detail")
        if self.exit_code is not None:
            if isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int):
                raise ValueError("exit_code must be an integer when provided")
        if self.error_text is not None:
            _validate_nonempty_string(self.error_text, "error_text")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "job_id": self.job_id,
            "shard_id": self.shard_id,
            "label": self.label,
            "sandbox_name": self.sandbox_name,
            "step": self.step,
            "status": self.status,
            "detail": self.detail,
            "exit_code": self.exit_code,
            "error_text": self.error_text,
        }


class DaytonaSandboxClient(Protocol):
    """Protocol for an injected Daytona-like sandbox client."""

    def open_sandbox(
        self,
        *,
        sandbox_name: str | None,
        working_dir: str,
    ) -> DaytonaSandboxHandle:
        """Prepare or open one sandbox."""
        ...

    def upload_file(
        self,
        handle: DaytonaSandboxHandle,
        operation: DaytonaUploadOperation,
    ) -> None:
        """Upload one planned input file."""
        ...

    def run_command(
        self,
        handle: DaytonaSandboxHandle,
        operation: DaytonaCommandOperation,
    ) -> DaytonaClientCommandResult:
        """Run one structured command operation."""
        ...

    def download_file(
        self,
        handle: DaytonaSandboxHandle,
        operation: DaytonaDownloadOperation,
    ) -> None:
        """Download one planned output file."""
        ...

    def close_sandbox(self, handle: DaytonaSandboxHandle) -> None:
        """Close or release one sandbox."""
        ...


class DaytonaClientExecutor:
    """Adapter from execution requests to an injected Daytona-like client."""

    def __init__(
        self,
        client: DaytonaSandboxClient,
        *,
        expected_remote_git_commit: str | None = None,
        remote_commit_marker_path: str = DAYTONA_RUNTIME_COMMIT_MARKER,
    ) -> None:
        if expected_remote_git_commit is not None:
            _validate_nonempty_string(
                expected_remote_git_commit,
                "expected_remote_git_commit",
            )
        _validate_nonempty_string(remote_commit_marker_path, "remote_commit_marker_path")
        self.client = client
        self.events: list[DaytonaClientExecutionEvent] = []
        self.operation_plans: list[DaytonaSandboxOperationPlan] = []
        self.expected_remote_git_commit = expected_remote_git_commit
        self.remote_commit_marker_path = remote_commit_marker_path

    @property
    def event_trace(self) -> tuple[DaytonaClientExecutionEvent, ...]:
        """Return all recorded client execution events in order."""

        return tuple(self.events)

    def execute(
        self,
        request: DaytonaShardExecutionRequest,
    ) -> DaytonaShardExecutionResult:
        """Execute one request through the injected client protocol."""

        if not isinstance(request, DaytonaShardExecutionRequest):
            raise ValueError("request must be a DaytonaShardExecutionRequest")
        plan = build_daytona_sandbox_operation_plan(request)
        self.operation_plans.append(plan)
        handle: DaytonaSandboxHandle | None = None
        close_error: str | None = None
        result: DaytonaShardExecutionResult | None = None

        try:
            handle = self._open(plan)
            self._verify_remote_git_commit(plan, handle)
            self._upload_all(plan, handle)
            command_result = self._run_command(plan, handle)
            if command_result.exit_code != 0:
                result = self._failure_result(
                    plan,
                    step="command",
                    error_text=(
                        f"command failed: exit_code={command_result.exit_code}"
                        + (
                            f": {command_result.stderr}"
                            if command_result.stderr is not None
                            else ""
                        )
                    ),
                    exit_code=command_result.exit_code,
                )
            else:
                completed_downloads, optional_missing_downloads = self._download_all(
                    plan,
                    handle,
                )
                result = DaytonaShardExecutionResult(
                    job_id=plan.job_id,
                    shard_id=plan.shard_id,
                    label=plan.label,
                    sandbox_name=plan.sandbox_name,
                    shard_result_path=plan.local_shard_result_path,
                    exit_code=0,
                    summary_text=(
                        "daytona_client_execution=COMPLETE "
                        f"job_id={plan.job_id} uploads={len(plan.upload_operations)} "
                        f"downloads={completed_downloads}/{len(plan.download_operations)} "
                        f"optional_missing_downloads={optional_missing_downloads}"
                    ),
                )
        except Exception as exc:  # noqa: BLE001 - executor returns structured failure.
            result = self._failure_result(
                plan,
                step="client",
                error_text=f"{type(exc).__name__}: {exc}",
                exit_code=2,
            )
        finally:
            if handle is not None:
                try:
                    self._close(plan, handle)
                except Exception as exc:  # noqa: BLE001 - cleanup is traced.
                    close_error = f"{type(exc).__name__}: {exc}"
                    self._event(plan, "close", "error", handle.handle_id, close_error)
            if close_error is not None and result is not None and result.exit_code == 0:
                result = DaytonaShardExecutionResult(
                    job_id=plan.job_id,
                    shard_id=plan.shard_id,
                    label=plan.label,
                    sandbox_name=plan.sandbox_name,
                    shard_result_path=None,
                    exit_code=2,
                    summary_text=(
                        "daytona_client_execution=ERROR "
                        f"job_id={plan.job_id} step=close exit_code=2"
                    ),
                    error_text=close_error,
                )
        if result is None:
            return self._failure_result(
                plan,
                step="client",
                error_text="RuntimeError: client executor produced no result",
                exit_code=2,
            )
        return result

    def _open(self, plan: DaytonaSandboxOperationPlan) -> DaytonaSandboxHandle:
        self._event(plan, "open", "attempted", plan.working_dir)
        handle = self.client.open_sandbox(
            sandbox_name=plan.sandbox_name,
            working_dir=plan.working_dir,
        )
        if not isinstance(handle, DaytonaSandboxHandle):
            raise ValueError("client.open_sandbox must return DaytonaSandboxHandle")
        self._event(plan, "open", "completed", handle.handle_id)
        return handle

    def _upload_all(
        self,
        plan: DaytonaSandboxOperationPlan,
        handle: DaytonaSandboxHandle,
    ) -> None:
        for operation in plan.upload_operations:
            detail = f"{operation.local_path}->{operation.sandbox_path}"
            self._event(plan, "upload", "attempted", detail)
            self.client.upload_file(handle, operation)
            self._event(plan, "upload", "completed", detail)

    def _verify_remote_git_commit(
        self,
        plan: DaytonaSandboxOperationPlan,
        handle: DaytonaSandboxHandle,
    ) -> None:
        expected_commit = self.expected_remote_git_commit
        if expected_commit is None:
            return
        detail = f"expected={expected_commit}"
        self._event(plan, "snapshot_commit", "attempted", detail)
        result = self.client.run_command(
            handle,
            DaytonaCommandOperation(
                worker_argv=(
                    ".venv/bin/python",
                    "-c",
                    (
                        "from pathlib import Path; "
                        f"print(Path({self.remote_commit_marker_path!r}).read_text().strip())"
                    ),
                ),
                working_dir=plan.working_dir,
            ),
        )
        if not isinstance(result, DaytonaClientCommandResult):
            raise ValueError("client.run_command must return DaytonaClientCommandResult")
        remote_commit = (result.stdout or "").strip()
        if result.exit_code != 0:
            self._event(
                plan,
                "snapshot_commit",
                "error",
                result.summary_text,
                error_text=result.stderr or result.summary_text,
                exit_code=result.exit_code,
            )
            raise RuntimeError(
                "remote snapshot commit check failed: "
                f"exit_code={result.exit_code}"
            )
        if remote_commit != expected_commit:
            error_text = (
                "remote snapshot commit mismatch: "
                f"expected={expected_commit} actual={remote_commit or '<empty>'}"
            )
            self._event(
                plan,
                "snapshot_commit",
                "error",
                error_text,
                error_text=error_text,
                exit_code=2,
            )
            raise RuntimeError(error_text)
        self._event(plan, "snapshot_commit", "completed", f"actual={remote_commit}")

    def _run_command(
        self,
        plan: DaytonaSandboxOperationPlan,
        handle: DaytonaSandboxHandle,
    ) -> DaytonaClientCommandResult:
        detail = f"argv_count={len(plan.command_operation.worker_argv)}"
        self._event(plan, "command", "attempted", detail)
        result = self.client.run_command(handle, plan.command_operation)
        if not isinstance(result, DaytonaClientCommandResult):
            raise ValueError("client.run_command must return DaytonaClientCommandResult")
        status = "completed" if result.exit_code == 0 else "error"
        self._event(
            plan,
            "command",
            status,
            result.summary_text,
            error_text=result.stderr if result.exit_code != 0 else None,
            exit_code=result.exit_code,
        )
        return result

    def _download_all(
        self,
        plan: DaytonaSandboxOperationPlan,
        handle: DaytonaSandboxHandle,
    ) -> tuple[int, int]:
        completed_downloads = 0
        optional_missing_downloads = 0
        for operation in plan.download_operations:
            detail = f"{operation.sandbox_path}->{operation.local_path}"
            self._event(plan, "download", "attempted", detail)
            try:
                self.client.download_file(handle, operation)
            except Exception as exc:
                if operation.local_path == plan.local_shard_result_path:
                    raise
                optional_missing_downloads += 1
                self._event(
                    plan,
                    "download",
                    "optional_missing",
                    detail,
                    error_text=f"{type(exc).__name__}: {exc}",
                    exit_code=0,
                )
                continue
            completed_downloads += 1
            self._event(plan, "download", "completed", detail)
        return completed_downloads, optional_missing_downloads

    def _close(
        self,
        plan: DaytonaSandboxOperationPlan,
        handle: DaytonaSandboxHandle,
    ) -> None:
        self._event(plan, "close", "attempted", handle.handle_id)
        self.client.close_sandbox(handle)
        self._event(plan, "close", "completed", handle.handle_id)

    def _failure_result(
        self,
        plan: DaytonaSandboxOperationPlan,
        *,
        step: str,
        error_text: str,
        exit_code: int,
    ) -> DaytonaShardExecutionResult:
        self._event(plan, step, "error", error_text, error_text, exit_code)
        return DaytonaShardExecutionResult(
            job_id=plan.job_id,
            shard_id=plan.shard_id,
            label=plan.label,
            sandbox_name=plan.sandbox_name,
            shard_result_path=None,
            exit_code=exit_code if exit_code != 0 else 2,
            summary_text=(
                "daytona_client_execution=ERROR "
                f"job_id={plan.job_id} step={step} exit_code="
                f"{exit_code if exit_code != 0 else 2}"
            ),
            error_text=error_text,
        )

    def _event(
        self,
        plan: DaytonaSandboxOperationPlan,
        step: str,
        status: str,
        detail: str,
        error_text: str | None = None,
        exit_code: int | None = None,
    ) -> None:
        self.events.append(
            DaytonaClientExecutionEvent(
                job_id=plan.job_id,
                shard_id=plan.shard_id,
                label=plan.label,
                sandbox_name=plan.sandbox_name,
                step=step,
                status=status,
                detail=detail,
                exit_code=exit_code,
                error_text=error_text,
            )
        )


def run_daytona_shard_job_plan_with_client(
    plan_or_path: DaytonaShardJobPlan | str | Path,
    client: DaytonaSandboxClient,
    *,
    require_upload_paths_exist: bool = True,
    require_unique_sandbox_names: bool = True,
    merge_results: bool = True,
    expected_remote_git_commit: str | None = None,
):
    """Run a Daytona shard job plan through an injected client executor."""

    executor = DaytonaClientExecutor(
        client,
        expected_remote_git_commit=expected_remote_git_commit,
    )
    return run_daytona_shard_job_plan(
        plan_or_path,
        executor,
        require_upload_paths_exist=require_upload_paths_exist,
        require_unique_sandbox_names=require_unique_sandbox_names,
        merge_results=merge_results,
    )


def _validate_nonempty_string(value: object, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


__all__ = (
    "DaytonaClientCommandResult",
    "DaytonaClientExecutionEvent",
    "DaytonaClientExecutor",
    "DaytonaSandboxClient",
    "DaytonaSandboxHandle",
    "run_daytona_shard_job_plan_with_client",
)
