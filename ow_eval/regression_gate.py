"""Canonical quick local regression gate for evaluation harness smoke checks.

Evaluation Harness Cycle 10 composes existing local evaluation APIs into a
deterministic pre-promotion gate. It runs a small official-environment baseline
batch, validates generated-submission parity, summarizes with triage and
scoreboard records, and reports structured failures. It does not submit to live
Kaggle or write artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .baselines import BaselineName, builtin_baseline_spec
from .batch_runner import (
    EvaluationBatchConfig,
    EvaluationBatchResult,
    run_evaluation_batch,
)
from .contracts import EvaluationStatus, MatchConfig, OpponentSpec, PlayerCount
from .parity import (
    SubmissionParityConfig,
    SubmissionParityResult,
    run_submission_parity_check,
)
from .scoreboard import ScoreboardRecord, build_scoreboard_record
from .triage import FailureCategory, FailureTriageReport, triage_evaluation_batch


SEVERE_TRIAGE_CATEGORIES = (
    FailureCategory.PARSE_CRASH,
    FailureCategory.PLANNER_CRASH,
    FailureCategory.ACTION_CONVERSION_CRASH,
    FailureCategory.TIMEOUT_OR_BUDGET_FALLBACK,
    FailureCategory.INVALID_OR_NOOP_HEAVY_BEHAVIOR,
    FailureCategory.OTHER_FAILURE,
)


@dataclass(frozen=True, slots=True)
class RegressionGateConfig:
    """Configuration for the quick local regression gate."""

    matches: tuple[MatchConfig, ...] = field(
        default_factory=lambda: _default_gate_matches()
    )
    max_error_rate: float = 0.0
    max_mean_rank: float = 2.0
    min_win_rate: float = 0.0
    agent_name: str = "candidate-nearest-neutral"
    agent_version: str | None = None
    commit: str | None = None
    scenario_set: str = "quick-2p-seeds-7-8"
    submission_path: str | Path | None = None
    notes: tuple[str, ...] = ()
    metadata: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.matches, tuple):
            raise ValueError("matches must be a tuple")
        for match in self.matches:
            if not isinstance(match, MatchConfig):
                raise ValueError("matches entries must be MatchConfig objects")
        _validate_rate(self.max_error_rate, "max_error_rate")
        _validate_nonnegative_number(self.max_mean_rank, "max_mean_rank")
        _validate_rate(self.min_win_rate, "min_win_rate")
        _validate_nonempty_string(self.agent_name, "agent_name")
        _validate_nonempty_string(self.scenario_set, "scenario_set")
        if self.agent_version is not None:
            _validate_nonempty_string(self.agent_version, "agent_version")
        if self.commit is not None:
            _validate_nonempty_string(self.commit, "commit")
        if self.submission_path is not None and not isinstance(
            self.submission_path,
            (str, Path),
        ):
            raise ValueError("submission_path must be a path")
        _validate_string_tuple(self.notes, "notes")
        _validate_metadata(self.metadata)

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic plain dictionary representation."""

        return {
            "matches": [
                match.to_dict()
                for match in self.matches
            ],
            "max_error_rate": self.max_error_rate,
            "max_mean_rank": self.max_mean_rank,
            "min_win_rate": self.min_win_rate,
            "agent_name": self.agent_name,
            "agent_version": self.agent_version,
            "commit": self.commit,
            "scenario_set": self.scenario_set,
            "submission_path": (
                str(self.submission_path)
                if self.submission_path is not None
                else None
            ),
            "notes": list(self.notes),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class RegressionGateFailure:
    """One deterministic gate failure reason."""

    code: str
    message: str
    match_index: int | None = None
    status: str | None = None
    category: str | None = None

    def __post_init__(self) -> None:
        _validate_nonempty_string(self.code, "code")
        _validate_nonempty_string(self.message, "message")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic plain dictionary representation."""

        return {
            "code": self.code,
            "message": self.message,
            "match_index": self.match_index,
            "status": self.status,
            "category": self.category,
        }


@dataclass(frozen=True, slots=True)
class RegressionGateResult:
    """Structured result from one quick regression gate run."""

    passed: bool
    failures: tuple[RegressionGateFailure, ...] = ()
    scoreboard_record: ScoreboardRecord | None = None
    triage_report: FailureTriageReport | None = None
    parity_result: SubmissionParityResult | None = None
    summary_text: str = ""

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic plain dictionary representation."""

        return {
            "passed": self.passed,
            "failures": [
                failure.to_dict()
                for failure in self.failures
            ],
            "scoreboard_record": (
                self.scoreboard_record.to_dict()
                if self.scoreboard_record is not None
                else None
            ),
            "triage_report": (
                self.triage_report.to_dict()
                if self.triage_report is not None
                else None
            ),
            "parity_result": _parity_result_to_dict(self.parity_result),
            "summary_text": self.summary_text,
        }


def run_regression_gate(
    config: RegressionGateConfig | None = None,
) -> RegressionGateResult:
    """Run the deterministic quick local regression gate."""

    effective_config = RegressionGateConfig() if config is None else config
    if not effective_config.matches:
        failure = RegressionGateFailure(
            code="empty_scenario_set",
            message="no matches configured",
        )
        return RegressionGateResult(
            passed=False,
            failures=(failure,),
            summary_text=_summary_text(False, None, (failure,), None),
        )

    try:
        candidate_batch = run_evaluation_batch(
            EvaluationBatchConfig(matches=effective_config.matches)
        )
        parity_result = run_submission_parity_check(
            SubmissionParityConfig(
                matches=effective_config.matches,
                submission_path=effective_config.submission_path,
            )
        )
    except Exception as exc:
        failure = RegressionGateFailure(
            code="gate_execution_error",
            message=_error_text(exc),
        )
        return RegressionGateResult(
            passed=False,
            failures=(failure,),
            summary_text=_summary_text(False, None, (failure,), None),
        )

    triage_report = triage_evaluation_batch(candidate_batch)
    scoreboard_record = build_scoreboard_record(
        candidate_batch,
        agent_name=effective_config.agent_name,
        agent_version=effective_config.agent_version,
        commit=effective_config.commit,
        scenario_set=effective_config.scenario_set,
        notes=effective_config.notes,
        metadata=effective_config.metadata,
    )
    failures = tuple(
        _gate_failures(
            config=effective_config,
            candidate_batch=candidate_batch,
            parity_result=parity_result,
            triage_report=triage_report,
            scoreboard_record=scoreboard_record,
        )
    )
    passed = not failures
    return RegressionGateResult(
        passed=passed,
        failures=failures,
        scoreboard_record=scoreboard_record,
        triage_report=triage_report,
        parity_result=parity_result,
        summary_text=_summary_text(
            passed,
            scoreboard_record,
            failures,
            parity_result,
        ),
    )


def _default_gate_matches() -> tuple[MatchConfig, ...]:
    candidate = builtin_baseline_spec(
        BaselineName.NEAREST_NEUTRAL,
        name="candidate-nearest-neutral",
    )
    opponent = OpponentSpec(
        builtin_baseline_spec(BaselineName.NOOP, name="opponent-noop")
    )
    return tuple(
        MatchConfig(
            seed=seed,
            player_count=PlayerCount.TWO_PLAYER,
            controlled_seat=0,
            candidate_agent=candidate,
            opponent_agents=(opponent,),
            label=f"quick-gate-{seed}",
        )
        for seed in (7, 8)
    )


def _gate_failures(
    *,
    config: RegressionGateConfig,
    candidate_batch: EvaluationBatchResult,
    parity_result: SubmissionParityResult,
    triage_report: FailureTriageReport,
    scoreboard_record: ScoreboardRecord,
) -> list[RegressionGateFailure]:
    failures: list[RegressionGateFailure] = []
    if not parity_result.passed:
        failures.append(
            RegressionGateFailure(
                code="parity_mismatch",
                message="generated submission parity failed",
            )
        )
    failures.extend(_batch_status_failures("candidate", candidate_batch))
    failures.extend(_batch_status_failures("modular", parity_result.modular_batch))
    failures.extend(_batch_status_failures("submission", parity_result.submission_batch))
    failures.extend(_triage_failures(triage_report, side="candidate"))
    failures.extend(
        _triage_failures(
            triage_evaluation_batch(parity_result.modular_batch),
            side="modular",
        )
    )
    failures.extend(
        _triage_failures(
            triage_evaluation_batch(parity_result.submission_batch),
            side="submission",
        )
    )
    failures.extend(_threshold_failures(config, scoreboard_record))
    return failures


def _batch_status_failures(
    side: str,
    batch: EvaluationBatchResult,
) -> list[RegressionGateFailure]:
    failures: list[RegressionGateFailure] = []
    for index, result in enumerate(batch.results):
        if result.status is EvaluationStatus.COMPLETED:
            continue
        failures.append(
            RegressionGateFailure(
                code=f"{side}_match_status_failure",
                message=f"{side} match {index} ended with {result.status.value}",
                match_index=index,
                status=result.status.value,
            )
        )
    return failures


def _triage_failures(
    report: FailureTriageReport,
    *,
    side: str,
) -> list[RegressionGateFailure]:
    severe_values = {
        category.value
        for category in SEVERE_TRIAGE_CATEGORIES
    }
    failures = []
    for category, count in report.category_counts:
        if category not in severe_values:
            continue
        code = (
            "triage_failure_category"
            if side == "candidate"
            else f"{side}_triage_failure_category"
        )
        failures.append(
            RegressionGateFailure(
                code=code,
                message=f"{side} triage category {category} count {count}",
                category=category,
            )
        )
    return failures


def _threshold_failures(
    config: RegressionGateConfig,
    record: ScoreboardRecord,
) -> list[RegressionGateFailure]:
    failures = []
    if record.error_rate is not None and record.error_rate > config.max_error_rate:
        failures.append(
            RegressionGateFailure(
                code="max_error_rate_exceeded",
                message=(
                    f"error_rate {record.error_rate:.6g} exceeds "
                    f"{config.max_error_rate:.6g}"
                ),
            )
        )
    if record.mean_rank is not None and record.mean_rank > config.max_mean_rank:
        failures.append(
            RegressionGateFailure(
                code="max_mean_rank_exceeded",
                message=(
                    f"mean_rank {record.mean_rank:.6g} exceeds "
                    f"{config.max_mean_rank:.6g}"
                ),
            )
        )
    if record.win_rate is not None and record.win_rate < config.min_win_rate:
        failures.append(
            RegressionGateFailure(
                code="min_win_rate_not_met",
                message=(
                    f"win_rate {record.win_rate:.6g} below "
                    f"{config.min_win_rate:.6g}"
                ),
            )
        )
    return failures


def _summary_text(
    passed: bool,
    record: ScoreboardRecord | None,
    failures: tuple[RegressionGateFailure, ...],
    parity_result: SubmissionParityResult | None,
) -> str:
    status = "PASS" if passed else "FAIL"
    match_count = record.match_count if record is not None else 0
    win_rate = _format_optional_float(record.win_rate if record is not None else None)
    error_rate = _format_optional_float(
        record.error_rate if record is not None else None
    )
    mean_rank = _format_optional_float(record.mean_rank if record is not None else None)
    parity = (
        "none"
        if parity_result is None
        else (
            "pass"
            if parity_result.passed
            else f"fail:{parity_result.mismatch_count}"
        )
    )
    return (
        f"gate={status} matches={match_count} win_rate={win_rate} "
        f"mean_rank={mean_rank} error_rate={error_rate} parity={parity} "
        f"failures={len(failures)}"
    )


def _format_optional_float(value: float | None) -> str:
    if value is None:
        return "none"
    return f"{value:.6g}"


def _parity_result_to_dict(
    parity_result: SubmissionParityResult | None,
) -> dict[str, object] | None:
    if parity_result is None:
        return None
    return {
        "passed": parity_result.passed,
        "mismatch_count": parity_result.mismatch_count,
        "comparisons": [
            {
                "index": comparison.index,
                "status_matches": comparison.status_matches,
                "metrics_match": comparison.metrics_match,
                "matched": comparison.matched,
                "mismatch_reasons": list(comparison.mismatch_reasons),
                "modular_status": comparison.modular_result.status.value,
                "submission_status": comparison.submission_result.status.value,
            }
            for comparison in parity_result.comparisons
        ],
    }


def _validate_nonempty_string(value: object, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


def _validate_nonnegative_number(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ValueError(f"{name} must be a non-negative number")


def _validate_rate(value: object, name: str) -> None:
    _validate_nonnegative_number(value, name)
    if float(value) > 1.0:
        raise ValueError(f"{name} must be between 0.0 and 1.0")


def _validate_string_tuple(value: tuple[str, ...], name: str) -> None:
    if not isinstance(value, tuple):
        raise ValueError(f"{name} must be a tuple")
    for item in value:
        _validate_nonempty_string(item, name)


def _validate_metadata(metadata: tuple[tuple[str, str], ...]) -> None:
    if not isinstance(metadata, tuple):
        raise ValueError("metadata must be a tuple")
    for item in metadata:
        if not isinstance(item, tuple) or len(item) != 2:
            raise ValueError("metadata entries must be key/value tuples")
        _validate_nonempty_string(item[0], "metadata key")
        if not isinstance(item[1], str):
            raise ValueError("metadata values must be strings")


def _error_text(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


__all__ = (
    "RegressionGateConfig",
    "RegressionGateFailure",
    "RegressionGateResult",
    "run_regression_gate",
)
