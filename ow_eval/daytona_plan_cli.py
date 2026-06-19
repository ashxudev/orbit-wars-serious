"""Write deterministic Daytona shard job plan JSON files.

Distributed Evaluation Cycle 11 persists the pure Cycle 10 Daytona-ready job
plan for later sandbox orchestration. It does not call Daytona, spawn
subprocesses, execute worker commands, upload files, download files, or run
matches.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .daytona_jobs import (
    DEFAULT_PYTHON_COMMAND,
    DEFAULT_RUNNER_SCRIPT,
    DEFAULT_SANDBOX_NAME_PREFIX,
    DEFAULT_WORKING_DIR,
    DaytonaShardJobPlan,
    DaytonaShardJobPlanConfig,
    build_daytona_shard_job_plan,
)


@dataclass(frozen=True, slots=True)
class DaytonaShardJobPlanWriteResult:
    """Outcome from preparing and writing one Daytona shard job plan JSON."""

    index_path: str
    output_path: str
    config: DaytonaShardJobPlanConfig | None = None
    plan: DaytonaShardJobPlan | None = None
    exit_code: int = 2
    summary_text: str = ""
    error_text: str | None = None

    def __post_init__(self) -> None:
        _validate_nonempty_string(self.index_path, "index_path")
        _validate_nonempty_string(self.output_path, "output_path")
        if self.config is not None and not isinstance(
            self.config,
            DaytonaShardJobPlanConfig,
        ):
            raise ValueError("config must be a DaytonaShardJobPlanConfig")
        if self.plan is not None and not isinstance(self.plan, DaytonaShardJobPlan):
            raise ValueError("plan must be a DaytonaShardJobPlan")
        if isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int):
            raise ValueError("exit_code must be an integer")
        _validate_nonempty_string(self.summary_text, "summary_text")
        if self.error_text is not None:
            _validate_nonempty_string(self.error_text, "error_text")

    @property
    def passed(self) -> bool:
        """Return true when the plan JSON was written successfully."""

        return self.exit_code == 0

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "index_path": self.index_path,
            "output_path": self.output_path,
            "config": self.config.to_dict() if self.config is not None else None,
            "plan": self.plan.to_dict() if self.plan is not None else None,
            "exit_code": self.exit_code,
            "passed": self.passed,
            "summary_text": self.summary_text,
            "error_text": self.error_text,
        }


def write_daytona_shard_job_plan(
    plan: DaytonaShardJobPlan,
    path: str | Path,
) -> Path:
    """Write ``plan`` as deterministic UTF-8 JSON to ``path``."""

    if not isinstance(plan, DaytonaShardJobPlan):
        raise ValueError("plan must be a DaytonaShardJobPlan")
    output_path = Path(_path_text(path, "path"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(plan.to_dict(), sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def prepare_daytona_shard_job_plan(
    index_path: str | Path,
    *,
    output_path: str | Path,
    working_dir: str = DEFAULT_WORKING_DIR,
    python_command: str = DEFAULT_PYTHON_COMMAND,
    runner_script: str = DEFAULT_RUNNER_SCRIPT,
    sandbox_name_prefix: str | None = DEFAULT_SANDBOX_NAME_PREFIX,
) -> DaytonaShardJobPlanWriteResult:
    """Build and write one deterministic Daytona shard job plan JSON file."""

    index_path_text = _safe_path_text(index_path, "index_path")
    output_path_text = _safe_path_text(output_path, "output_path")
    try:
        index_path_text = _path_text(index_path, "index_path")
        output_path_text = _path_text(output_path, "output_path")
        config = DaytonaShardJobPlanConfig(
            working_dir=working_dir,
            python_command=python_command,
            runner_script=runner_script,
            sandbox_name_prefix=sandbox_name_prefix,
        )
        plan = build_daytona_shard_job_plan(index_path, config)
        written_path = write_daytona_shard_job_plan(plan, output_path)
        return DaytonaShardJobPlanWriteResult(
            index_path=index_path_text,
            output_path=str(written_path),
            config=config,
            plan=plan,
            exit_code=0,
            summary_text=(
                "daytona_shard_job_plan=WRITTEN "
                f"index_path={index_path_text} output_path={written_path} "
                f"jobs={len(plan.specs)} exit_code=0"
            ),
        )
    except Exception as exc:  # noqa: BLE001 - CLI boundary returns structured errors.
        return DaytonaShardJobPlanWriteResult(
            index_path=index_path_text,
            output_path=output_path_text,
            config=config if "config" in locals() else None,
            plan=plan if "plan" in locals() else None,
            exit_code=2,
            summary_text=(
                "daytona_shard_job_plan=ERROR "
                f"index_path={index_path_text} output_path={output_path_text} "
                "exit_code=2"
            ),
            error_text=f"{type(exc).__name__}: {exc}",
        )


def main(argv: Sequence[str] | None = None) -> int:
    """Prepare one Daytona shard job plan JSON from command-line arguments."""

    parser = argparse.ArgumentParser(
        description="Prepare a deterministic Daytona shard job plan JSON file.",
    )
    parser.add_argument("index", help="Shard job package index JSON path.")
    parser.add_argument(
        "--output-path",
        required=True,
        help="Required output path for the Daytona shard job plan JSON.",
    )
    parser.add_argument(
        "--working-dir",
        default=DEFAULT_WORKING_DIR,
        help="Worker working directory to include in every job spec.",
    )
    parser.add_argument(
        "--python-command",
        default=DEFAULT_PYTHON_COMMAND,
        help="Python command to include in every structured worker argv.",
    )
    parser.add_argument(
        "--runner-script",
        default=DEFAULT_RUNNER_SCRIPT,
        help="Shard job runner script path to include in every worker argv.",
    )
    parser.add_argument(
        "--sandbox-name-prefix",
        default=DEFAULT_SANDBOX_NAME_PREFIX,
        help="Prefix for deterministic sandbox names.",
    )
    parser.add_argument(
        "--no-sandbox-name-prefix",
        action="store_true",
        help="Do not generate sandbox names in job specs.",
    )
    args = parser.parse_args(argv)

    result = prepare_daytona_shard_job_plan(
        args.index,
        output_path=args.output_path,
        working_dir=args.working_dir,
        python_command=args.python_command,
        runner_script=args.runner_script,
        sandbox_name_prefix=(
            None
            if args.no_sandbox_name_prefix
            else args.sandbox_name_prefix
        ),
    )
    print(result.summary_text)
    if result.error_text is not None:
        print(result.error_text, file=sys.stderr)
    return result.exit_code


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
    "DaytonaShardJobPlanWriteResult",
    "main",
    "prepare_daytona_shard_job_plan",
    "write_daytona_shard_job_plan",
)
