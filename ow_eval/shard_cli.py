"""Sequential local multi-shard evaluation workflow.

Distributed Evaluation Cycle 4 composes shard planning, local single-shard
execution, optional shard-result persistence, and shard-result merge. It does
not add Daytona execution, parallelism, subprocess workers, or promotion gates.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .shard_merge import EvaluationShardMergeResult, merge_evaluation_shard_results
from .shard_persistence import write_evaluation_shard_run_result
from .shard_runner import EvaluationShardRunResult, run_evaluation_shard
from .sharding import (
    EvaluationShardPlan,
    ShardPlanConfig,
    build_evaluation_shard_plan,
)


@dataclass(frozen=True, slots=True)
class EvaluationShardCliResult:
    """Deterministic outcome from running a sequential local shard workflow."""

    manifest_paths: tuple[str, ...]
    shard_plan: EvaluationShardPlan | None = None
    shard_result_paths: tuple[str, ...] = ()
    shard_run_results: tuple[EvaluationShardRunResult, ...] = ()
    merged_result: EvaluationShardMergeResult | None = None
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
        if not isinstance(self.shard_result_paths, tuple):
            raise ValueError("shard_result_paths must be a tuple")
        for path in self.shard_result_paths:
            _validate_nonempty_string(path, "shard result path")
        if not isinstance(self.shard_run_results, tuple):
            raise ValueError("shard_run_results must be a tuple")
        for result in self.shard_run_results:
            if not isinstance(result, EvaluationShardRunResult):
                raise ValueError(
                    "shard_run_results entries must be EvaluationShardRunResult"
                )
        if self.merged_result is not None and not isinstance(
            self.merged_result,
            EvaluationShardMergeResult,
        ):
            raise ValueError("merged_result must be an EvaluationShardMergeResult")
        if isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int):
            raise ValueError("exit_code must be an integer")
        _validate_nonempty_string(self.summary_text, "summary_text")
        if self.error_text is not None:
            _validate_nonempty_string(self.error_text, "error_text")

    @property
    def passed(self) -> bool:
        """Return true when the shard workflow completed successfully."""

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
            "shard_result_paths": list(self.shard_result_paths),
            "shard_run_results": [
                result.to_dict()
                for result in self.shard_run_results
            ],
            "merged_result": (
                self.merged_result.to_dict()
                if self.merged_result is not None
                else None
            ),
            "exit_code": self.exit_code,
            "passed": self.passed,
            "summary_text": self.summary_text,
            "error_text": self.error_text,
        }


def run_evaluation_shards(
    manifest_paths: Sequence[str | Path],
    *,
    shard_count: int | None = None,
    matches_per_shard: int | None = None,
    output_dir: str | Path | None = None,
    command_python: str = ".venv/bin/python",
    label_prefix: str | None = "eval-shard",
) -> EvaluationShardCliResult:
    """Run a local manifest set through sequential shard execution."""

    try:
        manifest_path_texts = _manifest_path_texts(manifest_paths)
        output_root = Path(output_dir) if output_dir is not None else Path(
            "evaluation-shards"
        )
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

        shard_run_results = []
        shard_result_paths = []
        for shard in shard_plan.shards:
            shard_result = run_evaluation_shard(shard)
            shard_run_results.append(shard_result)
            if output_dir is not None:
                result_path = output_root / f"{shard.label}.shard-result.json"
                written_path = write_evaluation_shard_run_result(
                    shard_result,
                    result_path,
                )
                shard_result_paths.append(str(written_path))

        shard_run_result_tuple = tuple(shard_run_results)
        merged_result = merge_evaluation_shard_results(shard_run_result_tuple)
        return EvaluationShardCliResult(
            manifest_paths=manifest_path_texts,
            shard_plan=shard_plan,
            shard_result_paths=tuple(shard_result_paths),
            shard_run_results=shard_run_result_tuple,
            merged_result=merged_result,
            exit_code=0,
            summary_text=_summary_text(
                manifest_path_texts,
                shard_plan,
                merged_result,
                0,
                output_dir,
            ),
        )
    except Exception as exc:  # noqa: BLE001 - CLI boundary returns structured errors.
        error_text = f"{type(exc).__name__}: {exc}"
        return EvaluationShardCliResult(
            manifest_paths=(
                manifest_path_texts
                if "manifest_path_texts" in locals()
                else ()
            ),
            exit_code=2,
            summary_text=(
                "evaluation_shards=ERROR "
                f"manifests={len(manifest_path_texts) if 'manifest_path_texts' in locals() else 0} "
                "exit_code=2"
            ),
            error_text=error_text,
        )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the sequential local shard workflow from command-line arguments."""

    parser = argparse.ArgumentParser(
        description="Run local evaluation manifests through sequential shards.",
    )
    parser.add_argument(
        "manifests",
        nargs="+",
        help="Experiment manifest JSON paths.",
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
        "--output-dir",
        help="Optional directory for one shard-result JSON per shard.",
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

    result = run_evaluation_shards(
        args.manifests,
        shard_count=args.shard_count,
        matches_per_shard=args.matches_per_shard,
        output_dir=args.output_dir,
        command_python=args.command_python,
        label_prefix=args.label_prefix,
    )
    print(result.summary_text)
    for shard_result in result.shard_run_results:
        print(shard_result.summary_text)
    if result.merged_result is not None:
        print(result.merged_result.summary_text)
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
    merged_result: EvaluationShardMergeResult,
    exit_code: int,
    output_dir: str | Path | None,
) -> str:
    output_text = str(output_dir) if output_dir is not None else "none"
    summary = merged_result.batch_result.summary
    return (
        "evaluation_shards=PASS "
        f"manifests={len(manifest_paths)} shards={len(shard_plan.shards)} "
        f"matches={summary.total_matches} completed={summary.completed_count} "
        f"errors={summary.error_count} output_dir={output_text} "
        f"exit_code={exit_code}"
    )


def _validate_nonempty_string(value: object, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


__all__ = (
    "EvaluationShardCliResult",
    "main",
    "run_evaluation_shards",
)
