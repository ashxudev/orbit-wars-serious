"""Guarded Daytona runtime snapshot preparation.

This module prepares a clean tracked-source runtime context for Daytona and can
optionally create a remote Daytona snapshot behind the real-execution guard.
It does not run gauntlet matches.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import shlex
import shutil
import subprocess
import sys
import tarfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .daytona_real_config import (
    DEFAULT_DAYTONA_RUNTIME_SNAPSHOT_NAME_PREFIX,
    DaytonaRealExecutionReadiness,
    read_daytona_real_execution_config_from_env,
    validate_daytona_real_execution_readiness,
)


DEFAULT_SNAPSHOT_OUTPUT_DIR = "/tmp/ow-daytona-runtime-snapshot"
DEFAULT_SNAPSHOT_NAME_PREFIX = DEFAULT_DAYTONA_RUNTIME_SNAPSHOT_NAME_PREFIX
DEFAULT_PYTHON_VERSION = "3.12"
DEFAULT_REMOTE_WORKING_DIR = "/workspace/orbit-wars-serious"
DEFAULT_SNAPSHOT_CPU = 4
DEFAULT_SNAPSHOT_MEMORY = 8
DEFAULT_SNAPSHOT_DISK = 10
DAYTONA_RUNTIME_COMMIT_MARKER = ".ow-runtime-git-commit"


@dataclass(frozen=True, slots=True)
class DaytonaRuntimeSnapshotConfig:
    """Local config for a reproducible Daytona runtime snapshot context."""

    repo_root: str
    output_dir: str = DEFAULT_SNAPSHOT_OUTPUT_DIR
    snapshot_name: str | None = None
    snapshot_name_prefix: str = DEFAULT_SNAPSHOT_NAME_PREFIX
    remote_working_dir: str = DEFAULT_REMOTE_WORKING_DIR
    python_version: str = DEFAULT_PYTHON_VERSION
    cpu: int = DEFAULT_SNAPSHOT_CPU
    memory: int = DEFAULT_SNAPSHOT_MEMORY
    disk: int = DEFAULT_SNAPSHOT_DISK
    python_executable: str = sys.executable

    def __post_init__(self) -> None:
        _validate_nonempty_string(self.repo_root, "repo_root")
        _validate_nonempty_string(self.output_dir, "output_dir")
        if self.snapshot_name is not None:
            _validate_nonempty_string(self.snapshot_name, "snapshot_name")
        _validate_nonempty_string(self.snapshot_name_prefix, "snapshot_name_prefix")
        _validate_nonempty_string(self.remote_working_dir, "remote_working_dir")
        _validate_nonempty_string(self.python_version, "python_version")
        _validate_positive_int(self.cpu, "cpu")
        _validate_positive_int(self.memory, "memory")
        _validate_positive_int(self.disk, "disk")
        _validate_nonempty_string(self.python_executable, "python_executable")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "repo_root": self.repo_root,
            "output_dir": self.output_dir,
            "snapshot_name": self.snapshot_name,
            "snapshot_name_prefix": self.snapshot_name_prefix,
            "remote_working_dir": self.remote_working_dir,
            "python_version": self.python_version,
            "cpu": self.cpu,
            "memory": self.memory,
            "disk": self.disk,
            "python_executable": self.python_executable,
        }


@dataclass(frozen=True, slots=True)
class DaytonaRuntimeSnapshotPlan:
    """Prepared local runtime context for a future Daytona snapshot build."""

    config: DaytonaRuntimeSnapshotConfig
    git_commit: str
    snapshot_name: str
    source_dir: str
    requirements_path: str
    file_count: int
    requirement_count: int
    summary_text: str

    def __post_init__(self) -> None:
        if not isinstance(self.config, DaytonaRuntimeSnapshotConfig):
            raise ValueError("config must be a DaytonaRuntimeSnapshotConfig")
        _validate_nonempty_string(self.git_commit, "git_commit")
        _validate_nonempty_string(self.snapshot_name, "snapshot_name")
        _validate_nonempty_string(self.source_dir, "source_dir")
        _validate_nonempty_string(self.requirements_path, "requirements_path")
        _validate_positive_int(self.file_count, "file_count")
        _validate_positive_int(self.requirement_count, "requirement_count")
        _validate_nonempty_string(self.summary_text, "summary_text")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "config": self.config.to_dict(),
            "git_commit": self.git_commit,
            "snapshot_name": self.snapshot_name,
            "source_dir": self.source_dir,
            "requirements_path": self.requirements_path,
            "file_count": self.file_count,
            "requirement_count": self.requirement_count,
            "summary_text": self.summary_text,
        }


@dataclass(frozen=True, slots=True)
class DaytonaRuntimeSnapshotResult:
    """Structured result for the guarded runtime snapshot setup workflow."""

    plan: DaytonaRuntimeSnapshotPlan | None
    readiness: DaytonaRealExecutionReadiness
    allow_real_daytona: bool
    snapshot_created: bool = False
    snapshot_name: str | None = None
    exit_code: int = 2
    summary_text: str = ""
    error_text: str | None = None

    def __post_init__(self) -> None:
        if self.plan is not None and not isinstance(self.plan, DaytonaRuntimeSnapshotPlan):
            raise ValueError("plan must be a DaytonaRuntimeSnapshotPlan")
        if not isinstance(self.readiness, DaytonaRealExecutionReadiness):
            raise ValueError("readiness must be a DaytonaRealExecutionReadiness")
        if not isinstance(self.allow_real_daytona, bool):
            raise ValueError("allow_real_daytona must be a boolean")
        if not isinstance(self.snapshot_created, bool):
            raise ValueError("snapshot_created must be a boolean")
        if self.snapshot_name is not None:
            _validate_nonempty_string(self.snapshot_name, "snapshot_name")
        if isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int):
            raise ValueError("exit_code must be an integer")
        _validate_nonempty_string(self.summary_text, "summary_text")
        if self.error_text is not None:
            _validate_nonempty_string(self.error_text, "error_text")

    @property
    def passed(self) -> bool:
        """Return true when the setup workflow completed as requested."""

        return self.exit_code == 0

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "plan": self.plan.to_dict() if self.plan is not None else None,
            "readiness": self.readiness.to_dict(),
            "allow_real_daytona": self.allow_real_daytona,
            "snapshot_created": self.snapshot_created,
            "snapshot_name": self.snapshot_name,
            "exit_code": self.exit_code,
            "passed": self.passed,
            "summary_text": self.summary_text,
            "error_text": self.error_text,
        }


def prepare_daytona_runtime_snapshot_context(
    config: DaytonaRuntimeSnapshotConfig,
    *,
    requirements_lines: Sequence[str] | None = None,
) -> DaytonaRuntimeSnapshotPlan:
    """Materialize tracked source and requirements for a Daytona snapshot."""

    if not isinstance(config, DaytonaRuntimeSnapshotConfig):
        raise ValueError("config must be a DaytonaRuntimeSnapshotConfig")
    repo_root = Path(config.repo_root).resolve()
    if not repo_root.is_dir():
        raise ValueError(f"repo_root is not a directory: {repo_root}")

    git_commit = _git_output(repo_root, "rev-parse", "HEAD")
    snapshot_name = config.snapshot_name or (
        f"{config.snapshot_name_prefix}-{git_commit[:12]}"
    )
    output_root = Path(config.output_dir).resolve() / snapshot_name
    source_dir = output_root / "source"
    requirements_path = output_root / "requirements.txt"
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)
    source_dir.mkdir()

    _extract_git_archive(repo_root, source_dir)
    (source_dir / DAYTONA_RUNTIME_COMMIT_MARKER).write_text(
        git_commit + "\n",
        encoding="utf-8",
    )
    req_lines = tuple(requirements_lines) if requirements_lines is not None else _pip_freeze(config.python_executable)
    if not req_lines:
        raise ValueError("requirements must contain at least one line")
    requirements_path.write_text("\n".join(req_lines) + "\n", encoding="utf-8")
    file_count = sum(1 for path in source_dir.rglob("*") if path.is_file())
    if file_count <= 0:
        raise ValueError("tracked source archive did not contain files")
    return DaytonaRuntimeSnapshotPlan(
        config=config,
        git_commit=git_commit,
        snapshot_name=snapshot_name,
        source_dir=str(source_dir),
        requirements_path=str(requirements_path),
        file_count=file_count,
        requirement_count=len(req_lines),
        summary_text=(
            "daytona_runtime_snapshot_context=READY "
            f"snapshot_name={snapshot_name} files={file_count} "
            f"requirements={len(req_lines)} source_dir={source_dir}"
        ),
    )


def prepare_daytona_runtime_snapshot(
    config: DaytonaRuntimeSnapshotConfig,
    *,
    allow_real_daytona: bool = False,
    env: Mapping[str, str] | None = None,
    requirements_lines: Sequence[str] | None = None,
    snapshot_creator: Callable[[DaytonaRuntimeSnapshotPlan, object], str] | None = None,
) -> DaytonaRuntimeSnapshotResult:
    """Prepare context and optionally create a guarded remote Daytona snapshot."""

    try:
        plan = prepare_daytona_runtime_snapshot_context(
            config,
            requirements_lines=requirements_lines,
        )
        real_config = read_daytona_real_execution_config_from_env(env)
        readiness = validate_daytona_real_execution_readiness(real_config, env=env)
        if not allow_real_daytona:
            return DaytonaRuntimeSnapshotResult(
                plan=plan,
                readiness=readiness,
                allow_real_daytona=False,
                snapshot_created=False,
                snapshot_name=plan.snapshot_name,
                exit_code=0,
                summary_text=_summary_text(plan, False, False, 0),
                error_text=None,
            )
        if not readiness.passed:
            return DaytonaRuntimeSnapshotResult(
                plan=plan,
                readiness=readiness,
                allow_real_daytona=True,
                snapshot_created=False,
                snapshot_name=plan.snapshot_name,
                exit_code=2,
                summary_text=_summary_text(plan, True, False, 2),
                error_text=readiness.error_text,
            )
        snapshot_name = _create_snapshot(plan, real_config, env, snapshot_creator)
        return DaytonaRuntimeSnapshotResult(
            plan=plan,
            readiness=readiness,
            allow_real_daytona=True,
            snapshot_created=True,
            snapshot_name=snapshot_name,
            exit_code=0,
            summary_text=_summary_text(plan, True, True, 0),
        )
    except Exception as exc:  # noqa: BLE001 - CLI/API boundary returns errors.
        fallback_readiness = validate_daytona_real_execution_readiness(env=env)
        return DaytonaRuntimeSnapshotResult(
            plan=None,
            readiness=fallback_readiness,
            allow_real_daytona=allow_real_daytona,
            exit_code=2,
            summary_text=(
                "daytona_runtime_snapshot=ERROR "
                f"allow_real_daytona={allow_real_daytona} "
                "snapshot_created=False exit_code=2"
            ),
            error_text=f"{type(exc).__name__}: {exc}",
        )


def main(argv: Sequence[str] | None = None) -> int:
    """Prepare or create a Daytona runtime snapshot from command-line args."""

    parser = argparse.ArgumentParser(
        description="Prepare a clean Daytona runtime snapshot context.",
    )
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Repository root to archive from committed tracked files.",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_SNAPSHOT_OUTPUT_DIR,
        help="Local output directory for generated snapshot context.",
    )
    parser.add_argument("--snapshot-name", help="Explicit Daytona snapshot name.")
    parser.add_argument(
        "--snapshot-name-prefix",
        default=DEFAULT_SNAPSHOT_NAME_PREFIX,
        help="Snapshot name prefix when --snapshot-name is omitted.",
    )
    parser.add_argument(
        "--remote-working-dir",
        default=DEFAULT_REMOTE_WORKING_DIR,
        help="Repository path inside the Daytona snapshot.",
    )
    parser.add_argument(
        "--python-version",
        default=DEFAULT_PYTHON_VERSION,
        help="Python version for the Daytona debian_slim image.",
    )
    parser.add_argument("--cpu", type=int, default=DEFAULT_SNAPSHOT_CPU)
    parser.add_argument("--memory", type=int, default=DEFAULT_SNAPSHOT_MEMORY)
    parser.add_argument("--disk", type=int, default=DEFAULT_SNAPSHOT_DISK)
    parser.add_argument(
        "--allow-real-daytona",
        action="store_true",
        help="Actually create the remote Daytona snapshot after readiness passes.",
    )
    parser.add_argument("--json-output", help="Optional result JSON path.")
    args = parser.parse_args(argv)

    result = prepare_daytona_runtime_snapshot(
        DaytonaRuntimeSnapshotConfig(
            repo_root=args.repo_root,
            output_dir=args.output_dir,
            snapshot_name=args.snapshot_name,
            snapshot_name_prefix=args.snapshot_name_prefix,
            remote_working_dir=args.remote_working_dir,
            python_version=args.python_version,
            cpu=args.cpu,
            memory=args.memory,
            disk=args.disk,
        ),
        allow_real_daytona=args.allow_real_daytona,
    )
    print(result.summary_text)
    if result.plan is not None:
        print(result.plan.summary_text)
    if result.error_text is not None:
        print(result.error_text, file=sys.stderr)
    if args.json_output:
        _write_json(result.to_dict(), args.json_output)
    return result.exit_code


def _create_snapshot(
    plan: DaytonaRuntimeSnapshotPlan,
    real_config,
    env: Mapping[str, str] | None,
    snapshot_creator: Callable[[DaytonaRuntimeSnapshotPlan, object], str] | None,
) -> str:
    if snapshot_creator is not None:
        return snapshot_creator(plan, real_config)
    from daytona import (  # noqa: PLC0415 - imported only after readiness passes.
        CreateSnapshotParams,
        Daytona,
        DaytonaConfig,
        Image,
        Resources,
    )

    api_key = _required_env_value(real_config.api_key_env_var, env)
    daytona = Daytona(
        DaytonaConfig(
            api_key=api_key,
            api_url=real_config.api_url,
            target=real_config.target,
        )
    )
    remote_working_dir = shlex.quote(plan.config.remote_working_dir)
    image = (
        Image.debian_slim(plan.config.python_version)
        .add_local_dir(plan.source_dir, plan.config.remote_working_dir)
        .add_local_file(plan.requirements_path, "/tmp/ow-daytona-runtime-requirements.txt")
        .run_commands(
            f"cd {remote_working_dir} && python -m venv .venv",
            (
                f"{remote_working_dir}/.venv/bin/python "
                "-m pip install --upgrade pip"
            ),
            (
                f"{remote_working_dir}/.venv/bin/python "
                "-m pip install -r /tmp/ow-daytona-runtime-requirements.txt"
            ),
            (
                f"cd {remote_working_dir} && "
                ".venv/bin/python -c \"import ow_eval, agents.orbit_wars_agent; "
                "print('orbit-wars-runtime-ok')\""
            ),
        )
    )
    snapshot = daytona.snapshot.create(
        CreateSnapshotParams(
            name=plan.snapshot_name,
            image=image,
            resources=Resources(
                cpu=plan.config.cpu,
                memory=plan.config.memory,
                disk=plan.config.disk,
            ),
        ),
        timeout=0,
    )
    return str(getattr(snapshot, "name", plan.snapshot_name))


def _extract_git_archive(repo_root: Path, source_dir: Path) -> None:
    completed = subprocess.run(
        ("git", "archive", "--format=tar", "HEAD"),
        cwd=repo_root,
        check=True,
        capture_output=True,
    )
    with tarfile.open(fileobj=io.BytesIO(completed.stdout), mode="r:") as archive:
        archive.extractall(source_dir, filter="data")


def _pip_freeze(python_executable: str) -> tuple[str, ...]:
    completed = subprocess.run(
        (python_executable, "-m", "pip", "freeze"),
        check=True,
        capture_output=True,
        text=True,
    )
    return tuple(
        line.strip()
        for line in completed.stdout.splitlines()
        if line.strip() and not line.startswith("#")
    )


def _git_output(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _required_env_value(name: str | None, env: Mapping[str, str] | None) -> str:
    if name is None:
        raise ValueError("api_key_env_var is required")

    effective_env = os.environ if env is None else env
    value = effective_env.get(name)
    if value is None or not value.strip():
        raise ValueError(f"missing required env var: {name}")
    return value


def _summary_text(
    plan: DaytonaRuntimeSnapshotPlan,
    allow_real_daytona: bool,
    snapshot_created: bool,
    exit_code: int,
) -> str:
    status = "COMPLETE" if exit_code == 0 else "ERROR"
    return (
        f"daytona_runtime_snapshot={status} "
        f"snapshot_name={plan.snapshot_name} "
        f"allow_real_daytona={allow_real_daytona} "
        f"snapshot_created={snapshot_created} "
        f"exit_code={exit_code}"
    )


def _write_json(payload: object, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_nonempty_string(value: object, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


def _validate_positive_int(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


__all__ = (
    "DAYTONA_RUNTIME_COMMIT_MARKER",
    "DaytonaRuntimeSnapshotConfig",
    "DaytonaRuntimeSnapshotPlan",
    "DaytonaRuntimeSnapshotResult",
    "prepare_daytona_runtime_snapshot",
    "prepare_daytona_runtime_snapshot_context",
    "main",
)
