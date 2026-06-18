"""Run ordered local experiment manifest suites.

Evaluation Harness Cycle 18 composes existing single-manifest experiment
workflows. It does not add match-running logic, run at import time, or write
reports unless a report directory is explicitly supplied.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .experiment_cli import ExperimentCliResult, run_evaluation_experiment


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST_DIR = REPO_ROOT / "experiments" / "manifests"
DEFAULT_MANIFEST_FILENAMES = (
    "quick-2p-smoke.json",
    "quick-4p-smoke.json",
    "promotion-smoke.json",
)


@dataclass(frozen=True, slots=True)
class ExperimentSuiteResult:
    """Deterministic outcome from running an ordered manifest suite."""

    manifest_paths: tuple[str, ...]
    results: tuple[ExperimentCliResult, ...]
    report_dir: str | None = None
    exit_code: int = 2
    summary_text: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.manifest_paths, tuple):
            raise ValueError("manifest_paths must be a tuple")
        for path in self.manifest_paths:
            _validate_nonempty_string(path, "manifest path")
        if not isinstance(self.results, tuple):
            raise ValueError("results must be a tuple")
        for result in self.results:
            if not isinstance(result, ExperimentCliResult):
                raise ValueError("results entries must be ExperimentCliResult")
        if self.report_dir is not None:
            _validate_nonempty_string(self.report_dir, "report_dir")
        if isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int):
            raise ValueError("exit_code must be an integer")
        _validate_nonempty_string(self.summary_text, "summary_text")

    @property
    def passed(self) -> bool:
        """Return true when every child workflow exited successfully."""

        return self.exit_code == 0

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "manifest_paths": list(self.manifest_paths),
            "results": [
                result.to_dict()
                for result in self.results
            ],
            "report_dir": self.report_dir,
            "exit_code": self.exit_code,
            "passed": self.passed,
            "summary_text": self.summary_text,
        }


def default_manifest_paths() -> tuple[Path, ...]:
    """Return committed manifest fixtures in canonical suite order."""

    return tuple(
        DEFAULT_MANIFEST_DIR / filename
        for filename in DEFAULT_MANIFEST_FILENAMES
    )


def run_evaluation_suite(
    manifest_paths: Sequence[str | Path],
    *,
    report_dir: str | Path | None = None,
) -> ExperimentSuiteResult:
    """Run ``run_evaluation_experiment`` for each manifest path in order."""

    path_tuple = tuple(Path(path) for path in manifest_paths)
    report_dir_path = Path(report_dir) if report_dir is not None else None
    results = []

    for path in path_tuple:
        report_path = (
            report_dir_path / f"{path.stem}.report.json"
            if report_dir_path is not None
            else None
        )
        try:
            result = run_evaluation_experiment(path, report_path=report_path)
        except Exception as exc:  # noqa: BLE001 - suite boundary returns results.
            result = ExperimentCliResult(
                manifest_path=str(path),
                report_path=str(report_path) if report_path is not None else None,
                exit_code=2,
                summary_text=(
                    "experiment_workflow=ERROR "
                    f"manifest={path} exit_code=2"
                ),
                error_text=f"{type(exc).__name__}: {exc}",
            )
        results.append(result)

    result_tuple = tuple(results)
    exit_code = 0 if all(result.exit_code == 0 for result in result_tuple) else 1
    manifest_path_texts = tuple(str(path) for path in path_tuple)
    return ExperimentSuiteResult(
        manifest_paths=manifest_path_texts,
        results=result_tuple,
        report_dir=str(report_dir_path) if report_dir_path is not None else None,
        exit_code=exit_code,
        summary_text=_summary_text(manifest_path_texts, result_tuple, exit_code),
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run a local evaluation manifest suite from command-line arguments."""

    parser = argparse.ArgumentParser(
        description="Run a local evaluation experiment manifest suite.",
    )
    parser.add_argument(
        "manifests",
        nargs="*",
        help="Manifest JSON paths. Defaults to committed smoke fixtures.",
    )
    parser.add_argument(
        "--report-dir",
        help="Optional directory for one report JSON per manifest.",
    )
    args = parser.parse_args(argv)

    paths = tuple(args.manifests) if args.manifests else default_manifest_paths()
    result = run_evaluation_suite(paths, report_dir=args.report_dir)
    print(result.summary_text)
    for child in result.results:
        print(child.summary_text)
        if child.error_text is not None:
            print(child.error_text, file=sys.stderr)
    return result.exit_code


def _summary_text(
    manifest_paths: tuple[str, ...],
    results: tuple[ExperimentCliResult, ...],
    exit_code: int,
) -> str:
    total = len(results)
    passed_count = sum(1 for result in results if result.exit_code == 0)
    failed_count = total - passed_count
    failed_names = tuple(
        Path(path).stem
        for path, result in zip(manifest_paths, results)
        if result.exit_code != 0
    )
    failed_text = ",".join(failed_names) if failed_names else "none"
    status = "PASS" if exit_code == 0 else "FAIL"
    return (
        f"experiment_suite={status} total={total} passed={passed_count} "
        f"failed={failed_count} failed_manifests={failed_text} "
        f"exit_code={exit_code}"
    )


def _validate_nonempty_string(value: object, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


__all__ = (
    "DEFAULT_MANIFEST_FILENAMES",
    "ExperimentSuiteResult",
    "default_manifest_paths",
    "main",
    "run_evaluation_suite",
)
