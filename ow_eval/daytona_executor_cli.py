"""Dry-run CLI boundary for Daytona shard job execution plans.

Distributed Evaluation Cycle 14 reads a Daytona shard job plan, validates it
through the existing preflight path, and runs it through the Cycle 13 executor
orchestration using a deterministic dry-run executor. It does not call Daytona,
spawn subprocesses, execute worker argv, upload/download files, or run matches.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .daytona_executor import (
    DaytonaShardExecutionBatchResult,
    DaytonaShardExecutionRequest,
    DaytonaShardExecutionResult,
    run_daytona_shard_job_plan,
)


@dataclass(frozen=True, slots=True)
class DaytonaExecutorCliResult:
    """Structured result from a dry-run Daytona executor CLI workflow."""

    plan_path: str
    dry_run: bool
    batch_result: DaytonaShardExecutionBatchResult | None = None
    json_output_path: str | None = None
    exit_code: int = 2
    summary_text: str = ""
    error_text: str | None = None

    def __post_init__(self) -> None:
        _validate_nonempty_string(self.plan_path, "plan_path")
        if not isinstance(self.dry_run, bool):
            raise ValueError("dry_run must be a boolean")
        if self.batch_result is not None and not isinstance(
            self.batch_result,
            DaytonaShardExecutionBatchResult,
        ):
            raise ValueError("batch_result must be a DaytonaShardExecutionBatchResult")
        if self.json_output_path is not None:
            _validate_nonempty_string(self.json_output_path, "json_output_path")
        if isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int):
            raise ValueError("exit_code must be an integer")
        _validate_nonempty_string(self.summary_text, "summary_text")
        if self.error_text is not None:
            _validate_nonempty_string(self.error_text, "error_text")

    @property
    def passed(self) -> bool:
        """Return true when the dry-run workflow completed successfully."""

        return self.exit_code == 0

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "plan_path": self.plan_path,
            "dry_run": self.dry_run,
            "batch_result": (
                self.batch_result.to_dict()
                if self.batch_result is not None
                else None
            ),
            "json_output_path": self.json_output_path,
            "exit_code": self.exit_code,
            "passed": self.passed,
            "summary_text": self.summary_text,
            "error_text": self.error_text,
        }


class DaytonaDryRunExecutor:
    """Deterministic dry-run executor for Daytona shard execution requests."""

    def __init__(
        self,
        *,
        fail_job_id: str | None = None,
        fail_job_index: int | None = None,
    ) -> None:
        if fail_job_id is not None:
            _validate_nonempty_string(fail_job_id, "fail_job_id")
        if fail_job_index is not None:
            if isinstance(fail_job_index, bool) or not isinstance(fail_job_index, int):
                raise ValueError("fail_job_index must be an integer")
            if fail_job_index < 0:
                raise ValueError("fail_job_index must be non-negative")
        self.fail_job_id = fail_job_id
        self.fail_job_index = fail_job_index
        self.requests: list[DaytonaShardExecutionRequest] = []

    def execute(
        self,
        request: DaytonaShardExecutionRequest,
    ) -> DaytonaShardExecutionResult:
        """Return a deterministic synthetic result for one request."""

        job_index = len(self.requests)
        self.requests.append(request)
        if self._should_fail(request.job_id, job_index):
            return DaytonaShardExecutionResult(
                job_id=request.job_id,
                shard_id=request.shard_id,
                label=request.label,
                sandbox_name=request.sandbox_name,
                shard_result_path=request.local_shard_result_path,
                exit_code=2,
                summary_text=(
                    "daytona_dry_run=ERROR "
                    f"job_id={request.job_id} job_index={job_index} exit_code=2"
                ),
                error_text=(
                    "synthetic dry-run failure: "
                    f"job_id={request.job_id} job_index={job_index}"
                ),
            )
        return DaytonaShardExecutionResult(
            job_id=request.job_id,
            shard_id=request.shard_id,
            label=request.label,
            sandbox_name=request.sandbox_name,
            shard_result_path=request.local_shard_result_path,
            exit_code=0,
            summary_text=(
                "daytona_dry_run=COMPLETE "
                f"job_id={request.job_id} job_index={job_index} exit_code=0"
            ),
        )

    def _should_fail(self, job_id: str, job_index: int) -> bool:
        return job_id == self.fail_job_id or job_index == self.fail_job_index


def run_daytona_shard_jobs(
    plan_path: str | Path,
    *,
    dry_run: bool = False,
    require_upload_paths_exist: bool = True,
    require_unique_sandbox_names: bool = True,
    fail_job_id: str | None = None,
    fail_job_index: int | None = None,
    json_output: str | Path | None = None,
) -> DaytonaExecutorCliResult:
    """Dry-run one Daytona shard job plan through the executor boundary."""

    plan_path_text = _safe_path_text(plan_path, "plan_path")
    json_output_text = (
        _safe_path_text(json_output, "json_output")
        if json_output is not None
        else None
    )
    if not dry_run:
        return DaytonaExecutorCliResult(
            plan_path=plan_path_text,
            dry_run=False,
            json_output_path=json_output_text,
            exit_code=2,
            summary_text=(
                "daytona_shard_jobs_cli=ERROR "
                f"plan_path={plan_path_text} dry_run=False exit_code=2"
            ),
            error_text="dry-run mode is required in this cycle",
        )
    try:
        plan_path_text = _path_text(plan_path, "plan_path")
        executor = DaytonaDryRunExecutor(
            fail_job_id=fail_job_id,
            fail_job_index=fail_job_index,
        )
        batch_result = run_daytona_shard_job_plan(
            plan_path,
            executor,
            require_upload_paths_exist=require_upload_paths_exist,
            require_unique_sandbox_names=require_unique_sandbox_names,
            merge_results=False,
        )
        if json_output is not None:
            json_output_text = str(_write_json(batch_result.to_dict(), json_output))
        return DaytonaExecutorCliResult(
            plan_path=plan_path_text,
            dry_run=True,
            batch_result=batch_result,
            json_output_path=json_output_text,
            exit_code=batch_result.exit_code,
            summary_text=(
                "daytona_shard_jobs_cli="
                f"{'COMPLETE' if batch_result.exit_code == 0 else 'ERROR'} "
                f"plan_path={plan_path_text} dry_run=True "
                f"jobs={len(batch_result.execution_results)} "
                f"exit_code={batch_result.exit_code}"
            ),
            error_text=batch_result.error_text,
        )
    except Exception as exc:  # noqa: BLE001 - CLI boundary returns structured errors.
        return DaytonaExecutorCliResult(
            plan_path=plan_path_text,
            dry_run=True,
            json_output_path=json_output_text,
            exit_code=2,
            summary_text=(
                "daytona_shard_jobs_cli=ERROR "
                f"plan_path={plan_path_text} dry_run=True exit_code=2"
            ),
            error_text=f"{type(exc).__name__}: {exc}",
        )


def main(argv: Sequence[str] | None = None) -> int:
    """Run a deterministic dry-run Daytona shard job plan from CLI arguments."""

    parser = argparse.ArgumentParser(
        description="Dry-run a deterministic Daytona shard job plan JSON file.",
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
        "--fail-job-id",
        help="Inject a deterministic dry-run failure for one job id.",
    )
    parser.add_argument(
        "--fail-job-index",
        type=int,
        help="Inject a deterministic dry-run failure for one zero-based job index.",
    )
    parser.add_argument(
        "--json-output",
        help="Optional output path for the execution batch result JSON.",
    )
    args = parser.parse_args(argv)

    result = run_daytona_shard_jobs(
        args.plan,
        dry_run=args.dry_run,
        require_upload_paths_exist=not args.no_upload_path_existence_check,
        require_unique_sandbox_names=not args.allow_duplicate_sandbox_names,
        fail_job_id=args.fail_job_id,
        fail_job_index=args.fail_job_index,
        json_output=args.json_output,
    )
    print(result.summary_text)
    if result.batch_result is not None:
        print(result.batch_result.summary_text)
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
    "DaytonaDryRunExecutor",
    "DaytonaExecutorCliResult",
    "main",
    "run_daytona_shard_jobs",
)
