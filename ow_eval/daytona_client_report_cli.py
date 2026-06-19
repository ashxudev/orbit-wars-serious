"""Dry-run CLI boundary for Daytona client execution reports.

Distributed Evaluation Cycle 18 reads a Daytona shard job plan, runs it through
the Cycle 17 client-report path with a deterministic recording client, and can
write the full JSON report when explicitly requested. It does not import or
call Daytona, create real sandboxes, spawn subprocesses, execute worker argv,
upload/download real files, or run matches.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .daytona_client_executor import (
    DaytonaClientCommandResult,
    DaytonaSandboxHandle,
)
from .daytona_client_report import (
    DaytonaClientExecutionReport,
    run_daytona_shard_job_plan_with_client_report,
)


VALID_FAILURE_STEPS = ("open", "upload", "command", "download", "close")


@dataclass(frozen=True, slots=True)
class DaytonaClientReportCliResult:
    """Structured result from a dry-run Daytona client report CLI workflow."""

    plan_path: str
    dry_run: bool
    report: DaytonaClientExecutionReport | None = None
    json_output_path: str | None = None
    exit_code: int = 2
    summary_text: str = ""
    error_text: str | None = None

    def __post_init__(self) -> None:
        _validate_nonempty_string(self.plan_path, "plan_path")
        if not isinstance(self.dry_run, bool):
            raise ValueError("dry_run must be a boolean")
        if self.report is not None and not isinstance(
            self.report,
            DaytonaClientExecutionReport,
        ):
            raise ValueError("report must be a DaytonaClientExecutionReport")
        if self.json_output_path is not None:
            _validate_nonempty_string(self.json_output_path, "json_output_path")
        if isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int):
            raise ValueError("exit_code must be an integer")
        _validate_nonempty_string(self.summary_text, "summary_text")
        if self.error_text is not None:
            _validate_nonempty_string(self.error_text, "error_text")

    @property
    def passed(self) -> bool:
        """Return true when the dry-run report workflow completed successfully."""

        return self.exit_code == 0

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "plan_path": self.plan_path,
            "dry_run": self.dry_run,
            "report": self.report.to_dict() if self.report is not None else None,
            "json_output_path": self.json_output_path,
            "exit_code": self.exit_code,
            "passed": self.passed,
            "summary_text": self.summary_text,
            "error_text": self.error_text,
        }


class DaytonaRecordingClient:
    """Deterministic recording client for Daytona client report dry-runs."""

    def __init__(
        self,
        *,
        fail_step: str | None = None,
        command_exit_code: int = 0,
    ) -> None:
        if fail_step is not None and fail_step not in VALID_FAILURE_STEPS:
            raise ValueError(
                "fail_step must be one of: " + ", ".join(VALID_FAILURE_STEPS)
            )
        if isinstance(command_exit_code, bool) or not isinstance(command_exit_code, int):
            raise ValueError("command_exit_code must be an integer")
        self.fail_step = fail_step
        self.command_exit_code = command_exit_code
        self.calls: list[tuple[object, ...]] = []

    def open_sandbox(
        self,
        *,
        sandbox_name: str | None,
        working_dir: str,
    ) -> DaytonaSandboxHandle:
        """Record and return a synthetic sandbox handle."""

        self.calls.append(("open", sandbox_name, working_dir))
        if self.fail_step == "open":
            raise RuntimeError("synthetic open failure")
        return DaytonaSandboxHandle(
            sandbox_name=sandbox_name,
            working_dir=working_dir,
            handle_id=f"dry-run-{sandbox_name or 'default'}",
        )

    def upload_file(self, handle, operation):  # noqa: ANN001 - protocol adapter.
        """Record one synthetic upload operation."""

        self.calls.append(("upload", operation.local_path, operation.sandbox_path))
        if self.fail_step == "upload":
            raise RuntimeError("synthetic upload failure")

    def run_command(self, handle, operation):  # noqa: ANN001 - protocol adapter.
        """Record one synthetic structured command operation."""

        self.calls.append(("command", operation.worker_argv, operation.working_dir))
        if self.fail_step == "command":
            raise RuntimeError("synthetic command failure")
        return DaytonaClientCommandResult(
            exit_code=self.command_exit_code,
            stdout="dry-run command ok" if self.command_exit_code == 0 else None,
            stderr=(
                f"synthetic command exit {self.command_exit_code}"
                if self.command_exit_code != 0
                else None
            ),
            summary_text=(
                "daytona_recording_client_command="
                f"{'COMPLETE' if self.command_exit_code == 0 else 'ERROR'} "
                f"exit_code={self.command_exit_code}"
            ),
        )

    def download_file(self, handle, operation):  # noqa: ANN001 - protocol adapter.
        """Record one synthetic download operation."""

        self.calls.append(("download", operation.sandbox_path, operation.local_path))
        if self.fail_step == "download":
            raise RuntimeError("synthetic download failure")

    def close_sandbox(self, handle):  # noqa: ANN001 - protocol adapter.
        """Record one synthetic sandbox close operation."""

        self.calls.append(("close", handle.handle_id))
        if self.fail_step == "close":
            raise RuntimeError("synthetic close failure")


def run_daytona_client_report(
    plan_path: str | Path,
    *,
    dry_run: bool = False,
    require_upload_paths_exist: bool = True,
    require_unique_sandbox_names: bool = True,
    fail_step: str | None = None,
    command_exit_code: int = 0,
    json_output: str | Path | None = None,
) -> DaytonaClientReportCliResult:
    """Dry-run one Daytona shard job plan and return a client execution report."""

    plan_path_text = _safe_path_text(plan_path, "plan_path")
    json_output_text = (
        _safe_path_text(json_output, "json_output")
        if json_output is not None
        else None
    )
    if not dry_run:
        return DaytonaClientReportCliResult(
            plan_path=plan_path_text,
            dry_run=False,
            json_output_path=json_output_text,
            exit_code=2,
            summary_text=(
                "daytona_client_report_cli=ERROR "
                f"plan_path={plan_path_text} dry_run=False exit_code=2"
            ),
            error_text="dry-run mode is required in this cycle",
        )
    try:
        plan_path_text = _path_text(plan_path, "plan_path")
        client = DaytonaRecordingClient(
            fail_step=fail_step,
            command_exit_code=command_exit_code,
        )
        report = run_daytona_shard_job_plan_with_client_report(
            plan_path,
            client,
            require_upload_paths_exist=require_upload_paths_exist,
            require_unique_sandbox_names=require_unique_sandbox_names,
            merge_results=False,
        )
        if json_output is not None:
            json_output_text = str(_write_json(report.to_dict(), json_output))
        return DaytonaClientReportCliResult(
            plan_path=plan_path_text,
            dry_run=True,
            report=report,
            json_output_path=json_output_text,
            exit_code=report.exit_code,
            summary_text=(
                "daytona_client_report_cli="
                f"{'COMPLETE' if report.exit_code == 0 else 'ERROR'} "
                f"plan_path={plan_path_text} dry_run=True "
                f"events={len(report.client_event_trace)} "
                f"operation_plans={len(report.operation_plans)} "
                f"exit_code={report.exit_code}"
            ),
            error_text=report.error_text,
        )
    except Exception as exc:  # noqa: BLE001 - CLI boundary returns structured errors.
        return DaytonaClientReportCliResult(
            plan_path=plan_path_text,
            dry_run=True,
            json_output_path=json_output_text,
            exit_code=2,
            summary_text=(
                "daytona_client_report_cli=ERROR "
                f"plan_path={plan_path_text} dry_run=True exit_code=2"
            ),
            error_text=f"{type(exc).__name__}: {exc}",
        )


def main(argv: Sequence[str] | None = None) -> int:
    """Run a deterministic Daytona client report dry-run from CLI arguments."""

    parser = argparse.ArgumentParser(
        description="Dry-run a deterministic Daytona client execution report.",
    )
    parser.add_argument("plan", help="Daytona shard job plan JSON path.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Required in this cycle; do not execute remote jobs.",
    )
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
    parser.add_argument(
        "--fail-step",
        choices=VALID_FAILURE_STEPS,
        help="Inject a deterministic fake-client failure at one client step.",
    )
    parser.add_argument(
        "--command-exit-code",
        type=int,
        default=0,
        help="Synthetic client command exit code.",
    )
    parser.add_argument(
        "--json-output",
        help="Optional output path for the full client execution report JSON.",
    )
    args = parser.parse_args(argv)

    result = run_daytona_client_report(
        args.plan,
        dry_run=args.dry_run,
        require_upload_paths_exist=not args.no_upload_path_existence_check,
        require_unique_sandbox_names=not args.allow_duplicate_sandbox_names,
        fail_step=args.fail_step,
        command_exit_code=args.command_exit_code,
        json_output=args.json_output,
    )
    print(result.summary_text)
    if result.report is not None:
        print(result.report.summary_text)
    if result.error_text is not None:
        print(result.error_text, file=sys.stderr)
    return result.exit_code


def _write_json(payload: object, path: str | Path) -> Path:
    output_path = Path(_path_text(path, "json_output"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def _path_text(value: str | Path, name: str) -> str:
    if not isinstance(value, (str, Path)):
        raise ValueError(f"{name} must be a path")
    if isinstance(value, str) and not value:
        raise ValueError(f"{name} must be a non-empty path")
    path_text = str(value)
    _validate_nonempty_string(path_text, name)
    return path_text


def _safe_path_text(value: object, name: str) -> str:
    if isinstance(value, str) and not value:
        return f"<invalid {name}>"
    if not isinstance(value, (str, Path)):
        return f"<invalid {name}>"
    path_text = str(value)
    if not path_text:
        return f"<invalid {name}>"
    return path_text


def _validate_nonempty_string(value: object, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


__all__ = (
    "DaytonaClientReportCliResult",
    "DaytonaRecordingClient",
    "main",
    "run_daytona_client_report",
)
