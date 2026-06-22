"""Deterministic regression report for historical gauntlet leak fixtures.

This module is measurement-only. It runs the committed compact historical
gauntlet fixtures through the current runtime path and summarizes whether the
known deterministic leak classes remain plugged or unresolved.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from agents.runtime_state import observation_to_game_state
from agents.runtime_turn import (
    last_runtime_diagnostic_metadata,
    safe_actions_for_observation,
)


BUDGET_GUARD_REASONS = frozenset(
    ("budget_guard_budget_exhausted", "budget_guard_low_budget")
)

CASE_CLASS_ACTION_EMITTED = "action_emitted"
CASE_CLASS_SOURCE_LESS = "source_less_no_owned_planets"
CASE_CLASS_BUDGET_GUARDED = "budget_guarded"
CASE_CLASS_CANDIDATE_STARVATION = "candidate_starvation_unresolved"
CASE_CLASS_STRATEGY_NO_ACTION = "strategy_selection_no_action_unresolved"
CASE_CLASS_OTHER_NO_ACTION = "other_no_action"


@dataclass(frozen=True, slots=True)
class HistoricalLeakRegressionCaseResult:
    """One historical gauntlet fixture runtime result."""

    fixture_name: str
    case_id: str
    leak_class: str
    player_count: int
    turn: int
    player_id: int
    action_count: int
    action_summary: tuple[tuple[object, ...], ...]
    diagnostic_status: str
    no_action_reason: str
    candidate_count: int
    evaluation_count: int
    budget_status: str | None
    selected_commitment_type: str | None
    selected_mission_type: str | None
    selection_notes: str
    classification: str

    @property
    def emitted_action(self) -> bool:
        return self.action_count > 0

    @property
    def unresolved_deterministic_leak(self) -> bool:
        return self.classification in (
            CASE_CLASS_CANDIDATE_STARVATION,
            CASE_CLASS_STRATEGY_NO_ACTION,
            CASE_CLASS_OTHER_NO_ACTION,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "action_count": self.action_count,
            "action_summary": [list(action) for action in self.action_summary],
            "budget_status": self.budget_status,
            "candidate_count": self.candidate_count,
            "case_id": self.case_id,
            "classification": self.classification,
            "diagnostic_status": self.diagnostic_status,
            "emitted_action": self.emitted_action,
            "evaluation_count": self.evaluation_count,
            "fixture_name": self.fixture_name,
            "leak_class": self.leak_class,
            "no_action_reason": self.no_action_reason,
            "player_count": self.player_count,
            "player_id": self.player_id,
            "selected_commitment_type": self.selected_commitment_type,
            "selected_mission_type": self.selected_mission_type,
            "selection_notes": self.selection_notes,
            "turn": self.turn,
            "unresolved_deterministic_leak": self.unresolved_deterministic_leak,
        }


@dataclass(frozen=True, slots=True)
class HistoricalLeakRegressionMetrics:
    """Aggregate historical gauntlet leak fixture metrics."""

    total_cases: int
    action_emitting_count: int
    source_less_no_owned_planets_count: int
    budget_guarded_no_action_count: int
    unresolved_no_candidates_generated_count: int
    unresolved_strategy_selection_no_action_count: int
    other_no_action_count: int
    unresolved_deterministic_leak_count: int

    @property
    def action_emitting_rate(self) -> float:
        return _rate(self.action_emitting_count, self.total_cases)

    def to_dict(self) -> dict[str, object]:
        return {
            "action_emitting_count": self.action_emitting_count,
            "action_emitting_rate": self.action_emitting_rate,
            "budget_guarded_no_action_count": self.budget_guarded_no_action_count,
            "other_no_action_count": self.other_no_action_count,
            "source_less_no_owned_planets_count": (
                self.source_less_no_owned_planets_count
            ),
            "total_cases": self.total_cases,
            "unresolved_deterministic_leak_count": (
                self.unresolved_deterministic_leak_count
            ),
            "unresolved_no_candidates_generated_count": (
                self.unresolved_no_candidates_generated_count
            ),
            "unresolved_strategy_selection_no_action_count": (
                self.unresolved_strategy_selection_no_action_count
            ),
        }


@dataclass(frozen=True, slots=True)
class HistoricalLeakRegressionReport:
    """Deterministic historical gauntlet leak regression report."""

    fixture_dir: str
    case_results: tuple[HistoricalLeakRegressionCaseResult, ...]
    metrics: HistoricalLeakRegressionMetrics
    summary_text: str

    def to_dict(self) -> dict[str, object]:
        return {
            "case_results": [case.to_dict() for case in self.case_results],
            "fixture_dir": self.fixture_dir,
            "metrics": self.metrics.to_dict(),
            "summary_text": self.summary_text,
        }


def default_historical_leak_fixture_dir() -> Path:
    """Return the committed compact historical gauntlet leak fixture directory."""

    return (
        Path(__file__).resolve().parents[1]
        / "tests"
        / "fixtures"
        / "historical_gauntlet_leaks"
    )


def run_historical_leak_regression(
    fixture_dir: str | Path | None = None,
) -> HistoricalLeakRegressionReport:
    """Run all compact historical gauntlet fixtures and return a report."""

    resolved_fixture_dir = (
        default_historical_leak_fixture_dir()
        if fixture_dir is None
        else Path(fixture_dir)
    )
    paths = tuple(sorted(resolved_fixture_dir.glob("*.json")))
    if not paths:
        raise ValueError(
            f"no historical gauntlet leak fixtures found in {resolved_fixture_dir}"
        )

    case_results = tuple(_run_case(path) for path in paths)
    metrics = _summarize_case_results(case_results)
    return HistoricalLeakRegressionReport(
        fixture_dir=str(resolved_fixture_dir),
        case_results=case_results,
        metrics=metrics,
        summary_text=_summary_text(metrics),
    )


def _run_case(path: Path) -> HistoricalLeakRegressionCaseResult:
    payload = _read_payload(path)
    observation = _required_mapping(payload, "observation")
    case_id = _required_str(payload, "case_id")
    leak_class = _required_str(payload, "leak_class")
    player_count = _required_int(payload, "player_count")
    turn = _required_int(payload, "turn")

    state = observation_to_game_state(observation)
    player_id = _required_player_id(state.player_id, path)
    actions = safe_actions_for_observation(observation, {})
    metadata = dict(last_runtime_diagnostic_metadata())
    no_action_reason = metadata.get("runtime_diagnostic_no_action_reason", "")
    classification = _classify_case(len(actions), no_action_reason)

    return HistoricalLeakRegressionCaseResult(
        fixture_name=path.name,
        case_id=case_id,
        leak_class=leak_class,
        player_count=player_count,
        turn=turn,
        player_id=player_id,
        action_count=len(actions),
        action_summary=_action_summary(actions),
        diagnostic_status=metadata.get("runtime_diagnostic_status", ""),
        no_action_reason=no_action_reason,
        candidate_count=_int_metadata(
            metadata,
            "runtime_diagnostic_candidate_count",
        ),
        evaluation_count=_int_metadata(
            metadata,
            "runtime_diagnostic_evaluation_count",
        ),
        budget_status=metadata.get("runtime_diagnostic_budget_status"),
        selected_commitment_type=metadata.get(
            "runtime_diagnostic_selected_commitment_type"
        ),
        selected_mission_type=metadata.get("runtime_diagnostic_selected_mission_type"),
        selection_notes=metadata.get("runtime_diagnostic_selection_notes", ""),
        classification=classification,
    )


def _classify_case(action_count: int, no_action_reason: str) -> str:
    if action_count > 0:
        return CASE_CLASS_ACTION_EMITTED
    if no_action_reason == "no_owned_planets":
        return CASE_CLASS_SOURCE_LESS
    if no_action_reason in BUDGET_GUARD_REASONS:
        return CASE_CLASS_BUDGET_GUARDED
    if no_action_reason == "no_candidates_generated":
        return CASE_CLASS_CANDIDATE_STARVATION
    if no_action_reason == "strategy_selection_no_action":
        return CASE_CLASS_STRATEGY_NO_ACTION
    return CASE_CLASS_OTHER_NO_ACTION


def _summarize_case_results(
    case_results: Sequence[HistoricalLeakRegressionCaseResult],
) -> HistoricalLeakRegressionMetrics:
    total_cases = len(case_results)
    action_emitting_count = sum(
        1 for case in case_results if case.classification == CASE_CLASS_ACTION_EMITTED
    )
    source_less_count = sum(
        1 for case in case_results if case.classification == CASE_CLASS_SOURCE_LESS
    )
    budget_guarded_count = sum(
        1 for case in case_results if case.classification == CASE_CLASS_BUDGET_GUARDED
    )
    candidate_starvation_count = sum(
        1
        for case in case_results
        if case.classification == CASE_CLASS_CANDIDATE_STARVATION
    )
    strategy_no_action_count = sum(
        1
        for case in case_results
        if case.classification == CASE_CLASS_STRATEGY_NO_ACTION
    )
    other_no_action_count = sum(
        1 for case in case_results if case.classification == CASE_CLASS_OTHER_NO_ACTION
    )
    return HistoricalLeakRegressionMetrics(
        total_cases=total_cases,
        action_emitting_count=action_emitting_count,
        source_less_no_owned_planets_count=source_less_count,
        budget_guarded_no_action_count=budget_guarded_count,
        unresolved_no_candidates_generated_count=candidate_starvation_count,
        unresolved_strategy_selection_no_action_count=strategy_no_action_count,
        other_no_action_count=other_no_action_count,
        unresolved_deterministic_leak_count=(
            candidate_starvation_count + strategy_no_action_count + other_no_action_count
        ),
    )


def _summary_text(metrics: HistoricalLeakRegressionMetrics) -> str:
    return (
        "historical_leak_regression "
        f"cases={metrics.total_cases} "
        f"action_emitting={metrics.action_emitting_count} "
        f"action_rate={metrics.action_emitting_rate} "
        f"source_less_no_owned={metrics.source_less_no_owned_planets_count} "
        f"budget_guarded={metrics.budget_guarded_no_action_count} "
        f"unresolved_no_candidates={metrics.unresolved_no_candidates_generated_count} "
        f"unresolved_strategy_no_action={metrics.unresolved_strategy_selection_no_action_count} "
        f"other_no_action={metrics.other_no_action_count} "
        f"unresolved_deterministic_leaks={metrics.unresolved_deterministic_leak_count}"
    )


def _action_summary(actions: Sequence[object]) -> tuple[tuple[object, ...], ...]:
    summary: list[tuple[object, ...]] = []
    for action in actions:
        if isinstance(action, Sequence) and not isinstance(action, (str, bytes)):
            summary.append(tuple(action))
        else:
            summary.append((action,))
    return tuple(summary)


def _rate(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 6)


def _read_payload(path: Path) -> Mapping[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"fixture {path} is not valid JSON: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise ValueError(f"fixture {path} must contain a JSON object")
    return payload


def _required_mapping(payload: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f"fixture field {key} must be an object")
    return value


def _required_str(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"fixture field {key} must be a non-empty string")
    return value


def _required_int(payload: Mapping[str, object], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"fixture field {key} must be an integer")
    return value


def _required_player_id(value: int | None, path: Path) -> int:
    if value is None:
        raise ValueError(f"fixture {path} did not parse a player id")
    return value


def _int_metadata(metadata: Mapping[str, str], key: str) -> int:
    value = metadata.get(key)
    if value is None:
        return 0
    try:
        return int(value)
    except ValueError:
        return 0


__all__ = (
    "HistoricalLeakRegressionCaseResult",
    "HistoricalLeakRegressionMetrics",
    "HistoricalLeakRegressionReport",
    "default_historical_leak_fixture_dir",
    "run_historical_leak_regression",
)
