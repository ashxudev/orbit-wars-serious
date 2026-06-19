"""Prepare deterministic shard job packages from experiment manifests.

Distributed Evaluation Cycle 7 builds shard plans and writes portable shard job
packages without running matches, executing commands, spawning workers, or
calling Daytona.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .shard_jobs import (
    EvaluationShardJobPackageResult,
    write_evaluation_shard_job_package,
)
from .sharding import (
    EvaluationShardPlan,
    ShardPlanConfig,
    build_evaluation_shard_plan,
)


@dataclass(frozen=True, slots=True)
class EvaluationShardPackageCliResult:
    """Outcome from preparing a local shard job package."""

    manifest_paths: tuple[str, ...]
    shard_plan: EvaluationShardPlan | None = None
    package_result: EvaluationShardJobPackageResult | None = None
    exit_code: int = 2
    summary_text: str = ""
    error_text: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.manifest_paths, tuple):
            raise ValueError("manifest_paths must be a tuple")
        for path in self.manifest_paths:
            _validate_nonempty_string(path, "manifest path")
        if self.shard_plan is not None and not isinstance(
            self.shard_plan,
            EvaluationShardPlan,
        ):
            raise ValueError("shard_plan must be an EvaluationShardPlan")
        if self.package_result is not None and not isinstance(
            self.package_result,
            EvaluationShardJobPackageResult,
        ):
            raise ValueError(
                "package_result must be an EvaluationShardJobPackageResult"
            )
        if isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int):
            raise ValueError("exit_code must be an integer")
        _validate_nonempty_string(self.summary_text, "summary_text")
        if self.error_text is not None:
            _validate_nonempty_string(self.error_text, "error_text")

    @property
    def passed(self) -> bool:
        """Return true when package preparation completed successfully."""

        return self.exit_code == 0

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "manifest_paths": list(self.manifest_paths),
            "shard_plan": (
                self.shard_plan.to_dict()
                if self.shard_plan is not None
                else None
            ),
            "package_result": (
                self.package_result.to_dict()
                if self.package_result is not None
                else None
            ),
            "exit_code": self.exit_code,
            "passed": self.passed,
            "summary_text": self.summary_text,
            "error_text": self.error_text,
        }


def prepare_evaluation_shard_package(
    manifest_paths: Sequence[str | Path],
    *,
    output_dir: str | Path | None = None,
    shard_count: int | None = None,
    matches_per_shard: int | None = None,
    index_path: str | Path | None = None,
    materialize_manifests: bool = True,
    command_python: str = ".venv/bin/python",
    label_prefix: str | None = "eval-shard",
) -> EvaluationShardPackageCliResult:
    """Prepare a deterministic shard job package without executing jobs."""

    try:
        manifest_path_texts = _manifest_path_texts(manifest_paths)
        if output_dir is None:
            raise ValueError("output_dir is required")
        output_root = Path(output_dir)
        shard_plan = build_evaluation_shard_plan(
            tuple(Path(path) for path in manifest_path_texts),
            ShardPlanConfig(
                shard_count=shard_count,
                matches_per_shard=matches_per_shard,
                output_root=output_root,
                command_python=command_python,
                label_prefix=label_prefix,
            ),
        )
        package_result = write_evaluation_shard_job_package(
            shard_plan,
            index_path=index_path,
            materialize_manifests=materialize_manifests,
        )
        return EvaluationShardPackageCliResult(
            manifest_paths=manifest_path_texts,
            shard_plan=shard_plan,
            package_result=package_result,
            exit_code=0,
            summary_text=_summary_text(
                manifest_path_texts,
                shard_plan,
                package_result,
                output_root,
                0,
            ),
        )
    except Exception as exc:  # noqa: BLE001 - CLI boundary returns structured errors.
        error_text = f"{type(exc).__name__}: {exc}"
        return EvaluationShardPackageCliResult(
            manifest_paths=(
                manifest_path_texts
                if "manifest_path_texts" in locals()
                else ()
            ),
            exit_code=2,
            summary_text=(
                "evaluation_shard_package=ERROR "
                f"manifests={len(manifest_path_texts) if 'manifest_path_texts' in locals() else 0} "
                "exit_code=2"
            ),
            error_text=error_text,
        )


def main(argv: Sequence[str] | None = None) -> int:
    """Prepare shard jobs from command-line arguments."""

    parser = argparse.ArgumentParser(
        description="Prepare local evaluation shard job package files.",
    )
    parser.add_argument(
        "manifests",
        nargs="+",
        help="Experiment manifest JSON paths.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Required output directory for shard manifests, jobs, and index.",
    )
    strategy = parser.add_mutually_exclusive_group(required=True)
    strategy.add_argument(
        "--shard-count",
        type=int,
        help="Number of deterministic shards to plan.",
    )
    strategy.add_argument(
        "--matches-per-shard",
        type=int,
        help="Maximum number of matches in each deterministic shard.",
    )
    parser.add_argument(
        "--index-path",
        help="Optional explicit shard job index JSON path.",
    )
    parser.add_argument(
        "--no-materialize-manifests",
        action="store_true",
        help="Write job/index files without writing shard manifest files.",
    )
    parser.add_argument(
        "--command-python",
        default=".venv/bin/python",
        help="Python command to include in suggested shard commands.",
    )
    parser.add_argument(
        "--label-prefix",
        default="eval-shard",
        help="Prefix for deterministic shard labels.",
    )
    args = parser.parse_args(argv)

    result = prepare_evaluation_shard_package(
        args.manifests,
        output_dir=args.output_dir,
        shard_count=args.shard_count,
        matches_per_shard=args.matches_per_shard,
        index_path=args.index_path,
        materialize_manifests=not args.no_materialize_manifests,
        command_python=args.command_python,
        label_prefix=args.label_prefix,
    )
    print(result.summary_text)
    if result.package_result is not None:
        print(result.package_result.summary_text)
        for job in result.package_result.jobs:
            print(
                f"job_id={job.job_id} label={job.label} "
                f"job_path={job.job_path} manifest_path={job.manifest_path} "
                f"result_path={job.shard_result_path} command={job.command}"
            )
    if result.error_text is not None:
        print(result.error_text, file=sys.stderr)
    return result.exit_code


def _manifest_path_texts(
    manifest_paths: Sequence[str | Path],
) -> tuple[str, ...]:
    if isinstance(manifest_paths, (str, bytes)) or not isinstance(
        manifest_paths,
        Sequence,
    ):
        raise ValueError("manifest_paths must be a non-string sequence")
    if not manifest_paths:
        raise ValueError("manifest_paths must contain at least one path")
    result = []
    for index, path in enumerate(manifest_paths):
        if not isinstance(path, (str, Path)):
            raise ValueError(f"manifest_paths[{index}] must be a path")
        path_text = str(path)
        _validate_nonempty_string(path_text, f"manifest_paths[{index}]")
        result.append(path_text)
    return tuple(result)


def _summary_text(
    manifest_paths: tuple[str, ...],
    shard_plan: EvaluationShardPlan,
    package_result: EvaluationShardJobPackageResult,
    output_dir: Path,
    exit_code: int,
) -> str:
    return (
        "evaluation_shard_package=PASS "
        f"manifests={len(manifest_paths)} shards={len(shard_plan.shards)} "
        f"jobs={len(package_result.jobs)} output_dir={output_dir} "
        f"index_path={package_result.index_path} exit_code={exit_code}"
    )


def _validate_nonempty_string(value: object, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


__all__ = (
    "EvaluationShardPackageCliResult",
    "main",
    "prepare_evaluation_shard_package",
)
