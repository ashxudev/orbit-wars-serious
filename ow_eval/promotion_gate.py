"""In-memory promotion-gate decisions for experiment results.

Evaluation Harness Cycle 14 evaluates a completed ``ExperimentRunResult``
against its manifest's promotion thresholds. It does not run matches, write
files, submit to live Kaggle, or orchestrate distributed evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass

from .experiment_runner import ExperimentRunResult


@dataclass(frozen=True, slots=True)
class PromotionGateFailure:
    """One deterministic promotion-gate threshold failure."""

    code: str
    message: str
    observed: int | float | None
    threshold: int | float

    def __post_init__(self) -> None:
        _validate_nonempty_string(self.code, "code")
        _validate_nonempty_string(self.message, "message")
        if self.observed is not None:
            _validate_number(self.observed, "observed")
        _validate_number(self.threshold, "threshold")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "code": self.code,
            "message": self.message,
            "observed": self.observed,
            "threshold": self.threshold,
        }


@dataclass(frozen=True, slots=True)
class PromotionGateDecision:
    """Pass/fail promotion decision for one experiment run result."""

    passed: bool
    failures: tuple[PromotionGateFailure, ...] = ()
    summary_text: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.passed, bool):
            raise ValueError("passed must be a boolean")
        if not isinstance(self.failures, tuple):
            raise ValueError("failures must be a tuple")
        for failure in self.failures:
            if not isinstance(failure, PromotionGateFailure):
                raise ValueError("failures entries must be PromotionGateFailure")
        _validate_nonempty_string(self.summary_text, "summary_text")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "passed": self.passed,
            "failures": [
                failure.to_dict()
                for failure in self.failures
            ],
            "summary_text": self.summary_text,
        }


def evaluate_promotion_gate(
    run_result: ExperimentRunResult,
) -> PromotionGateDecision:
    """Evaluate ``run_result`` against manifest promotion thresholds."""

    if not isinstance(run_result, ExperimentRunResult):
        raise ValueError("run_result must be an ExperimentRunResult")

    thresholds = run_result.manifest.promotion_thresholds
    record = run_result.scoreboard_record
    failures: list[PromotionGateFailure] = []

    if thresholds.min_win_rate is not None:
        failures.extend(
            _minimum_threshold_failure(
                code="min_win_rate_not_met",
                field_name="win_rate",
                observed=record.win_rate,
                threshold=thresholds.min_win_rate,
            )
        )
    if thresholds.max_error_rate is not None:
        failures.extend(
            _maximum_threshold_failure(
                code="max_error_rate_exceeded",
                field_name="error_rate",
                observed=record.error_rate,
                threshold=thresholds.max_error_rate,
            )
        )
    if thresholds.max_mean_rank is not None:
        failures.extend(
            _maximum_threshold_failure(
                code="max_mean_rank_exceeded",
                field_name="mean_rank",
                observed=record.mean_rank,
                threshold=thresholds.max_mean_rank,
            )
        )
    if thresholds.min_completed_count is not None:
        failures.extend(
            _minimum_threshold_failure(
                code="min_completed_count_not_met",
                field_name="completed_count",
                observed=record.completed_count,
                threshold=thresholds.min_completed_count,
            )
        )

    failure_tuple = tuple(failures)
    passed = not failure_tuple
    return PromotionGateDecision(
        passed=passed,
        failures=failure_tuple,
        summary_text=_summary_text(run_result, passed, failure_tuple),
    )


def _minimum_threshold_failure(
    *,
    code: str,
    field_name: str,
    observed: int | float | None,
    threshold: int | float,
) -> tuple[PromotionGateFailure, ...]:
    if observed is None or float(observed) < float(threshold):
        return (
            PromotionGateFailure(
                code=code,
                message=(
                    f"{field_name} {_format_observed(observed)} below "
                    f"{_format_number(threshold)}"
                ),
                observed=observed,
                threshold=threshold,
            ),
        )
    return ()


def _maximum_threshold_failure(
    *,
    code: str,
    field_name: str,
    observed: int | float | None,
    threshold: int | float,
) -> tuple[PromotionGateFailure, ...]:
    if observed is None or float(observed) > float(threshold):
        return (
            PromotionGateFailure(
                code=code,
                message=(
                    f"{field_name} {_format_observed(observed)} exceeds "
                    f"{_format_number(threshold)}"
                ),
                observed=observed,
                threshold=threshold,
            ),
        )
    return ()


def _summary_text(
    run_result: ExperimentRunResult,
    passed: bool,
    failures: tuple[PromotionGateFailure, ...],
) -> str:
    status = "PASS" if passed else "FAIL"
    record = run_result.scoreboard_record
    return (
        f"promotion={status} experiment={run_result.manifest.name} "
        f"matches={record.match_count} completed={record.completed_count} "
        f"win_rate={_format_observed(record.win_rate)} "
        f"error_rate={_format_observed(record.error_rate)} "
        f"mean_rank={_format_observed(record.mean_rank)} "
        f"failures={len(failures)}"
    )


def _format_observed(value: int | float | None) -> str:
    if value is None:
        return "none"
    return _format_number(value)


def _format_number(value: int | float) -> str:
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    return f"{float(value):.6g}"


def _validate_nonempty_string(value: object, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


def _validate_number(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")


__all__ = (
    "PromotionGateDecision",
    "PromotionGateFailure",
    "evaluate_promotion_gate",
)
