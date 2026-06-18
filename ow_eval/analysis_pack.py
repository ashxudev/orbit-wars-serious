"""Planner-improvement analysis packs for local evaluation results.

Evaluation Harness Cycle 11 converts existing ``EvaluationBatchResult`` objects
into compact diagnostics for planner improvement. It does not run matches,
parse replays, write artifacts, or import Kaggle environments.
"""

from __future__ import annotations

from dataclasses import dataclass

from .batch_runner import EvaluationBatchResult
from .contracts import EvaluationStatus, MatchResult
from .triage import (
    FailureCategory,
    FailureTriageItem,
    triage_evaluation_batch,
)


@dataclass(frozen=True, slots=True)
class PlannerAnalysisPackConfig:
    """Configuration for building planner analysis packs."""

    max_items: int | None = None
    include_clean_wins: bool = False

    def __post_init__(self) -> None:
        if self.max_items is not None:
            _validate_nonnegative_int(self.max_items, "max_items")
        if not isinstance(self.include_clean_wins, bool):
            raise ValueError("include_clean_wins must be a boolean")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "max_items": self.max_items,
            "include_clean_wins": self.include_clean_wins,
        }


@dataclass(frozen=True, slots=True)
class PlannerAnalysisItem:
    """One deterministic planner-improvement diagnostic item."""

    batch_index: int
    label: str | None
    seed: int
    player_count: int
    controlled_seat: int
    candidate_agent_name: str
    opponent_names: tuple[str, ...]
    status: EvaluationStatus
    triage_category: FailureCategory
    triage_reason: str
    final_rank: int | None = None
    final_score: float | None = None
    final_planets: int | None = None
    final_ships: int | None = None
    final_production: int | None = None
    turns_survived: int | None = None
    no_action_count: int | None = None
    invalid_action_count: int | None = None
    timeout_count: int | None = None
    error_count: int | None = None
    error_text: str | None = None
    replay_path: str | None = None
    artifact_path: str | None = None
    selected_metadata: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        _validate_nonnegative_int(self.batch_index, "batch_index")
        _validate_string_tuple(self.opponent_names, "opponent_names")
        _validate_metadata(self.selected_metadata)

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "batch_index": self.batch_index,
            "label": self.label,
            "seed": self.seed,
            "player_count": self.player_count,
            "controlled_seat": self.controlled_seat,
            "candidate_agent_name": self.candidate_agent_name,
            "opponent_names": list(self.opponent_names),
            "status": self.status.value,
            "triage_category": self.triage_category.value,
            "triage_reason": self.triage_reason,
            "final_rank": self.final_rank,
            "final_score": self.final_score,
            "final_planets": self.final_planets,
            "final_ships": self.final_ships,
            "final_production": self.final_production,
            "turns_survived": self.turns_survived,
            "no_action_count": self.no_action_count,
            "invalid_action_count": self.invalid_action_count,
            "timeout_count": self.timeout_count,
            "error_count": self.error_count,
            "error_text": self.error_text,
            "replay_path": self.replay_path,
            "artifact_path": self.artifact_path,
            "selected_metadata": [
                {"key": key, "value": value}
                for key, value in self.selected_metadata
            ],
        }


@dataclass(frozen=True, slots=True)
class PlannerAnalysisPack:
    """Ordered planner-improvement diagnostics for one evaluation batch."""

    items: tuple[PlannerAnalysisItem, ...] = ()
    total_results: int = 0
    included_count: int = 0
    omitted_count: int = 0
    triage_category_counts: tuple[tuple[str, int], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.items, tuple):
            raise ValueError("items must be a tuple")
        for item in self.items:
            if not isinstance(item, PlannerAnalysisItem):
                raise ValueError("items entries must be PlannerAnalysisItem objects")
        _validate_nonnegative_int(self.total_results, "total_results")
        _validate_nonnegative_int(self.included_count, "included_count")
        _validate_nonnegative_int(self.omitted_count, "omitted_count")
        _validate_category_counts(self.triage_category_counts)

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "items": [
                item.to_dict()
                for item in self.items
            ],
            "total_results": self.total_results,
            "included_count": self.included_count,
            "omitted_count": self.omitted_count,
            "triage_category_counts": [
                {"category": category, "count": count}
                for category, count in self.triage_category_counts
            ],
        }

    def summary_text(self) -> str:
        """Return a compact deterministic plain-text summary."""

        categories = ",".join(
            f"{category}:{count}"
            for category, count in self.triage_category_counts
        )
        if not categories:
            categories = "none"
        return (
            f"analysis_items={self.included_count} total={self.total_results} "
            f"omitted={self.omitted_count} categories={categories}"
        )


def build_planner_analysis_pack(
    batch: EvaluationBatchResult,
    config: PlannerAnalysisPackConfig | None = None,
) -> PlannerAnalysisPack:
    """Build deterministic planner-improvement diagnostics for ``batch``."""

    effective_config = PlannerAnalysisPackConfig() if config is None else config
    triage_report = triage_evaluation_batch(batch)
    selected_items: list[PlannerAnalysisItem] = []

    for result, triage_item in zip(batch.results, triage_report.items):
        if not _should_include_item(triage_item, effective_config):
            continue
        if (
            effective_config.max_items is not None
            and len(selected_items) >= effective_config.max_items
        ):
            continue
        selected_items.append(_analysis_item(result, triage_item))

    items = tuple(selected_items)
    return PlannerAnalysisPack(
        items=items,
        total_results=len(batch.results),
        included_count=len(items),
        omitted_count=len(batch.results) - len(items),
        triage_category_counts=_category_counts(items),
    )


def _should_include_item(
    triage_item: FailureTriageItem,
    config: PlannerAnalysisPackConfig,
) -> bool:
    if config.include_clean_wins:
        return True
    return triage_item.category is not FailureCategory.CLEAN


def _analysis_item(
    result: MatchResult,
    triage_item: FailureTriageItem,
) -> PlannerAnalysisItem:
    config = result.config
    metrics = result.metrics
    return PlannerAnalysisItem(
        batch_index=triage_item.index if triage_item.index is not None else 0,
        label=config.label,
        seed=config.seed,
        player_count=config.player_count.value,
        controlled_seat=config.controlled_seat,
        candidate_agent_name=config.candidate_agent.name,
        opponent_names=tuple(opponent.name for opponent in config.opponent_agents),
        status=result.status,
        triage_category=triage_item.category,
        triage_reason=triage_item.reason,
        final_rank=metrics.final_rank,
        final_score=metrics.final_score,
        final_planets=metrics.final_planets,
        final_ships=metrics.final_ships,
        final_production=metrics.final_production,
        turns_survived=metrics.turns_survived,
        no_action_count=metrics.no_action_count,
        invalid_action_count=metrics.invalid_action_count,
        timeout_count=metrics.timeout_count,
        error_count=metrics.error_count,
        error_text=result.error_text,
        replay_path=result.replay_path,
        artifact_path=result.artifact_path,
        selected_metadata=_selected_metadata(config.metadata, result.metadata),
    )


def _selected_metadata(
    *metadata_groups: tuple[tuple[str, str], ...],
) -> tuple[tuple[str, str], ...]:
    selected = []
    for metadata in metadata_groups:
        for key, value in metadata:
            if _is_selected_metadata_key(key):
                selected.append((key, value))
    return tuple(selected)


def _is_selected_metadata_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_").replace(" ", "_")
    return normalized == "selected" or normalized.startswith("selected_")


def _category_counts(
    items: tuple[PlannerAnalysisItem, ...],
) -> tuple[tuple[str, int], ...]:
    counts = {
        category: 0
        for category in FailureCategory
    }
    for item in items:
        counts[item.triage_category] += 1
    return tuple(
        (category.value, count)
        for category, count in counts.items()
        if count > 0
    )


def _validate_nonnegative_int(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")


def _validate_string_tuple(value: tuple[str, ...], name: str) -> None:
    if not isinstance(value, tuple):
        raise ValueError(f"{name} must be a tuple")
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"{name} entries must be strings")


def _validate_metadata(metadata: tuple[tuple[str, str], ...]) -> None:
    if not isinstance(metadata, tuple):
        raise ValueError("metadata must be a tuple")
    for item in metadata:
        if not isinstance(item, tuple) or len(item) != 2:
            raise ValueError("metadata entries must be key/value tuples")
        if not isinstance(item[0], str) or not isinstance(item[1], str):
            raise ValueError("metadata keys and values must be strings")


def _validate_category_counts(category_counts: tuple[tuple[str, int], ...]) -> None:
    if not isinstance(category_counts, tuple):
        raise ValueError("triage_category_counts must be a tuple")
    for item in category_counts:
        if not isinstance(item, tuple) or len(item) != 2:
            raise ValueError("triage_category_counts entries must be tuples")
        if not isinstance(item[0], str):
            raise ValueError("triage_category_counts category must be a string")
        _validate_nonnegative_int(item[1], "triage_category_counts count")


__all__ = (
    "PlannerAnalysisItem",
    "PlannerAnalysisPack",
    "PlannerAnalysisPackConfig",
    "build_planner_analysis_pack",
)
