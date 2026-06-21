"""Deterministic regression report for compact V1 replay leak fixtures.

This module is measurement-only. It runs the committed single-observation V1
fixtures through the current runtime path, extracts existing deterministic
planner fact labels, and summarizes whether known V1 leak classes remain
plugged or unresolved.
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
from ow_planner.enemy_denial import enemy_denial_opportunity_facts
from ow_planner.four_player_plateau import four_player_plateau_facts
from ow_planner.four_player_rank import four_player_rank_facts
from ow_planner.owned_threats import owned_production_threat_facts
from ow_planner.own_transfers import own_transfer_intent_facts


BUDGET_GUARD_REASONS = frozenset(
    ("budget_guard_budget_exhausted", "budget_guard_low_budget")
)


@dataclass(frozen=True, slots=True)
class V1ReplayRegressionCaseResult:
    """One V1 replay fixture runtime and fact-label result."""

    fixture_name: str
    case_id: str
    leak_class: str
    player_count: int
    episode_id: int
    turn: int
    player_id: int
    action_count: int
    candidate_count: int
    diagnostic_status: str
    no_action_reason: str
    selected_commitment_type: str | None
    selection_notes: str
    owned_production_pressure: bool
    own_transfer_spam: bool
    high_value_enemy_denial: bool
    enemy_denial_safety_blocked: bool
    four_player_plateau: bool
    four_player_action_emitting_plateau: bool
    four_player_no_action_plateau: bool
    reduced_active_owner_caveat: bool
    rank_aware_continuation: bool
    thin_capture_risk: bool
    budget_guarded_no_action: bool
    leak_labels: tuple[str, ...] = ()

    @property
    def emitted_action(self) -> bool:
        return self.action_count > 0

    @property
    def unresolved_planner_no_action(self) -> bool:
        return (
            not self.emitted_action
            and not self.budget_guarded_no_action
            and not self.reduced_active_owner_caveat
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "action_count": self.action_count,
            "budget_guarded_no_action": self.budget_guarded_no_action,
            "candidate_count": self.candidate_count,
            "case_id": self.case_id,
            "diagnostic_status": self.diagnostic_status,
            "emitted_action": self.emitted_action,
            "enemy_denial_safety_blocked": self.enemy_denial_safety_blocked,
            "episode_id": self.episode_id,
            "fixture_name": self.fixture_name,
            "four_player_action_emitting_plateau": (
                self.four_player_action_emitting_plateau
            ),
            "four_player_no_action_plateau": self.four_player_no_action_plateau,
            "four_player_plateau": self.four_player_plateau,
            "high_value_enemy_denial": self.high_value_enemy_denial,
            "leak_class": self.leak_class,
            "leak_labels": list(self.leak_labels),
            "no_action_reason": self.no_action_reason,
            "own_transfer_spam": self.own_transfer_spam,
            "owned_production_pressure": self.owned_production_pressure,
            "player_count": self.player_count,
            "player_id": self.player_id,
            "rank_aware_continuation": self.rank_aware_continuation,
            "reduced_active_owner_caveat": self.reduced_active_owner_caveat,
            "selected_commitment_type": self.selected_commitment_type,
            "selection_notes": self.selection_notes,
            "thin_capture_risk": self.thin_capture_risk,
            "turn": self.turn,
            "unresolved_planner_no_action": self.unresolved_planner_no_action,
        }


@dataclass(frozen=True, slots=True)
class V1ReplayRegressionMetrics:
    """Aggregate V1 replay leak fixture metrics."""

    total_cases: int
    live_action_count: int
    live_no_action_count: int
    unresolved_planner_no_action_count: int
    reduced_active_owner_caveat_count: int
    owned_production_pressure_coverage_count: int
    own_transfer_spam_coverage_count: int
    enemy_denial_safety_blocked_count: int
    four_player_plateau_action_count: int
    four_player_plateau_no_action_count: int
    rank_aware_continuation_count: int
    thin_capture_risk_count: int
    budget_guarded_no_action_count: int

    @property
    def live_action_rate(self) -> float:
        return _rate(self.live_action_count, self.total_cases)

    def to_dict(self) -> dict[str, object]:
        return {
            "budget_guarded_no_action_count": self.budget_guarded_no_action_count,
            "enemy_denial_safety_blocked_count": (
                self.enemy_denial_safety_blocked_count
            ),
            "four_player_plateau_action_count": (
                self.four_player_plateau_action_count
            ),
            "four_player_plateau_no_action_count": (
                self.four_player_plateau_no_action_count
            ),
            "live_action_count": self.live_action_count,
            "live_action_rate": self.live_action_rate,
            "live_no_action_count": self.live_no_action_count,
            "own_transfer_spam_coverage_count": (
                self.own_transfer_spam_coverage_count
            ),
            "owned_production_pressure_coverage_count": (
                self.owned_production_pressure_coverage_count
            ),
            "rank_aware_continuation_count": self.rank_aware_continuation_count,
            "reduced_active_owner_caveat_count": (
                self.reduced_active_owner_caveat_count
            ),
            "thin_capture_risk_count": self.thin_capture_risk_count,
            "total_cases": self.total_cases,
            "unresolved_planner_no_action_count": (
                self.unresolved_planner_no_action_count
            ),
        }


@dataclass(frozen=True, slots=True)
class V1ReplayRegressionReport:
    """Deterministic V1 replay leak regression report."""

    fixture_dir: str
    case_results: tuple[V1ReplayRegressionCaseResult, ...]
    metrics: V1ReplayRegressionMetrics
    summary_text: str

    def to_dict(self) -> dict[str, object]:
        return {
            "case_results": [case.to_dict() for case in self.case_results],
            "fixture_dir": self.fixture_dir,
            "metrics": self.metrics.to_dict(),
            "summary_text": self.summary_text,
        }


def default_v1_replay_fixture_dir() -> Path:
    """Return the committed compact V1 replay leak fixture directory."""

    return Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "v1_replay_leaks"


def run_v1_replay_regression(
    fixture_dir: str | Path | None = None,
) -> V1ReplayRegressionReport:
    """Run all compact V1 replay fixtures and return a deterministic report."""

    resolved_fixture_dir = (
        default_v1_replay_fixture_dir() if fixture_dir is None else Path(fixture_dir)
    )
    paths = tuple(sorted(resolved_fixture_dir.glob("*.json")))
    if not paths:
        raise ValueError(f"no V1 replay leak fixtures found in {resolved_fixture_dir}")

    case_results = tuple(_run_case(path) for path in paths)
    metrics = _summarize_case_results(case_results)
    summary_text = _summary_text(metrics)
    return V1ReplayRegressionReport(
        fixture_dir=str(resolved_fixture_dir),
        case_results=case_results,
        metrics=metrics,
        summary_text=summary_text,
    )


def _run_case(path: Path) -> V1ReplayRegressionCaseResult:
    payload = _read_payload(path)
    observation = _required_mapping(payload, "observation")
    expected_runtime = _required_mapping(payload, "expected_current_runtime")
    case_id = _required_str(payload, "case_id")
    leak_class = _required_str(payload, "leak_class")
    player_count = _required_int(payload, "player_count")
    episode_id = _required_int(payload, "episode_id")
    turn = _required_int(payload, "turn")

    state = observation_to_game_state(observation)
    player_id = _required_player_id(state.player_id, path)
    actions = safe_actions_for_observation(observation, {})
    metadata = dict(last_runtime_diagnostic_metadata())

    owned_threat_report = owned_production_threat_facts(state)
    transfer_report = own_transfer_intent_facts(
        state,
        threat_report=owned_threat_report,
    )
    denial_report = enemy_denial_opportunity_facts(state)
    plateau_report = four_player_plateau_facts(
        state,
        declared_player_count=player_count,
        runtime_metadata=metadata,
    )
    rank_report = four_player_rank_facts(
        state,
        declared_player_count=player_count,
    )

    selection_notes = metadata.get("runtime_diagnostic_selection_notes", "")
    no_action_reason = metadata.get("runtime_diagnostic_no_action_reason", "")
    reduced_active_owner_caveat = (
        player_count == 4
        and rank_report.is_declared_four_player_context
        and not rank_report.is_active_four_player_context
        and "declared_four_player_reduced_active_owners" in rank_report.labels
    )
    owned_production_pressure = (
        owned_threat_report.production_pressure_count > 0
        or "owned_production_pressure" in owned_threat_report.labels
    )
    own_transfer_spam = (
        transfer_report.potentially_spammy_count > 0
        or "potentially_spammy_own_transfer" in transfer_report.labels
    )
    high_value_enemy_denial = (
        denial_report.high_value_denial_count > 0
        or "high_value_enemy_denial" in denial_report.labels
    )
    rank_aware_continuation = "rank-aware four-player continuation" in selection_notes
    thin_capture_risk = (
        leak_class == "thin_capture_recaptured"
        or (
            player_count == 4
            and rank_report.is_four_player_context
            and "thin_capture_risk_context" in rank_report.labels
        )
    )
    enemy_denial_safety_blocked = (
        leak_class == "enemy_denial_absent"
        and high_value_enemy_denial
        and owned_production_pressure
        and "owned-production pressure preference" in selection_notes
    )
    budget_guarded_no_action = (
        len(actions) == 0 and no_action_reason in BUDGET_GUARD_REASONS
    )
    leak_labels = _case_labels(
        owned_production_pressure=owned_production_pressure,
        own_transfer_spam=own_transfer_spam,
        high_value_enemy_denial=high_value_enemy_denial,
        enemy_denial_safety_blocked=enemy_denial_safety_blocked,
        four_player_plateau=plateau_report.plateaued,
        four_player_action_emitting_plateau=plateau_report.action_emitting_plateau,
        four_player_no_action_plateau=plateau_report.candidate_backlog_no_action,
        reduced_active_owner_caveat=reduced_active_owner_caveat,
        rank_aware_continuation=rank_aware_continuation,
        thin_capture_risk=thin_capture_risk,
        budget_guarded_no_action=budget_guarded_no_action,
    )

    return V1ReplayRegressionCaseResult(
        fixture_name=path.name,
        case_id=case_id,
        leak_class=leak_class,
        player_count=player_count,
        episode_id=episode_id,
        turn=turn,
        player_id=player_id,
        action_count=len(actions),
        candidate_count=_int_metadata(
            metadata,
            "runtime_diagnostic_candidate_count",
            expected_runtime.get("candidate_count"),
        ),
        diagnostic_status=metadata.get("runtime_diagnostic_status", ""),
        no_action_reason=no_action_reason,
        selected_commitment_type=metadata.get(
            "runtime_diagnostic_selected_commitment_type",
        ),
        selection_notes=selection_notes,
        owned_production_pressure=owned_production_pressure,
        own_transfer_spam=own_transfer_spam,
        high_value_enemy_denial=high_value_enemy_denial,
        enemy_denial_safety_blocked=enemy_denial_safety_blocked,
        four_player_plateau=plateau_report.plateaued,
        four_player_action_emitting_plateau=(
            plateau_report.action_emitting_plateau
        ),
        four_player_no_action_plateau=plateau_report.candidate_backlog_no_action,
        reduced_active_owner_caveat=reduced_active_owner_caveat,
        rank_aware_continuation=rank_aware_continuation,
        thin_capture_risk=thin_capture_risk,
        budget_guarded_no_action=budget_guarded_no_action,
        leak_labels=leak_labels,
    )


def _summarize_case_results(
    case_results: Sequence[V1ReplayRegressionCaseResult],
) -> V1ReplayRegressionMetrics:
    total_cases = len(case_results)
    live_action_count = sum(1 for case in case_results if case.emitted_action)
    live_no_action_count = total_cases - live_action_count
    return V1ReplayRegressionMetrics(
        total_cases=total_cases,
        live_action_count=live_action_count,
        live_no_action_count=live_no_action_count,
        unresolved_planner_no_action_count=sum(
            1 for case in case_results if case.unresolved_planner_no_action
        ),
        reduced_active_owner_caveat_count=sum(
            1 for case in case_results if case.reduced_active_owner_caveat
        ),
        owned_production_pressure_coverage_count=sum(
            1 for case in case_results if case.owned_production_pressure
        ),
        own_transfer_spam_coverage_count=sum(
            1 for case in case_results if case.own_transfer_spam
        ),
        enemy_denial_safety_blocked_count=sum(
            1 for case in case_results if case.enemy_denial_safety_blocked
        ),
        four_player_plateau_action_count=sum(
            1
            for case in case_results
            if case.four_player_plateau and case.emitted_action
        ),
        four_player_plateau_no_action_count=sum(
            1
            for case in case_results
            if case.four_player_plateau and not case.emitted_action
        ),
        rank_aware_continuation_count=sum(
            1 for case in case_results if case.rank_aware_continuation
        ),
        thin_capture_risk_count=sum(
            1 for case in case_results if case.thin_capture_risk
        ),
        budget_guarded_no_action_count=sum(
            1 for case in case_results if case.budget_guarded_no_action
        ),
    )


def _summary_text(metrics: V1ReplayRegressionMetrics) -> str:
    return (
        "v1_replay_regression "
        f"cases={metrics.total_cases} "
        f"live_actions={metrics.live_action_count} "
        f"live_no_actions={metrics.live_no_action_count} "
        f"unresolved_planner_no_actions={metrics.unresolved_planner_no_action_count} "
        f"reduced_active_owner_caveats={metrics.reduced_active_owner_caveat_count} "
        f"owned_pressure={metrics.owned_production_pressure_coverage_count} "
        f"own_transfer_spam={metrics.own_transfer_spam_coverage_count} "
        f"enemy_denial_safety_blocked={metrics.enemy_denial_safety_blocked_count} "
        f"four_player_plateau_actions={metrics.four_player_plateau_action_count} "
        f"four_player_plateau_no_actions={metrics.four_player_plateau_no_action_count} "
        f"rank_aware_continuations={metrics.rank_aware_continuation_count} "
        f"thin_capture_risks={metrics.thin_capture_risk_count}"
    )


def _case_labels(
    *,
    owned_production_pressure: bool,
    own_transfer_spam: bool,
    high_value_enemy_denial: bool,
    enemy_denial_safety_blocked: bool,
    four_player_plateau: bool,
    four_player_action_emitting_plateau: bool,
    four_player_no_action_plateau: bool,
    reduced_active_owner_caveat: bool,
    rank_aware_continuation: bool,
    thin_capture_risk: bool,
    budget_guarded_no_action: bool,
) -> tuple[str, ...]:
    labels: list[str] = []
    if owned_production_pressure:
        labels.append("owned_production_pressure")
    if own_transfer_spam:
        labels.append("own_transfer_spam")
    if high_value_enemy_denial:
        labels.append("high_value_enemy_denial")
    if enemy_denial_safety_blocked:
        labels.append("enemy_denial_safety_blocked")
    if four_player_plateau:
        labels.append("four_player_plateau")
    if four_player_action_emitting_plateau:
        labels.append("action_emitting_plateau")
    if four_player_no_action_plateau:
        labels.append("candidate_backlog_no_action")
    if reduced_active_owner_caveat:
        labels.append("reduced_active_owner_live_2p_dispatch_caveat")
    if rank_aware_continuation:
        labels.append("rank_aware_continuation")
    if thin_capture_risk:
        labels.append("thin_capture_risk")
    if budget_guarded_no_action:
        labels.append("budget_guarded_no_action")
    return tuple(labels)


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


def _int_metadata(
    metadata: Mapping[str, str],
    key: str,
    fallback: object | None = None,
) -> int:
    value = metadata.get(key, fallback)
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


__all__ = (
    "V1ReplayRegressionCaseResult",
    "V1ReplayRegressionMetrics",
    "V1ReplayRegressionReport",
    "default_v1_replay_fixture_dir",
    "run_v1_replay_regression",
)
