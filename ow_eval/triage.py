"""Deterministic failure triage for local evaluation results.

Evaluation Harness Cycle 8 groups existing ``MatchResult`` objects into stable
failure buckets. It does not run matches, parse replays, write artifacts, or
apply regression gates.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from .batch_runner import EvaluationBatchResult
from .contracts import EvaluationStatus, MatchResult


NOOP_HEAVY_MIN_NO_ACTION_COUNT = 50
NOOP_HEAVY_MIN_RATIO = 0.8


class FailureCategory(str, Enum):
    """Stable failure category labels for local evaluation triage."""

    PARSE_CRASH = "parse_crash"
    PLANNER_CRASH = "planner_crash"
    ACTION_CONVERSION_CRASH = "action_conversion_crash"
    TIMEOUT_OR_BUDGET_FALLBACK = "timeout_or_budget_fallback"
    INVALID_OR_NOOP_HEAVY_BEHAVIOR = "invalid_or_noop_heavy_behavior"
    NORMAL_LOSS = "normal_loss"
    CLEAN = "clean"
    OTHER_FAILURE = "other_failure"


@dataclass(frozen=True, slots=True)
class FailureTriageItem:
    """Triage record for one ``MatchResult``."""

    index: int | None
    label: str | None
    seed: int
    player_count: int
    controlled_seat: int
    status: EvaluationStatus
    category: FailureCategory
    reason: str
    final_rank: int | None = None
    error_text: str | None = None
    artifact_path: str | None = None
    replay_path: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic plain dictionary representation."""

        return {
            "index": self.index,
            "label": self.label,
            "seed": self.seed,
            "player_count": self.player_count,
            "controlled_seat": self.controlled_seat,
            "status": self.status.value,
            "category": self.category.value,
            "reason": self.reason,
            "final_rank": self.final_rank,
            "error_text": self.error_text,
            "artifact_path": self.artifact_path,
            "replay_path": self.replay_path,
        }


@dataclass(frozen=True, slots=True)
class FailureTriageReport:
    """Ordered triage items plus deterministic category summary counts."""

    items: tuple[FailureTriageItem, ...] = ()
    category_counts: tuple[tuple[str, int], ...] = ()
    total_results: int = 0
    clean_count: int = 0
    failure_count: int = 0

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic plain dictionary representation."""

        return {
            "items": [
                item.to_dict()
                for item in self.items
            ],
            "category_counts": [
                {"category": category, "count": count}
                for category, count in self.category_counts
            ],
            "total_results": self.total_results,
            "clean_count": self.clean_count,
            "failure_count": self.failure_count,
        }


def triage_match_result(
    result: MatchResult,
    index: int | None = None,
) -> FailureTriageItem:
    """Classify one ``MatchResult`` into a deterministic failure category."""

    category, reason = _category_and_reason(result)
    return FailureTriageItem(
        index=index,
        label=result.config.label,
        seed=result.config.seed,
        player_count=result.config.player_count.value,
        controlled_seat=result.config.controlled_seat,
        status=result.status,
        category=category,
        reason=reason,
        final_rank=result.metrics.final_rank,
        error_text=result.error_text,
        artifact_path=result.artifact_path,
        replay_path=result.replay_path,
    )


def triage_match_results(
    results: Sequence[MatchResult],
) -> FailureTriageReport:
    """Return deterministic triage items and category counts for ``results``."""

    items = tuple(
        triage_match_result(result, index)
        for index, result in enumerate(results)
    )
    category_counts = _category_counts(items)
    clean_count = sum(
        1
        for item in items
        if item.category is FailureCategory.CLEAN
    )
    return FailureTriageReport(
        items=items,
        category_counts=category_counts,
        total_results=len(items),
        clean_count=clean_count,
        failure_count=len(items) - clean_count,
    )


def triage_evaluation_batch(
    batch: EvaluationBatchResult,
) -> FailureTriageReport:
    """Triage the ordered results from an ``EvaluationBatchResult``."""

    return triage_match_results(batch.results)


def _category_and_reason(result: MatchResult) -> tuple[FailureCategory, str]:
    error_text = result.error_text or ""
    normalized_error = error_text.lower()

    if _has_timeout_or_budget_facts(result, normalized_error):
        return (
            FailureCategory.TIMEOUT_OR_BUDGET_FALLBACK,
            "timeout, budget, or fallback signal",
        )
    if _has_invalid_or_noop_heavy_facts(result):
        return (
            FailureCategory.INVALID_OR_NOOP_HEAVY_BEHAVIOR,
            "invalid action or no-op heavy behavior",
        )
    if _has_action_conversion_error(normalized_error):
        return (
            FailureCategory.ACTION_CONVERSION_CRASH,
            "action conversion error text",
        )
    if _has_parse_error(normalized_error):
        return (
            FailureCategory.PARSE_CRASH,
            "parse or observation adapter error text",
        )
    if _has_planner_error(normalized_error):
        return (
            FailureCategory.PLANNER_CRASH,
            "planner pipeline error text",
        )
    if (
        result.status is EvaluationStatus.COMPLETED
        and result.metrics.final_rank is not None
        and result.metrics.final_rank > 1
    ):
        return FailureCategory.NORMAL_LOSS, "completed with losing final rank"
    if result.status is EvaluationStatus.COMPLETED:
        return FailureCategory.CLEAN, "completed without triage issue"
    return FailureCategory.OTHER_FAILURE, "unclassified non-completed result"


def _has_timeout_or_budget_facts(
    result: MatchResult,
    normalized_error: str,
) -> bool:
    if result.status is EvaluationStatus.TIMEOUT:
        return True
    if result.metrics.timeout_count is not None and result.metrics.timeout_count > 0:
        return True
    return _contains_any(
        normalized_error,
        (
            "timeout",
            "timed out",
            "time limit",
            "budget",
            "overage",
            "fallback",
            "low_budget",
            "budget_exhausted",
        ),
    )


def _has_invalid_or_noop_heavy_facts(result: MatchResult) -> bool:
    if result.status is EvaluationStatus.INVALID_ACTION:
        return True
    if (
        result.metrics.invalid_action_count is not None
        and result.metrics.invalid_action_count > 0
    ):
        return True
    no_action_count = result.metrics.no_action_count
    if no_action_count is None or no_action_count < NOOP_HEAVY_MIN_NO_ACTION_COUNT:
        return False
    turns_survived = result.metrics.turns_survived
    if turns_survived is None or turns_survived <= 0:
        return True
    return (no_action_count / turns_survived) >= NOOP_HEAVY_MIN_RATIO


def _has_parse_error(normalized_error: str) -> bool:
    return _contains_any(
        normalized_error,
        (
            "parse",
            "parser",
            "observation_to_game_state",
            "observation adapter",
            "invalid observation",
            "runtime_state",
            "runtime state",
            "state adapter",
            "state parsing",
            "gamestate.from_obs",
            "game state",
            "game state from observation",
        ),
    )


def _has_planner_error(normalized_error: str) -> bool:
    return _contains_any(
        normalized_error,
        (
            "planner",
            "run_planner_pipeline",
            "candidate",
            "generate_candidates",
            "candidate generation",
            "evaluation",
            "evaluate_and_score_candidates",
            "mission evaluation",
            "scoring",
            "response",
            "commitment",
            "strategy",
            "selection",
        ),
    )


def _has_action_conversion_error(normalized_error: str) -> bool:
    return _contains_any(
        normalized_error,
        (
            "action conversion",
            "planner_result_to_actions",
            "mission_candidate_to_actions",
            "mission_candidate_to_orders",
            "action row",
            "launch order",
            "kaggle action",
        ),
    )


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _category_counts(
    items: tuple[FailureTriageItem, ...],
) -> tuple[tuple[str, int], ...]:
    counts = {
        category: 0
        for category in FailureCategory
    }
    for item in items:
        counts[item.category] += 1
    return tuple(
        (category.value, count)
        for category, count in counts.items()
        if count > 0
    )


__all__ = (
    "FailureCategory",
    "FailureTriageItem",
    "FailureTriageReport",
    "triage_evaluation_batch",
    "triage_match_result",
    "triage_match_results",
)
