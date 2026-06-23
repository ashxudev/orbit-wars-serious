"""Local submission-readiness preflight checks.

Evaluation Harness Cycle 19 composes existing local build, parity, regression
gate, and experiment-suite workflows into one deterministic checklist. It does
not submit to live Kaggle, add match-running logic, or write artifacts outside
temporary build output unless an explicit suite report directory is provided.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable

from scripts.build_submission import write_submission

from .experiment_suite import (
    default_manifest_paths,
    run_evaluation_suite,
)
from .parity import (
    SubmissionParityConfig,
    SubmissionParityResult,
    run_submission_parity_check,
)
from .regression_gate import RegressionGateConfig, run_regression_gate


CHECK_SUBMISSION_BUILD = "submission_build"
CHECK_SUBMISSION_PARITY = "submission_parity"
CHECK_REGRESSION_GATE = "regression_gate"
CHECK_EXPERIMENT_SUITE = "experiment_suite"
PREFLIGHT_LEVEL_FAST = "fast"
PREFLIGHT_LEVEL_STANDARD = "standard"
PREFLIGHT_LEVEL_FULL = "full"
PREFLIGHT_LEVELS = (
    PREFLIGHT_LEVEL_FAST,
    PREFLIGHT_LEVEL_STANDARD,
    PREFLIGHT_LEVEL_FULL,
)
ProgressCallback = Callable[[str, str, float | None], None]


@dataclass(frozen=True, slots=True)
class SubmissionPreflightCheck:
    """One ordered preflight check record."""

    name: str
    passed: bool
    exit_code: int
    summary_text: str
    failure_reasons: tuple[str, ...] = ()
    duration_seconds: float | None = None

    def __post_init__(self) -> None:
        _validate_nonempty_string(self.name, "name")
        if not isinstance(self.passed, bool):
            raise ValueError("passed must be a boolean")
        if isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int):
            raise ValueError("exit_code must be an integer")
        _validate_nonempty_string(self.summary_text, "summary_text")
        if not isinstance(self.failure_reasons, tuple):
            raise ValueError("failure_reasons must be a tuple")
        for reason in self.failure_reasons:
            _validate_nonempty_string(reason, "failure reason")
        if self.duration_seconds is not None:
            _validate_nonnegative_number(self.duration_seconds, "duration_seconds")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "name": self.name,
            "passed": self.passed,
            "exit_code": self.exit_code,
            "summary_text": self.summary_text,
            "failure_reasons": list(self.failure_reasons),
            "duration_seconds": self.duration_seconds,
        }


@dataclass(frozen=True, slots=True)
class SubmissionPreflightResult:
    """Deterministic local preflight result."""

    checks: tuple[SubmissionPreflightCheck, ...]
    passed: bool
    exit_code: int
    summary_text: str

    def __post_init__(self) -> None:
        if not isinstance(self.checks, tuple):
            raise ValueError("checks must be a tuple")
        for check in self.checks:
            if not isinstance(check, SubmissionPreflightCheck):
                raise ValueError("checks entries must be SubmissionPreflightCheck")
        if not isinstance(self.passed, bool):
            raise ValueError("passed must be a boolean")
        if isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int):
            raise ValueError("exit_code must be an integer")
        _validate_nonempty_string(self.summary_text, "summary_text")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "checks": [
                check.to_dict()
                for check in self.checks
            ],
            "passed": self.passed,
            "exit_code": self.exit_code,
            "summary_text": self.summary_text,
        }


def run_submission_preflight(
    *,
    manifest_paths: Sequence[str | Path] | None = None,
    suite_report_dir: str | Path | None = None,
    level: str = PREFLIGHT_LEVEL_STANDARD,
    skip_parity: bool = False,
    skip_regression_gate: bool = False,
    skip_experiment_suite: bool = False,
    progress_callback: ProgressCallback | None = None,
) -> SubmissionPreflightResult:
    """Run the deterministic local submission-readiness checklist."""

    _validate_preflight_level(level)
    checks: list[SubmissionPreflightCheck] = []
    with tempfile.TemporaryDirectory(prefix="ow-submission-preflight-") as tmp:
        submission_path = Path(tmp) / "orbit_wars_submission.py"
        build_check = _timed_check(
            CHECK_SUBMISSION_BUILD,
            lambda: _submission_build_check(submission_path),
            progress_callback=progress_callback,
        )
        checks.append(build_check)

        if build_check.passed:
            checks.extend(
                _run_expensive_checks(
                    submission_path=submission_path,
                    manifest_paths=manifest_paths,
                    suite_report_dir=suite_report_dir,
                    level=level,
                    skip_parity=skip_parity,
                    skip_regression_gate=skip_regression_gate,
                    skip_experiment_suite=skip_experiment_suite,
                    progress_callback=progress_callback,
                )
            )
        else:
            checks.extend(
                _checks_for_unavailable_submission(
                    level=level,
                    skip_parity=skip_parity,
                    skip_regression_gate=skip_regression_gate,
                    skip_experiment_suite=skip_experiment_suite,
                )
            )

    check_tuple = tuple(checks)
    passed = all(check.passed for check in check_tuple)
    exit_code = 0 if passed else 1
    return SubmissionPreflightResult(
        checks=check_tuple,
        passed=passed,
        exit_code=exit_code,
        summary_text=_summary_text(check_tuple, exit_code),
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the local submission-readiness preflight from CLI arguments."""

    parser = argparse.ArgumentParser(
        description="Run local submission-readiness preflight checks.",
    )
    parser.add_argument(
        "manifests",
        nargs="*",
        help="Manifest JSON paths for the experiment suite check.",
    )
    parser.add_argument(
        "--suite-report-dir",
        help="Optional directory for experiment suite report JSON files.",
    )
    parser.add_argument(
        "--level",
        choices=PREFLIGHT_LEVELS,
        default=PREFLIGHT_LEVEL_STANDARD,
        help=(
            "Preflight scope: fast=build plus one parity match; "
            "standard=build, parity, regression gate; "
            "full=standard plus experiment suite."
        ),
    )
    parser.add_argument(
        "--quiet-progress",
        action="store_true",
        help="Do not print per-check progress and timing lines to stderr.",
    )
    parser.add_argument(
        "--skip-parity",
        action="store_true",
        help="Skip generated-submission parity check.",
    )
    parser.add_argument(
        "--skip-regression-gate",
        action="store_true",
        help="Skip quick regression gate.",
    )
    parser.add_argument(
        "--skip-experiment-suite",
        action="store_true",
        help="Skip committed manifest experiment suite.",
    )
    args = parser.parse_args(argv)

    result = run_submission_preflight(
        manifest_paths=tuple(args.manifests) if args.manifests else None,
        suite_report_dir=args.suite_report_dir,
        level=args.level,
        skip_parity=args.skip_parity,
        skip_regression_gate=args.skip_regression_gate,
        skip_experiment_suite=args.skip_experiment_suite,
        progress_callback=None if args.quiet_progress else _print_progress,
    )
    print(result.summary_text)
    for check in result.checks:
        print(check.summary_text)
        for reason in check.failure_reasons:
            print(f"{check.name}: {reason}", file=sys.stderr)
    return result.exit_code


def _submission_build_check(submission_path: Path) -> SubmissionPreflightCheck:
    try:
        written_path = write_submission(submission_path)
        if not written_path.is_file():
            return _failed_check(CHECK_SUBMISSION_BUILD, "submission file was not written")
        return SubmissionPreflightCheck(
            name=CHECK_SUBMISSION_BUILD,
            passed=True,
            exit_code=0,
            summary_text=(
                f"preflight_check={CHECK_SUBMISSION_BUILD} status=PASS exit_code=0"
            ),
        )
    except Exception as exc:  # noqa: BLE001 - preflight records failures.
        return _exception_check(CHECK_SUBMISSION_BUILD, exc)


def _submission_parity_check(
    submission_path: Path,
    *,
    fast: bool = False,
) -> SubmissionPreflightCheck:
    return _submission_parity_attempt(submission_path, fast=fast)[0]


def _submission_parity_attempt(
    submission_path: Path,
    *,
    fast: bool = False,
) -> tuple[SubmissionPreflightCheck, SubmissionParityResult | None]:
    try:
        config = RegressionGateConfig()
        matches = config.matches[:1] if fast else config.matches
        parity_result = run_submission_parity_check(
            SubmissionParityConfig(
                matches=matches,
                submission_path=submission_path,
            )
        )
        reasons = ()
        if not parity_result.passed:
            reasons = _parity_failure_reasons(parity_result)
        return SubmissionPreflightCheck(
            name=CHECK_SUBMISSION_PARITY,
            passed=parity_result.passed,
            exit_code=0 if parity_result.passed else 1,
            summary_text=(
                f"preflight_check={CHECK_SUBMISSION_PARITY} "
                f"status={'PASS' if parity_result.passed else 'FAIL'} "
                f"mismatches={parity_result.mismatch_count} "
                f"exit_code={0 if parity_result.passed else 1}"
            ),
            failure_reasons=reasons,
        ), parity_result
    except Exception as exc:  # noqa: BLE001 - preflight records failures.
        return _exception_check(CHECK_SUBMISSION_PARITY, exc), None


def _regression_gate_check(
    submission_path: Path | None,
    *,
    parity_result=None,
) -> SubmissionPreflightCheck:
    try:
        gate_result = run_regression_gate(
            RegressionGateConfig(submission_path=submission_path),
            parity_result=parity_result,
        )
        reasons = tuple(
            f"{failure.code}: {failure.message}"
            for failure in gate_result.failures
        )
        return SubmissionPreflightCheck(
            name=CHECK_REGRESSION_GATE,
            passed=gate_result.passed,
            exit_code=0 if gate_result.passed else 1,
            summary_text=(
                f"preflight_check={CHECK_REGRESSION_GATE} "
                f"status={'PASS' if gate_result.passed else 'FAIL'} "
                f"failures={len(gate_result.failures)} "
                f"exit_code={0 if gate_result.passed else 1}"
            ),
            failure_reasons=reasons,
        )
    except Exception as exc:  # noqa: BLE001 - preflight records failures.
        return _exception_check(CHECK_REGRESSION_GATE, exc)


def _experiment_suite_check(
    *,
    manifest_paths: Sequence[str | Path] | None,
    suite_report_dir: str | Path | None,
) -> SubmissionPreflightCheck:
    try:
        paths = tuple(manifest_paths) if manifest_paths is not None else default_manifest_paths()
        suite_result = run_evaluation_suite(paths, report_dir=suite_report_dir)
        reasons = tuple(
            f"{Path(child.manifest_path).stem}: exit_code {child.exit_code}"
            for child in suite_result.results
            if child.exit_code != 0
        )
        return SubmissionPreflightCheck(
            name=CHECK_EXPERIMENT_SUITE,
            passed=suite_result.exit_code == 0,
            exit_code=suite_result.exit_code,
            summary_text=(
                f"preflight_check={CHECK_EXPERIMENT_SUITE} "
                f"status={'PASS' if suite_result.exit_code == 0 else 'FAIL'} "
                f"exit_code={suite_result.exit_code}"
            ),
            failure_reasons=reasons,
        )
    except Exception as exc:  # noqa: BLE001 - preflight records failures.
        return _exception_check(CHECK_EXPERIMENT_SUITE, exc)


def _run_expensive_checks(
    *,
    submission_path: Path,
    manifest_paths: Sequence[str | Path] | None,
    suite_report_dir: str | Path | None,
    level: str,
    skip_parity: bool,
    skip_regression_gate: bool,
    skip_experiment_suite: bool,
    progress_callback: ProgressCallback | None,
) -> tuple[SubmissionPreflightCheck, ...]:
    include_parity = level in (PREFLIGHT_LEVEL_FAST, PREFLIGHT_LEVEL_STANDARD, PREFLIGHT_LEVEL_FULL)
    include_gate = level in (PREFLIGHT_LEVEL_STANDARD, PREFLIGHT_LEVEL_FULL)
    include_suite = (
        level == PREFLIGHT_LEVEL_FULL
        or manifest_paths is not None
        or suite_report_dir is not None
    )

    def parity_and_gate() -> tuple[SubmissionPreflightCheck, ...]:
        checks: list[SubmissionPreflightCheck] = []
        precomputed_parity: SubmissionParityResult | None = None
        if include_parity:
            if skip_parity:
                checks.append(_skipped_check(CHECK_SUBMISSION_PARITY))
            else:
                parity_check, precomputed_parity = _timed_parity_attempt(
                    submission_path,
                    fast=level == PREFLIGHT_LEVEL_FAST,
                    progress_callback=progress_callback,
                )
                checks.append(parity_check)
        if include_gate:
            if skip_regression_gate:
                checks.append(_skipped_check(CHECK_REGRESSION_GATE))
            else:
                checks.append(
                    _timed_check(
                        CHECK_REGRESSION_GATE,
                        lambda: _regression_gate_check(
                            submission_path,
                            parity_result=precomputed_parity,
                        ),
                        progress_callback=progress_callback,
                    )
                )
        return tuple(checks)

    def suite() -> tuple[SubmissionPreflightCheck, ...]:
        if not include_suite:
            return ()
        if skip_experiment_suite:
            return (_skipped_check(CHECK_EXPERIMENT_SUITE),)
        return (
            _timed_check(
                CHECK_EXPERIMENT_SUITE,
                lambda: _experiment_suite_check(
                    manifest_paths=manifest_paths,
                    suite_report_dir=suite_report_dir,
                ),
                progress_callback=progress_callback,
            ),
        )

    if include_suite and include_gate:
        with ThreadPoolExecutor(max_workers=2) as executor:
            parity_and_gate_future = executor.submit(parity_and_gate)
            suite_future = executor.submit(suite)
            return parity_and_gate_future.result() + suite_future.result()
    return parity_and_gate() + suite()


def _checks_for_unavailable_submission(
    *,
    level: str,
    skip_parity: bool,
    skip_regression_gate: bool,
    skip_experiment_suite: bool,
) -> tuple[SubmissionPreflightCheck, ...]:
    checks: list[SubmissionPreflightCheck] = []
    if level in (PREFLIGHT_LEVEL_FAST, PREFLIGHT_LEVEL_STANDARD, PREFLIGHT_LEVEL_FULL):
        checks.append(
            _skipped_check(CHECK_SUBMISSION_PARITY)
            if skip_parity
            else _failed_check(CHECK_SUBMISSION_PARITY, "submission build unavailable")
        )
    if level in (PREFLIGHT_LEVEL_STANDARD, PREFLIGHT_LEVEL_FULL):
        checks.append(
            _skipped_check(CHECK_REGRESSION_GATE)
            if skip_regression_gate
            else _failed_check(CHECK_REGRESSION_GATE, "submission build unavailable")
        )
    if level == PREFLIGHT_LEVEL_FULL:
        checks.append(
            _skipped_check(CHECK_EXPERIMENT_SUITE)
            if skip_experiment_suite
            else _failed_check(CHECK_EXPERIMENT_SUITE, "submission build unavailable")
        )
    return tuple(checks)


def _timed_check(
    name: str,
    func: Callable[[], SubmissionPreflightCheck],
    *,
    progress_callback: ProgressCallback | None,
) -> SubmissionPreflightCheck:
    if progress_callback is not None:
        progress_callback("start", name, None)
    started = time.perf_counter()
    check = func()
    duration = time.perf_counter() - started
    timed_check = replace(check, duration_seconds=duration)
    if progress_callback is not None:
        progress_callback("done", name, duration)
    return timed_check


def _timed_parity_attempt(
    submission_path: Path,
    *,
    fast: bool,
    progress_callback: ProgressCallback | None,
) -> tuple[SubmissionPreflightCheck, SubmissionParityResult | None]:
    if progress_callback is not None:
        progress_callback("start", CHECK_SUBMISSION_PARITY, None)
    started = time.perf_counter()
    check, parity_result = _submission_parity_attempt(submission_path, fast=fast)
    duration = time.perf_counter() - started
    timed_check = replace(check, duration_seconds=duration)
    if progress_callback is not None:
        progress_callback("done", CHECK_SUBMISSION_PARITY, duration)
    return timed_check, parity_result


def _print_progress(event: str, name: str, duration_seconds: float | None) -> None:
    if event == "start":
        print(f"preflight_start check={name}", file=sys.stderr, flush=True)
        return
    duration = 0.0 if duration_seconds is None else duration_seconds
    print(
        f"preflight_done check={name} duration_s={duration:.3f}",
        file=sys.stderr,
        flush=True,
    )


def _parity_failure_reasons(parity_result: object) -> tuple[str, ...]:
    reasons: list[str] = []
    comparisons = getattr(parity_result, "comparisons", ())
    for comparison in comparisons:
        mismatch_reasons = getattr(comparison, "mismatch_reasons", ())
        if mismatch_reasons:
            reasons.append(
                f"match {comparison.index}: {', '.join(mismatch_reasons)}"
            )
    if not reasons:
        reasons.append("generated submission parity failed")
    return tuple(reasons)


def _skipped_check(name: str) -> SubmissionPreflightCheck:
    return SubmissionPreflightCheck(
        name=name,
        passed=True,
        exit_code=0,
        summary_text=f"preflight_check={name} status=SKIPPED exit_code=0",
    )


def _failed_check(name: str, reason: str) -> SubmissionPreflightCheck:
    return SubmissionPreflightCheck(
        name=name,
        passed=False,
        exit_code=1,
        summary_text=f"preflight_check={name} status=FAIL exit_code=1",
        failure_reasons=(reason,),
    )


def _exception_check(name: str, exc: Exception) -> SubmissionPreflightCheck:
    reason = f"{type(exc).__name__}: {exc}"
    return SubmissionPreflightCheck(
        name=name,
        passed=False,
        exit_code=2,
        summary_text=f"preflight_check={name} status=ERROR exit_code=2",
        failure_reasons=(reason,),
    )


def _summary_text(
    checks: tuple[SubmissionPreflightCheck, ...],
    exit_code: int,
) -> str:
    passed_count = sum(1 for check in checks if check.passed)
    failed_names = tuple(check.name for check in checks if not check.passed)
    failed_text = ",".join(failed_names) if failed_names else "none"
    status = "PASS" if exit_code == 0 else "FAIL"
    return (
        f"submission_preflight={status} total={len(checks)} "
        f"passed={passed_count} failed={len(checks) - passed_count} "
        f"failed_checks={failed_text} exit_code={exit_code}"
    )


def _validate_preflight_level(value: object) -> None:
    if value not in PREFLIGHT_LEVELS:
        raise ValueError(f"level must be one of {', '.join(PREFLIGHT_LEVELS)}")


def _validate_nonempty_string(value: object, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


def _validate_nonnegative_number(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ValueError(f"{name} must be a non-negative number")


__all__ = (
    "CHECK_EXPERIMENT_SUITE",
    "CHECK_REGRESSION_GATE",
    "CHECK_SUBMISSION_BUILD",
    "CHECK_SUBMISSION_PARITY",
    "PREFLIGHT_LEVEL_FAST",
    "PREFLIGHT_LEVEL_FULL",
    "PREFLIGHT_LEVEL_STANDARD",
    "PREFLIGHT_LEVELS",
    "SubmissionPreflightCheck",
    "SubmissionPreflightResult",
    "main",
    "run_submission_preflight",
)
