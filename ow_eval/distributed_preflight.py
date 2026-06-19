"""One-command distributed evaluation preflight.

Distributed Evaluation Cycle 24 composes local shard packaging, Daytona plan
generation, preflight validation, fake executor dry-runs, fake client-report
dry-runs, and guarded real-Daytona fail-closed validation. It does not call
Daytona, run real sandboxes, execute worker argv, submit to Kaggle, or run
matches.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .daytona_client_report_cli import run_daytona_client_report
from .daytona_executor_cli import run_daytona_shard_jobs
from .daytona_plan_cli import prepare_daytona_shard_job_plan
from .daytona_preflight import validate_daytona_shard_job_plan
from .daytona_real_cli import run_daytona_real_shard_jobs
from .shard_package_cli import prepare_evaluation_shard_package


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST_PATHS = (
    REPO_ROOT / "experiments" / "manifests" / "quick-2p-smoke.json",
    REPO_ROOT / "experiments" / "manifests" / "quick-4p-smoke.json",
)


@dataclass(frozen=True, slots=True)
class DistributedEvaluationPreflightConfig:
    """Configuration for one distributed evaluation preflight run."""

    manifest_paths: tuple[str, ...] = ()
    shard_count: int | None = 2
    matches_per_shard: int | None = None
    output_dir: str | None = None
    json_output_path: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.manifest_paths, tuple):
            raise ValueError("manifest_paths must be a tuple")
        for index, path in enumerate(self.manifest_paths):
            _validate_nonempty_string(path, f"manifest_paths[{index}]")
        _validate_optional_positive_int(self.shard_count, "shard_count")
        _validate_optional_positive_int(self.matches_per_shard, "matches_per_shard")
        if self.shard_count is not None and self.matches_per_shard is not None:
            raise ValueError("use shard_count or matches_per_shard, not both")
        if self.shard_count is None and self.matches_per_shard is None:
            raise ValueError("one sharding strategy is required")
        if self.output_dir is not None:
            _validate_nonempty_string(self.output_dir, "output_dir")
        if self.json_output_path is not None:
            _validate_nonempty_string(self.json_output_path, "json_output_path")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "manifest_paths": list(self.manifest_paths),
            "shard_count": self.shard_count,
            "matches_per_shard": self.matches_per_shard,
            "output_dir": self.output_dir,
            "json_output_path": self.json_output_path,
        }


@dataclass(frozen=True, slots=True)
class DistributedEvaluationPreflightStageResult:
    """One stage result in the distributed preflight workflow."""

    name: str
    passed: bool
    exit_code: int
    summary_text: str
    artifact_paths: tuple[str, ...] = ()
    error_text: str | None = None

    def __post_init__(self) -> None:
        _validate_nonempty_string(self.name, "name")
        if not isinstance(self.passed, bool):
            raise ValueError("passed must be a boolean")
        if isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int):
            raise ValueError("exit_code must be an integer")
        _validate_nonempty_string(self.summary_text, "summary_text")
        _validate_string_tuple(self.artifact_paths, "artifact_paths")
        if self.error_text is not None:
            _validate_nonempty_string(self.error_text, "error_text")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "name": self.name,
            "passed": self.passed,
            "exit_code": self.exit_code,
            "summary_text": self.summary_text,
            "artifact_paths": list(self.artifact_paths),
            "error_text": self.error_text,
        }


@dataclass(frozen=True, slots=True)
class DistributedEvaluationPreflightResult:
    """Structured result from one distributed evaluation preflight run."""

    config: DistributedEvaluationPreflightConfig
    output_dir: str
    stages: tuple[DistributedEvaluationPreflightStageResult, ...]
    json_output_path: str | None = None
    exit_code: int = 2
    summary_text: str = ""
    error_text: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.config, DistributedEvaluationPreflightConfig):
            raise ValueError("config must be a DistributedEvaluationPreflightConfig")
        _validate_nonempty_string(self.output_dir, "output_dir")
        if not isinstance(self.stages, tuple):
            raise ValueError("stages must be a tuple")
        for index, stage in enumerate(self.stages):
            if not isinstance(stage, DistributedEvaluationPreflightStageResult):
                raise ValueError(
                    f"stages[{index}] must be a DistributedEvaluationPreflightStageResult"
                )
        if self.json_output_path is not None:
            _validate_nonempty_string(self.json_output_path, "json_output_path")
        if isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int):
            raise ValueError("exit_code must be an integer")
        _validate_nonempty_string(self.summary_text, "summary_text")
        if self.error_text is not None:
            _validate_nonempty_string(self.error_text, "error_text")

    @property
    def passed(self) -> bool:
        """Return true when all preflight stages passed."""

        return self.exit_code == 0

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "config": self.config.to_dict(),
            "output_dir": self.output_dir,
            "stages": [stage.to_dict() for stage in self.stages],
            "json_output_path": self.json_output_path,
            "exit_code": self.exit_code,
            "passed": self.passed,
            "summary_text": self.summary_text,
            "error_text": self.error_text,
        }


def run_distributed_evaluation_preflight(
    manifest_paths: Sequence[str | Path] | None = None,
    *,
    shard_count: int | None = 2,
    matches_per_shard: int | None = None,
    output_dir: str | Path | None = None,
    json_output: str | Path | None = None,
) -> DistributedEvaluationPreflightResult:
    """Run the local distributed evaluation acceptance preflight."""

    manifest_path_texts = _manifest_paths(manifest_paths)
    output_dir_text = (
        str(Path(output_dir))
        if output_dir is not None
        else tempfile.mkdtemp(prefix="ow-distributed-preflight-")
    )
    json_output_text = str(json_output) if json_output is not None else None
    config = DistributedEvaluationPreflightConfig(
        manifest_paths=manifest_path_texts,
        shard_count=shard_count,
        matches_per_shard=matches_per_shard,
        output_dir=str(output_dir) if output_dir is not None else None,
        json_output_path=json_output_text,
    )
    stages: list[DistributedEvaluationPreflightStageResult] = []
    error_text: str | None = None

    try:
        output_root = Path(output_dir_text)
        output_root.mkdir(parents=True, exist_ok=True)

        package_result = prepare_evaluation_shard_package(
            manifest_path_texts,
            output_dir=output_root,
            shard_count=shard_count,
            matches_per_shard=matches_per_shard,
            label_prefix="distributed-preflight",
        )
        stages.append(
            _stage(
                "shard_package",
                package_result.exit_code == 0,
                package_result.exit_code,
                package_result.summary_text,
                (
                    (package_result.package_result.index_path,)
                    if package_result.package_result is not None
                    else ()
                ),
                package_result.error_text,
            )
        )
        if package_result.exit_code != 0 or package_result.package_result is None:
            raise RuntimeError(package_result.error_text or "shard package failed")

        daytona_plan_path = output_root / "daytona-shard-jobs.json"
        plan_result = prepare_daytona_shard_job_plan(
            package_result.package_result.index_path,
            output_path=daytona_plan_path,
        )
        stages.append(
            _stage(
                "daytona_plan",
                plan_result.exit_code == 0,
                plan_result.exit_code,
                plan_result.summary_text,
                (plan_result.output_path,) if plan_result.exit_code == 0 else (),
                plan_result.error_text,
            )
        )
        if plan_result.exit_code != 0:
            raise RuntimeError(plan_result.error_text or "Daytona plan failed")

        validation_result = validate_daytona_shard_job_plan(daytona_plan_path)
        stages.append(
            _stage(
                "daytona_preflight",
                validation_result.exit_code == 0,
                validation_result.exit_code,
                validation_result.summary_text,
                (str(daytona_plan_path),),
                validation_result.error_text,
            )
        )
        if validation_result.exit_code != 0:
            raise RuntimeError(validation_result.error_text or "Daytona preflight failed")

        executor_result = run_daytona_shard_jobs(
            daytona_plan_path,
            dry_run=True,
        )
        stages.append(
            _stage(
                "fake_executor_dry_run",
                executor_result.exit_code == 0,
                executor_result.exit_code,
                executor_result.summary_text,
                (str(daytona_plan_path),),
                executor_result.error_text,
            )
        )
        if executor_result.exit_code != 0:
            raise RuntimeError(executor_result.error_text or "fake executor failed")

        client_report_result = run_daytona_client_report(
            daytona_plan_path,
            dry_run=True,
        )
        stages.append(
            _stage(
                "fake_client_report_dry_run",
                client_report_result.exit_code == 0,
                client_report_result.exit_code,
                client_report_result.summary_text,
                (str(daytona_plan_path),),
                client_report_result.error_text,
            )
        )
        if client_report_result.exit_code != 0:
            raise RuntimeError(client_report_result.error_text or "fake client report failed")

        sys.modules.pop("daytona", None)
        real_result = run_daytona_real_shard_jobs(daytona_plan_path)
        real_stage_passed = (
            real_result.exit_code == 2
            and real_result.error_text is not None
            and "--allow-real-daytona" in real_result.error_text
            and "daytona" not in sys.modules
        )
        real_stage_error = None if real_stage_passed else (
            real_result.error_text or "real Daytona fail-closed check failed"
        )
        stages.append(
            _stage(
                "guarded_real_daytona_fail_closed",
                real_stage_passed,
                0 if real_stage_passed else 2,
                (
                    "distributed_preflight_real_daytona_fail_closed="
                    f"{'PASS' if real_stage_passed else 'ERROR'} "
                    f"blocked_exit_code={real_result.exit_code} "
                    f"daytona_imported={'daytona' in sys.modules}"
                ),
                (str(daytona_plan_path),),
                real_stage_error,
            )
        )
        if not real_stage_passed:
            raise RuntimeError(real_stage_error or "real Daytona fail-closed check failed")
    except Exception as exc:  # noqa: BLE001 - preflight returns structured errors.
        error_text = f"{type(exc).__name__}: {exc}"

    passed = error_text is None and all(stage.passed for stage in stages)
    result = DistributedEvaluationPreflightResult(
        config=config,
        output_dir=output_dir_text,
        stages=tuple(stages),
        json_output_path=json_output_text,
        exit_code=0 if passed else 2,
        summary_text=(
            "distributed_evaluation_preflight="
            f"{'PASS' if passed else 'ERROR'} "
            f"stages={len(stages)} output_dir={output_dir_text} "
            f"exit_code={0 if passed else 2}"
        ),
        error_text=error_text,
    )
    if json_output is not None:
        written_path = _write_json(result.to_dict(), json_output)
        result = DistributedEvaluationPreflightResult(
            config=result.config,
            output_dir=result.output_dir,
            stages=result.stages,
            json_output_path=str(written_path),
            exit_code=result.exit_code,
            summary_text=result.summary_text,
            error_text=result.error_text,
        )
    return result


def main(argv: Sequence[str] | None = None) -> int:
    """Run the distributed evaluation preflight from CLI arguments."""

    parser = argparse.ArgumentParser(
        description="Run the local distributed evaluation preflight.",
    )
    parser.add_argument(
        "manifests",
        nargs="*",
        help="Experiment manifest JSON paths. Defaults to smoke fixtures.",
    )
    strategy = parser.add_mutually_exclusive_group()
    strategy.add_argument(
        "--shard-count",
        type=int,
        default=2,
        help="Number of deterministic shards to plan.",
    )
    strategy.add_argument(
        "--matches-per-shard",
        type=int,
        help="Maximum number of matches in each deterministic shard.",
    )
    parser.add_argument(
        "--output-dir",
        help="Optional output directory. Defaults to a temporary directory.",
    )
    parser.add_argument(
        "--json-output",
        help="Optional output path for the full preflight result JSON.",
    )
    args = parser.parse_args(argv)

    shard_count = None if args.matches_per_shard is not None else args.shard_count
    result = run_distributed_evaluation_preflight(
        args.manifests or None,
        shard_count=shard_count,
        matches_per_shard=args.matches_per_shard,
        output_dir=args.output_dir,
        json_output=args.json_output,
    )
    print(result.summary_text)
    for stage in result.stages:
        print(stage.summary_text)
    if result.error_text is not None:
        print(result.error_text, file=sys.stderr)
    return result.exit_code


def _manifest_paths(
    manifest_paths: Sequence[str | Path] | None,
) -> tuple[str, ...]:
    paths = DEFAULT_MANIFEST_PATHS if manifest_paths is None else manifest_paths
    if isinstance(paths, (str, bytes)) or not isinstance(paths, Sequence):
        raise ValueError("manifest_paths must be a non-string sequence")
    if not paths:
        raise ValueError("manifest_paths must contain at least one path")
    result = []
    for index, path in enumerate(paths):
        if not isinstance(path, (str, Path)):
            raise ValueError(f"manifest_paths[{index}] must be a path")
        path_text = str(path)
        _validate_nonempty_string(path_text, f"manifest_paths[{index}]")
        result.append(path_text)
    return tuple(result)


def _stage(
    name: str,
    passed: bool,
    exit_code: int,
    summary_text: str,
    artifact_paths: tuple[str, ...],
    error_text: str | None,
) -> DistributedEvaluationPreflightStageResult:
    return DistributedEvaluationPreflightStageResult(
        name=name,
        passed=passed,
        exit_code=exit_code,
        summary_text=summary_text,
        artifact_paths=artifact_paths,
        error_text=error_text,
    )


def _write_json(payload: object, path: str | Path) -> Path:
    output_path = Path(str(path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_optional_positive_int(value: object, name: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer when provided")
    if value <= 0:
        raise ValueError(f"{name} must be positive")


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
    "DistributedEvaluationPreflightConfig",
    "DistributedEvaluationPreflightResult",
    "DistributedEvaluationPreflightStageResult",
    "main",
    "run_distributed_evaluation_preflight",
)
