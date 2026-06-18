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
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from scripts.build_submission import write_submission

from .experiment_suite import (
    default_manifest_paths,
    run_evaluation_suite,
)
from .parity import SubmissionParityConfig, run_submission_parity_check
from .regression_gate import RegressionGateConfig, run_regression_gate


CHECK_SUBMISSION_BUILD = "submission_build"
CHECK_SUBMISSION_PARITY = "submission_parity"
CHECK_REGRESSION_GATE = "regression_gate"
CHECK_EXPERIMENT_SUITE = "experiment_suite"


@dataclass(frozen=True, slots=True)
class SubmissionPreflightCheck:
    """One ordered preflight check record."""

    name: str
    passed: bool
    exit_code: int
    summary_text: str
    failure_reasons: tuple[str, ...] = ()

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

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "name": self.name,
            "passed": self.passed,
            "exit_code": self.exit_code,
            "summary_text": self.summary_text,
            "failure_reasons": list(self.failure_reasons),
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
    skip_parity: bool = False,
    skip_regression_gate: bool = False,
    skip_experiment_suite: bool = False,
) -> SubmissionPreflightResult:
    """Run the deterministic local submission-readiness checklist."""

    checks: list[SubmissionPreflightCheck] = []
    with tempfile.TemporaryDirectory(prefix="ow-submission-preflight-") as tmp:
        submission_path = Path(tmp) / "orbit_wars_submission.py"
        build_check = _submission_build_check(submission_path)
        checks.append(build_check)

        if skip_parity:
            checks.append(_skipped_check(CHECK_SUBMISSION_PARITY))
        elif build_check.passed:
            checks.append(_submission_parity_check(submission_path))
        else:
            checks.append(
                _failed_check(
                    CHECK_SUBMISSION_PARITY,
                    "submission build unavailable",
                )
            )

        checks.append(
            _skipped_check(CHECK_REGRESSION_GATE)
            if skip_regression_gate
            else _regression_gate_check(submission_path if build_check.passed else None)
        )
        checks.append(
            _skipped_check(CHECK_EXPERIMENT_SUITE)
            if skip_experiment_suite
            else _experiment_suite_check(
                manifest_paths=manifest_paths,
                suite_report_dir=suite_report_dir,
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
        skip_parity=args.skip_parity,
        skip_regression_gate=args.skip_regression_gate,
        skip_experiment_suite=args.skip_experiment_suite,
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


def _submission_parity_check(submission_path: Path) -> SubmissionPreflightCheck:
    try:
        config = RegressionGateConfig()
        parity_result = run_submission_parity_check(
            SubmissionParityConfig(
                matches=config.matches,
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
        )
    except Exception as exc:  # noqa: BLE001 - preflight records failures.
        return _exception_check(CHECK_SUBMISSION_PARITY, exc)


def _regression_gate_check(
    submission_path: Path | None,
) -> SubmissionPreflightCheck:
    try:
        gate_result = run_regression_gate(
            RegressionGateConfig(submission_path=submission_path)
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


def _validate_nonempty_string(value: object, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


__all__ = (
    "CHECK_EXPERIMENT_SUITE",
    "CHECK_REGRESSION_GATE",
    "CHECK_SUBMISSION_BUILD",
    "CHECK_SUBMISSION_PARITY",
    "SubmissionPreflightCheck",
    "SubmissionPreflightResult",
    "main",
    "run_submission_preflight",
)
