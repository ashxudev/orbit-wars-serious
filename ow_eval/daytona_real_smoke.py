"""Guarded real-Daytona smoke diagnostics.

This module is intentionally narrower than shard execution. It opens one real
Daytona sandbox, runs one tiny command, and closes the sandbox so failures can
be classified before running full-horizon gauntlet jobs.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from .daytona_client_executor import (
    DaytonaClientCommandResult,
    DaytonaSandboxHandle,
)
from .daytona_operations import DaytonaCommandOperation
from .daytona_real_config import (
    DaytonaRealExecutionReadiness,
    read_daytona_real_execution_config_from_env,
    validate_daytona_real_execution_readiness,
)
from .daytona_sdk_adapter import DaytonaSdkAdapter, DaytonaSdkAdapterConfig


DEFAULT_SMOKE_ARGV = (
    ".venv/bin/python",
    "-c",
    (
        "import pathlib, sys; "
        "import ow_eval; "
        "print('daytona_smoke=OK'); "
        "print('cwd=' + str(pathlib.Path.cwd())); "
        "print('python=' + sys.executable)"
    ),
)


@dataclass(frozen=True, slots=True)
class DaytonaRealSmokeEvent:
    """One structured Daytona smoke diagnostic event."""

    step: str
    status: str
    detail: str
    exit_code: int | None = None
    error_text: str | None = None

    def __post_init__(self) -> None:
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
            "step": self.step,
            "status": self.status,
            "detail": self.detail,
            "exit_code": self.exit_code,
            "error_text": self.error_text,
        }


@dataclass(frozen=True, slots=True)
class DaytonaRealSmokeResult:
    """Structured result from one guarded real-Daytona smoke diagnostic."""

    allow_real_daytona: bool
    readiness: DaytonaRealExecutionReadiness
    sandbox_name: str | None
    working_dir: str
    worker_argv: tuple[str, ...]
    diagnosis: str
    events: tuple[DaytonaRealSmokeEvent, ...]
    command_result: DaytonaClientCommandResult | None = None
    json_output_path: str | None = None
    exit_code: int = 2
    summary_text: str = ""
    error_text: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.allow_real_daytona, bool):
            raise ValueError("allow_real_daytona must be a boolean")
        if not isinstance(self.readiness, DaytonaRealExecutionReadiness):
            raise ValueError("readiness must be a DaytonaRealExecutionReadiness")
        if self.sandbox_name is not None:
            _validate_nonempty_string(self.sandbox_name, "sandbox_name")
        _validate_nonempty_string(self.working_dir, "working_dir")
        _validate_string_tuple(self.worker_argv, "worker_argv")
        _validate_nonempty_string(self.diagnosis, "diagnosis")
        _validate_event_tuple(self.events, "events")
        if self.command_result is not None and not isinstance(
            self.command_result,
            DaytonaClientCommandResult,
        ):
            raise ValueError("command_result must be a DaytonaClientCommandResult")
        if self.json_output_path is not None:
            _validate_nonempty_string(self.json_output_path, "json_output_path")
        if isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int):
            raise ValueError("exit_code must be an integer")
        _validate_nonempty_string(self.summary_text, "summary_text")
        if self.error_text is not None:
            _validate_nonempty_string(self.error_text, "error_text")

    @property
    def passed(self) -> bool:
        """Return true when the smoke diagnostic completed successfully."""

        return self.exit_code == 0

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "allow_real_daytona": self.allow_real_daytona,
            "readiness": self.readiness.to_dict(),
            "sandbox_name": self.sandbox_name,
            "working_dir": self.working_dir,
            "worker_argv": list(self.worker_argv),
            "diagnosis": self.diagnosis,
            "events": [event.to_dict() for event in self.events],
            "command_result": (
                self.command_result.to_dict()
                if self.command_result is not None
                else None
            ),
            "json_output_path": self.json_output_path,
            "exit_code": self.exit_code,
            "passed": self.passed,
            "summary_text": self.summary_text,
            "error_text": self.error_text,
        }


def run_daytona_real_smoke(
    *,
    allow_real_daytona: bool = False,
    env: Mapping[str, str] | None = None,
    sandbox_name: str | None = None,
    working_dir: str | None = None,
    worker_argv: Sequence[str] | None = None,
    sdk_importer: Callable[[str], object] | None = None,
    sdk_client_factory: Callable[[object, object], object] | None = None,
    json_output: str | Path | None = None,
) -> DaytonaRealSmokeResult:
    """Run one guarded real-Daytona smoke command and classify failures."""

    config = read_daytona_real_execution_config_from_env(env)
    readiness = validate_daytona_real_execution_readiness(config, env=env)
    effective_working_dir = working_dir or config.default_working_dir
    effective_argv = _worker_argv(worker_argv)
    events: list[DaytonaRealSmokeEvent] = []
    json_output_text = str(json_output) if json_output is not None else None

    if not allow_real_daytona:
        result = _result(
            allow_real_daytona=False,
            readiness=readiness,
            sandbox_name=sandbox_name,
            working_dir=effective_working_dir,
            worker_argv=effective_argv,
            diagnosis="blocked_missing_cli_allow",
            events=events,
            exit_code=2,
            error_text="real Daytona smoke requires --allow-real-daytona",
            json_output_path=json_output_text,
        )
        return _write_result_if_requested(result, json_output)
    if not readiness.passed:
        result = _result(
            allow_real_daytona=True,
            readiness=readiness,
            sandbox_name=sandbox_name,
            working_dir=effective_working_dir,
            worker_argv=effective_argv,
            diagnosis="blocked_readiness",
            events=events,
            exit_code=2,
            error_text=readiness.error_text,
            json_output_path=json_output_text,
        )
        return _write_result_if_requested(result, json_output)

    adapter = DaytonaSdkAdapter(
        DaytonaSdkAdapterConfig(
            real_execution_config=config,
            readiness=readiness,
            sdk_importer=sdk_importer,
            sdk_client_factory=sdk_client_factory,
        )
    )
    handle: DaytonaSandboxHandle | None = None
    command_result: DaytonaClientCommandResult | None = None
    diagnosis = "unknown_error"
    exit_code = 2
    error_text: str | None = None

    try:
        events.append(_event("open", "attempted", effective_working_dir))
        handle = adapter.open_sandbox(
            sandbox_name=sandbox_name,
            working_dir=effective_working_dir,
        )
        events.append(_event("open", "completed", handle.handle_id))
    except Exception as exc:  # noqa: BLE001 - diagnostic boundary.
        diagnosis = "sandbox_open_failed"
        error_text = f"{type(exc).__name__}: {exc}"
        events.append(_event("open", "error", error_text, error_text=error_text))
        result = _result(
            allow_real_daytona=True,
            readiness=readiness,
            sandbox_name=sandbox_name,
            working_dir=effective_working_dir,
            worker_argv=effective_argv,
            diagnosis=diagnosis,
            events=events,
            command_result=None,
            exit_code=2,
            error_text=error_text,
            json_output_path=json_output_text,
        )
        return _write_result_if_requested(result, json_output)

    try:
        command_operation = DaytonaCommandOperation(
            worker_argv=effective_argv,
            working_dir=effective_working_dir,
        )
        events.append(_event("command", "attempted", f"argv_count={len(effective_argv)}"))
        command_result = adapter.run_command(handle, command_operation)
        command_status = "completed" if command_result.exit_code == 0 else "error"
        events.append(
            _event(
                "command",
                command_status,
                command_result.summary_text,
                exit_code=command_result.exit_code,
                error_text=command_result.stderr if command_result.exit_code != 0 else None,
            )
        )
        if command_result.exit_code == 0:
            diagnosis = "smoke_passed"
            exit_code = 0
        else:
            diagnosis = "snapshot_command_failed"
            exit_code = command_result.exit_code
            error_text = command_result.stderr or command_result.summary_text
    except Exception as exc:  # noqa: BLE001 - diagnostic boundary.
        diagnosis = "command_transport_failed"
        exit_code = 2
        error_text = f"{type(exc).__name__}: {exc}"
        events.append(
            _event(
                "command",
                "error",
                error_text,
                exit_code=2,
                error_text=error_text,
            )
        )
    finally:
        try:
            events.append(_event("close", "attempted", handle.handle_id))
            adapter.close_sandbox(handle)
            events.append(_event("close", "completed", handle.handle_id))
        except Exception as exc:  # noqa: BLE001 - cleanup diagnostic.
            close_error = f"{type(exc).__name__}: {exc}"
            events.append(_event("close", "error", close_error, error_text=close_error))
            if exit_code == 0:
                diagnosis = "cleanup_failed"
                exit_code = 2
                error_text = close_error

    result = _result(
        allow_real_daytona=True,
        readiness=readiness,
        sandbox_name=sandbox_name,
        working_dir=effective_working_dir,
        worker_argv=effective_argv,
        diagnosis=diagnosis,
        events=events,
        command_result=command_result,
        exit_code=exit_code,
        error_text=error_text,
        json_output_path=json_output_text,
    )
    return _write_result_if_requested(result, json_output)


def main(argv: Sequence[str] | None = None) -> int:
    """Run a guarded real-Daytona smoke diagnostic from CLI args."""

    parser = argparse.ArgumentParser(
        description="Run a guarded real-Daytona smoke diagnostic.",
    )
    parser.add_argument(
        "--allow-real-daytona",
        action="store_true",
        help="Required explicit opt-in for real Daytona execution.",
    )
    parser.add_argument("--sandbox-name", help="Optional smoke sandbox name.")
    parser.add_argument("--working-dir", help="Override the configured working dir.")
    parser.add_argument(
        "--command",
        nargs="+",
        help="Override the default smoke command argv.",
    )
    parser.add_argument(
        "--json-output",
        help="Optional output path for the full smoke result JSON.",
    )
    args = parser.parse_args(argv)

    result = run_daytona_real_smoke(
        allow_real_daytona=args.allow_real_daytona,
        sandbox_name=args.sandbox_name,
        working_dir=args.working_dir,
        worker_argv=args.command,
        json_output=args.json_output,
    )
    _print_result(result, stdout=sys.stdout, stderr=sys.stderr)
    return result.exit_code


def _print_result(
    result: DaytonaRealSmokeResult,
    *,
    stdout: TextIO,
    stderr: TextIO,
) -> None:
    print(result.summary_text, file=stdout)
    print(result.readiness.summary_text, file=stdout)
    if result.command_result is not None:
        print(result.command_result.summary_text, file=stdout)
        if result.command_result.stdout:
            print(result.command_result.stdout.rstrip(), file=stdout)
        if result.command_result.stderr:
            print(result.command_result.stderr.rstrip(), file=stderr)
    if result.error_text is not None:
        print(result.error_text, file=stderr)


def _result(
    *,
    allow_real_daytona: bool,
    readiness: DaytonaRealExecutionReadiness,
    sandbox_name: str | None,
    working_dir: str,
    worker_argv: tuple[str, ...],
    diagnosis: str,
    events: list[DaytonaRealSmokeEvent],
    exit_code: int,
    error_text: str | None,
    command_result: DaytonaClientCommandResult | None = None,
    json_output_path: str | None = None,
) -> DaytonaRealSmokeResult:
    return DaytonaRealSmokeResult(
        allow_real_daytona=allow_real_daytona,
        readiness=readiness,
        sandbox_name=sandbox_name,
        working_dir=working_dir,
        worker_argv=worker_argv,
        diagnosis=diagnosis,
        events=tuple(events),
        command_result=command_result,
        json_output_path=json_output_path,
        exit_code=exit_code,
        summary_text=(
            "daytona_real_smoke="
            f"{'COMPLETE' if exit_code == 0 else 'ERROR'} "
            f"diagnosis={diagnosis} events={len(events)} exit_code={exit_code}"
        ),
        error_text=error_text,
    )


def _write_result_if_requested(
    result: DaytonaRealSmokeResult,
    json_output: str | Path | None,
) -> DaytonaRealSmokeResult:
    if json_output is None:
        return result
    output_path = Path(json_output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result.to_dict(), sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return DaytonaRealSmokeResult(
        allow_real_daytona=result.allow_real_daytona,
        readiness=result.readiness,
        sandbox_name=result.sandbox_name,
        working_dir=result.working_dir,
        worker_argv=result.worker_argv,
        diagnosis=result.diagnosis,
        events=result.events,
        command_result=result.command_result,
        json_output_path=str(output_path),
        exit_code=result.exit_code,
        summary_text=result.summary_text,
        error_text=result.error_text,
    )


def _worker_argv(value: Sequence[str] | None) -> tuple[str, ...]:
    if value is None:
        return DEFAULT_SMOKE_ARGV
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError("worker_argv must be a non-string sequence")
    result = tuple(value)
    _validate_string_tuple(result, "worker_argv")
    if not result:
        raise ValueError("worker_argv must contain at least one argument")
    return result


def _event(
    step: str,
    status: str,
    detail: str,
    *,
    exit_code: int | None = None,
    error_text: str | None = None,
) -> DaytonaRealSmokeEvent:
    return DaytonaRealSmokeEvent(
        step=step,
        status=status,
        detail=detail,
        exit_code=exit_code,
        error_text=error_text,
    )


def _validate_event_tuple(value: object, name: str) -> None:
    if not isinstance(value, tuple):
        raise ValueError(f"{name} must be a tuple")
    for index, item in enumerate(value):
        if not isinstance(item, DaytonaRealSmokeEvent):
            raise ValueError(f"{name}[{index}] must be a DaytonaRealSmokeEvent")


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
    "DEFAULT_SMOKE_ARGV",
    "DaytonaRealSmokeEvent",
    "DaytonaRealSmokeResult",
    "main",
    "run_daytona_real_smoke",
)
