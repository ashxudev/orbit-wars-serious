"""Guarded real-Daytona client execution CLI boundary.

Distributed Evaluation Cycle 22 composes the real-execution readiness gate, SDK
adapter, and client-report runner behind an explicit CLI/API opt-in. Tests use
fake SDK modules only. This module does not import Daytona at import time,
create sandboxes, execute worker argv locally, submit to Kaggle, or run matches.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from .daytona_client_report import (
    DaytonaClientExecutionReport,
    run_daytona_shard_job_plan_with_client_report,
)
from .daytona_real_config import (
    DaytonaRealExecutionReadiness,
    read_daytona_real_execution_config_from_env,
    validate_daytona_real_execution_readiness,
)
from .daytona_sdk_adapter import DaytonaSdkAdapter, DaytonaSdkAdapterConfig
from .daytona_source import (
    DAYTONA_SOURCE_MODE_GITHUB,
    DaytonaGitPreflightResult,
    validate_daytona_git_preflight,
)


@dataclass(frozen=True, slots=True)
class DaytonaRealCliResult:
    """Structured result from a guarded real-Daytona CLI/API workflow."""

    plan_path: str
    allow_real_daytona: bool
    readiness: DaytonaRealExecutionReadiness
    expected_git_commit: str | None = None
    git_preflight: DaytonaGitPreflightResult | None = None
    report: DaytonaClientExecutionReport | None = None
    json_output_path: str | None = None
    exit_code: int = 2
    summary_text: str = ""
    error_text: str | None = None

    def __post_init__(self) -> None:
        _validate_nonempty_string(self.plan_path, "plan_path")
        if not isinstance(self.allow_real_daytona, bool):
            raise ValueError("allow_real_daytona must be a boolean")
        if not isinstance(self.readiness, DaytonaRealExecutionReadiness):
            raise ValueError("readiness must be a DaytonaRealExecutionReadiness")
        if self.expected_git_commit is not None:
            _validate_nonempty_string(self.expected_git_commit, "expected_git_commit")
        if self.git_preflight is not None and not isinstance(
            self.git_preflight,
            DaytonaGitPreflightResult,
        ):
            raise ValueError("git_preflight must be a DaytonaGitPreflightResult")
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
        """Return true when the guarded real-Daytona workflow completed."""

        return self.exit_code == 0

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "plan_path": self.plan_path,
            "allow_real_daytona": self.allow_real_daytona,
            "readiness": self.readiness.to_dict(),
            "expected_git_commit": self.expected_git_commit,
            "git_preflight": (
                self.git_preflight.to_dict()
                if self.git_preflight is not None
                else None
            ),
            "report": self.report.to_dict() if self.report is not None else None,
            "json_output_path": self.json_output_path,
            "exit_code": self.exit_code,
            "passed": self.passed,
            "summary_text": self.summary_text,
            "error_text": self.error_text,
        }


def run_daytona_real_shard_jobs(
    plan_path: str | Path,
    *,
    allow_real_daytona: bool = False,
    env: Mapping[str, str] | None = None,
    require_upload_paths_exist: bool = True,
    require_unique_sandbox_names: bool = True,
    sdk_importer: Callable[[str], object] | None = None,
    sdk_client_factory: Callable[[object, object], object] | None = None,
    json_output: str | Path | None = None,
) -> DaytonaRealCliResult:
    """Run one Daytona plan through the explicitly guarded SDK adapter path."""

    plan_path_text = _safe_path_text(plan_path, "plan_path")
    json_output_text = (
        _safe_path_text(json_output, "json_output")
        if json_output is not None
        else None
    )
    try:
        plan_path_text = _path_text(plan_path, "plan_path")
        config = read_daytona_real_execution_config_from_env(env)
        readiness = validate_daytona_real_execution_readiness(config, env=env)
        if not allow_real_daytona:
            error_text = "real Daytona execution requires --allow-real-daytona"
            return DaytonaRealCliResult(
                plan_path=plan_path_text,
                allow_real_daytona=False,
                readiness=readiness,
                json_output_path=json_output_text,
                exit_code=2,
                summary_text=_summary_text(
                    plan_path_text,
                    allow_real_daytona=False,
                    report=None,
                    exit_code=2,
                ),
                error_text=error_text,
            )
        if not readiness.passed:
            return DaytonaRealCliResult(
                plan_path=plan_path_text,
                allow_real_daytona=True,
                readiness=readiness,
                json_output_path=json_output_text,
                exit_code=2,
                summary_text=_summary_text(
                    plan_path_text,
                    allow_real_daytona=True,
                    report=None,
                    exit_code=2,
                ),
                error_text=readiness.error_text,
            )
        git_preflight = validate_daytona_git_preflight(
            source_mode=config.source_mode,
            remote=config.git_remote,
            branch=config.git_branch,
        )
        if not git_preflight.passed:
            return DaytonaRealCliResult(
                plan_path=plan_path_text,
                allow_real_daytona=True,
                readiness=readiness,
                git_preflight=git_preflight,
                json_output_path=json_output_text,
                exit_code=git_preflight.exit_code,
                summary_text=_summary_text(
                    plan_path_text,
                    allow_real_daytona=True,
                    report=None,
                    exit_code=git_preflight.exit_code,
                ),
                error_text=git_preflight.error_text,
            )
        expected_git_commit = _local_git_commit()
        adapter = DaytonaSdkAdapter(
            DaytonaSdkAdapterConfig(
                real_execution_config=config,
                readiness=readiness,
                sdk_importer=sdk_importer,
                sdk_client_factory=sdk_client_factory,
            )
        )
        report = run_daytona_shard_job_plan_with_client_report(
            plan_path,
            adapter,
            require_upload_paths_exist=require_upload_paths_exist,
            require_unique_sandbox_names=require_unique_sandbox_names,
            merge_results=False,
            expected_remote_git_commit=(
                None
                if config.source_mode == DAYTONA_SOURCE_MODE_GITHUB
                else expected_git_commit
            ),
        )
        if json_output is not None:
            json_output_text = str(_write_json(report.to_dict(), json_output))
        return DaytonaRealCliResult(
            plan_path=plan_path_text,
            allow_real_daytona=True,
            readiness=readiness,
            expected_git_commit=expected_git_commit,
            git_preflight=git_preflight,
            report=report,
            json_output_path=json_output_text,
            exit_code=report.exit_code,
            summary_text=_summary_text(
                plan_path_text,
                allow_real_daytona=True,
                report=report,
                exit_code=report.exit_code,
            ),
            error_text=report.error_text,
        )
    except Exception as exc:  # noqa: BLE001 - CLI/API boundary returns errors.
        fallback_readiness = validate_daytona_real_execution_readiness(
            env=env,
        )
        return DaytonaRealCliResult(
            plan_path=plan_path_text,
            allow_real_daytona=allow_real_daytona,
            readiness=fallback_readiness,
            json_output_path=json_output_text,
            exit_code=2,
            summary_text=_summary_text(
                plan_path_text,
                allow_real_daytona=allow_real_daytona,
                report=None,
                exit_code=2,
            ),
            error_text=f"{type(exc).__name__}: {exc}",
        )


def main(argv: Sequence[str] | None = None) -> int:
    """Run a guarded real-Daytona client execution workflow from CLI args."""

    parser = argparse.ArgumentParser(
        description="Run a guarded real-Daytona shard job plan.",
    )
    parser.add_argument("plan", help="Daytona shard job plan JSON path.")
    parser.add_argument(
        "--allow-real-daytona",
        action="store_true",
        help="Required explicit opt-in for real Daytona execution.",
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
        "--json-output",
        help="Optional output path for the full client execution report JSON.",
    )
    args = parser.parse_args(argv)

    result = run_daytona_real_shard_jobs(
        args.plan,
        allow_real_daytona=args.allow_real_daytona,
        require_upload_paths_exist=not args.no_upload_path_existence_check,
        require_unique_sandbox_names=not args.allow_duplicate_sandbox_names,
        json_output=args.json_output,
    )
    _print_result(result, stdout=sys.stdout, stderr=sys.stderr)
    return result.exit_code


def _print_result(
    result: DaytonaRealCliResult,
    *,
    stdout: TextIO,
    stderr: TextIO,
) -> None:
    print(result.summary_text, file=stdout)
    if result.report is not None:
        print(result.report.summary_text, file=stdout)
    if result.error_text is not None:
        print(result.error_text, file=stderr)


def _summary_text(
    plan_path: str,
    *,
    allow_real_daytona: bool,
    report: DaytonaClientExecutionReport | None,
    exit_code: int,
) -> str:
    status = "COMPLETE" if exit_code == 0 else "ERROR"
    events = len(report.client_event_trace) if report is not None else 0
    operation_plans = len(report.operation_plans) if report is not None else 0
    return (
        f"daytona_real_cli={status} plan_path={plan_path} "
        f"allow_real_daytona={allow_real_daytona} events={events} "
        f"operation_plans={operation_plans} exit_code={exit_code}"
    )


def _write_json(payload: object, path: str | Path) -> Path:
    output_path = Path(_path_text(path, "json_output"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def _local_git_commit() -> str:
    repo_root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    commit = completed.stdout.strip()
    _validate_nonempty_string(commit, "git_commit")
    return commit


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
    "DaytonaRealCliResult",
    "main",
    "run_daytona_real_shard_jobs",
)
