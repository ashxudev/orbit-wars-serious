"""Deterministic regression report for compact V0 replay leak fixtures.

This module is measurement-only. It runs the committed single-observation
fixtures through the current runtime path and a budgetless probe, then
summarizes whether the known V0 leak classes still reproduce locally.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from agents.runtime_config import runtime_turn_config_for_observation
from agents.runtime_planner import RuntimePlannerConfig, run_planner_pipeline
from agents.runtime_state import observation_to_game_state
from agents.runtime_turn import (
    RuntimeTurnConfig,
    last_runtime_diagnostic_metadata,
    safe_actions_for_observation,
)
from ow_planner import (
    CandidateGenerationConfig,
    FourPlayerSelectionConfig,
    MissionType,
    StrategyDispatchConfig,
    TwoPlayerSelectionConfig,
)
from ow_planner.commitment import CommitmentOptionType
from ow_planner.two_player_strategy import two_player_advantage_facts

PRESSURE_OR_RETENTION_LEAK_CLASSES = frozenset(
    ("two_player_pressure_collapse", "capture_hold_failure")
)
RISKY_CAPTURE_MISSION_TYPES = frozenset(
    (MissionType.CAPTURE_NEUTRAL.value, MissionType.ATTACK_ENEMY.value)
)
RETENTION_MISSION_TYPES = frozenset(
    (MissionType.DEFEND_OWN.value, MissionType.REINFORCE.value)
)
CONSERVATIVE_COMMITMENT_TYPES = frozenset(
    (
        CommitmentOptionType.RESERVE_PRESERVING.value,
        CommitmentOptionType.CAPTURE_AND_HOLD.value,
    )
)
CAPTURE_HOLD_RISK_LABELS = frozenset(
    ("target_reinforcement_feasible", "target_race_risk")
)
BUDGET_GUARD_REASONS = frozenset(
    ("budget_guard_budget_exhausted", "budget_guard_low_budget")
)


@dataclass(frozen=True, slots=True)
class V0ReplayRegressionCaseResult:
    """One replay fixture runtime/probe result."""

    fixture_name: str
    case_id: str
    leak_class: str
    player_count: int
    player_id: int
    turn: int
    runtime_mode: str
    live_action_count: int
    live_status: str
    live_no_action_reason: str
    live_budget_status: str | None
    budgetless_action_count: int
    budgetless_status: str
    budgetless_no_action_reason: str
    budgetless_budget_status: str | None
    budgetless_candidate_count: int
    selected_mission_type: str | None
    selected_commitment_type: str | None
    selected_source_planet_ids: tuple[int, ...]
    selected_target_planet_id: int | None
    response_labels: tuple[str, ...]
    pressure_or_retention_case: bool
    conservative_budgetless_action: bool
    budget_guarded_no_action: bool
    risky_thin_capture_proxy: bool

    @property
    def live_emitted_action(self) -> bool:
        return self.live_action_count > 0

    @property
    def budgetless_emitted_action(self) -> bool:
        return self.budgetless_action_count > 0

    def to_dict(self) -> dict[str, object]:
        return {
            "budget_guarded_no_action": self.budget_guarded_no_action,
            "budgetless_action_count": self.budgetless_action_count,
            "budgetless_budget_status": self.budgetless_budget_status,
            "budgetless_candidate_count": self.budgetless_candidate_count,
            "budgetless_emitted_action": self.budgetless_emitted_action,
            "budgetless_no_action_reason": self.budgetless_no_action_reason,
            "budgetless_status": self.budgetless_status,
            "case_id": self.case_id,
            "conservative_budgetless_action": self.conservative_budgetless_action,
            "fixture_name": self.fixture_name,
            "leak_class": self.leak_class,
            "live_action_count": self.live_action_count,
            "live_budget_status": self.live_budget_status,
            "live_emitted_action": self.live_emitted_action,
            "live_no_action_reason": self.live_no_action_reason,
            "live_status": self.live_status,
            "player_count": self.player_count,
            "player_id": self.player_id,
            "pressure_or_retention_case": self.pressure_or_retention_case,
            "response_labels": list(self.response_labels),
            "risky_thin_capture_proxy": self.risky_thin_capture_proxy,
            "runtime_mode": self.runtime_mode,
            "selected_commitment_type": self.selected_commitment_type,
            "selected_mission_type": self.selected_mission_type,
            "selected_source_planet_ids": list(self.selected_source_planet_ids),
            "selected_target_planet_id": self.selected_target_planet_id,
            "turn": self.turn,
        }


@dataclass(frozen=True, slots=True)
class V0ReplayRegressionMetrics:
    """Aggregate fixture leak metrics."""

    total_cases: int
    live_action_count: int
    live_action_rate: float
    live_no_action_count: int
    live_max_no_action_streak: int
    budget_guarded_no_action_count: int
    budgetless_action_count: int
    budgetless_action_rate: float
    pressure_retention_case_count: int
    pressure_retention_budgetless_action_count: int
    pressure_retention_budgetless_action_rate: float
    conservative_pressure_retention_action_count: int
    risky_thin_capture_proxy_count: int
    unresolved_planner_no_action_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "budget_guarded_no_action_count": self.budget_guarded_no_action_count,
            "budgetless_action_count": self.budgetless_action_count,
            "budgetless_action_rate": self.budgetless_action_rate,
            "conservative_pressure_retention_action_count": (
                self.conservative_pressure_retention_action_count
            ),
            "live_action_count": self.live_action_count,
            "live_action_rate": self.live_action_rate,
            "live_max_no_action_streak": self.live_max_no_action_streak,
            "live_no_action_count": self.live_no_action_count,
            "pressure_retention_budgetless_action_count": (
                self.pressure_retention_budgetless_action_count
            ),
            "pressure_retention_budgetless_action_rate": (
                self.pressure_retention_budgetless_action_rate
            ),
            "pressure_retention_case_count": self.pressure_retention_case_count,
            "risky_thin_capture_proxy_count": self.risky_thin_capture_proxy_count,
            "total_cases": self.total_cases,
            "unresolved_planner_no_action_count": (
                self.unresolved_planner_no_action_count
            ),
        }


@dataclass(frozen=True, slots=True)
class V0ReplayRegressionReport:
    """Deterministic V0 replay leak regression report."""

    fixture_dir: str
    case_results: tuple[V0ReplayRegressionCaseResult, ...]
    metrics: V0ReplayRegressionMetrics
    summary_text: str

    def to_dict(self) -> dict[str, object]:
        return {
            "case_results": [case.to_dict() for case in self.case_results],
            "fixture_dir": self.fixture_dir,
            "metrics": self.metrics.to_dict(),
            "summary_text": self.summary_text,
        }


def default_v0_replay_fixture_dir() -> Path:
    """Return the committed compact V0 replay leak fixture directory."""

    return Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "v0_replay_leaks"


def run_v0_replay_regression(
    fixture_dir: str | Path | None = None,
) -> V0ReplayRegressionReport:
    """Run all compact V0 replay fixtures and return a deterministic report."""

    resolved_fixture_dir = (
        default_v0_replay_fixture_dir() if fixture_dir is None else Path(fixture_dir)
    )
    paths = tuple(sorted(resolved_fixture_dir.glob("*.json")))
    if not paths:
        raise ValueError(f"no V0 replay leak fixtures found in {resolved_fixture_dir}")

    case_results = tuple(_run_case(path) for path in paths)
    metrics = _summarize_case_results(case_results)
    summary_text = _summary_text(metrics)
    return V0ReplayRegressionReport(
        fixture_dir=str(resolved_fixture_dir),
        case_results=case_results,
        metrics=metrics,
        summary_text=summary_text,
    )


def _run_case(path: Path) -> V0ReplayRegressionCaseResult:
    payload = _read_payload(path)
    observation = _required_mapping(payload, "observation")
    expected_runtime = _required_mapping(payload, "expected_current_runtime")
    case_id = _required_str(payload, "case_id")
    leak_class = _required_str(payload, "leak_class")
    player_count = _required_int(payload, "player_count")
    turn = _required_int(payload, "turn")
    runtime_mode = _required_str(expected_runtime, "runtime_mode")

    state = observation_to_game_state(observation)
    player_id = _required_player_id(state.player_id, path)

    live_config = (
        runtime_turn_config_for_observation(observation, {})
        if runtime_mode == "bounded"
        else None
    )
    live_actions = safe_actions_for_observation(observation, {}, live_config)
    live_metadata = dict(last_runtime_diagnostic_metadata())

    budgetless_config = _budgetless_runtime_config()
    budgetless_actions = safe_actions_for_observation(observation, {}, budgetless_config)
    budgetless_metadata = dict(last_runtime_diagnostic_metadata())
    planner_metadata = _planner_selection_metadata(observation, budgetless_config)

    pressure_or_retention_case = _pressure_or_retention_case(
        leak_class,
        planner_metadata.response_labels,
        planner_metadata.selected_mission_type,
    )
    risky_thin_capture_proxy = _risky_thin_capture_proxy(
        planner_metadata.selected_mission_type,
        planner_metadata.selected_commitment_type,
        planner_metadata.response_labels,
    )
    conservative_budgetless_action = (
        len(budgetless_actions) > 0
        and pressure_or_retention_case
        and not risky_thin_capture_proxy
        and (
            planner_metadata.selected_commitment_type in CONSERVATIVE_COMMITMENT_TYPES
            or planner_metadata.selected_mission_type in RETENTION_MISSION_TYPES
        )
    )
    live_no_action_reason = live_metadata.get("runtime_diagnostic_no_action_reason", "")
    budget_guarded_no_action = (
        len(live_actions) == 0 and live_no_action_reason in BUDGET_GUARD_REASONS
    )

    return V0ReplayRegressionCaseResult(
        fixture_name=path.name,
        case_id=case_id,
        leak_class=leak_class,
        player_count=player_count,
        player_id=player_id,
        turn=turn,
        runtime_mode=runtime_mode,
        live_action_count=len(live_actions),
        live_status=live_metadata.get("runtime_diagnostic_status", ""),
        live_no_action_reason=live_no_action_reason,
        live_budget_status=live_metadata.get("runtime_diagnostic_budget_status"),
        budgetless_action_count=len(budgetless_actions),
        budgetless_status=budgetless_metadata.get("runtime_diagnostic_status", ""),
        budgetless_no_action_reason=budgetless_metadata.get(
            "runtime_diagnostic_no_action_reason",
            "",
        ),
        budgetless_budget_status=budgetless_metadata.get(
            "runtime_diagnostic_budget_status",
        ),
        budgetless_candidate_count=_int_metadata(
            budgetless_metadata,
            "runtime_diagnostic_candidate_count",
        ),
        selected_mission_type=planner_metadata.selected_mission_type,
        selected_commitment_type=planner_metadata.selected_commitment_type,
        selected_source_planet_ids=planner_metadata.selected_source_planet_ids,
        selected_target_planet_id=planner_metadata.selected_target_planet_id,
        response_labels=planner_metadata.response_labels,
        pressure_or_retention_case=pressure_or_retention_case,
        conservative_budgetless_action=conservative_budgetless_action,
        budget_guarded_no_action=budget_guarded_no_action,
        risky_thin_capture_proxy=risky_thin_capture_proxy,
    )


@dataclass(frozen=True, slots=True)
class _PlannerSelectionMetadata:
    selected_mission_type: str | None
    selected_commitment_type: str | None
    selected_source_planet_ids: tuple[int, ...]
    selected_target_planet_id: int | None
    response_labels: tuple[str, ...]


def _planner_selection_metadata(
    observation: Mapping[str, object],
    config: RuntimeTurnConfig,
) -> _PlannerSelectionMetadata:
    state = observation_to_game_state(observation)
    planner_result = run_planner_pipeline(state, config.planner_config)
    selection = planner_result.selection
    selected_bundle = selection.selected_bundle
    selected_commitment = selection.selected_commitment_option
    selected_mission_type = None
    selected_source_planet_ids: tuple[int, ...] = ()
    selected_target_planet_id = None
    response_labels: tuple[str, ...] = ()
    if selected_bundle is not None:
        selected_mission_type = selected_bundle.candidate.mission_type.value
        selected_source_planet_ids = selected_bundle.candidate.source_planet_ids
        selected_target_planet_id = selected_bundle.candidate.target_planet_id
        response_labels = two_player_advantage_facts(selected_bundle).response_labels
    selected_commitment_type = (
        None if selected_commitment is None else selected_commitment.option_type.value
    )
    return _PlannerSelectionMetadata(
        selected_mission_type=selected_mission_type,
        selected_commitment_type=selected_commitment_type,
        selected_source_planet_ids=selected_source_planet_ids,
        selected_target_planet_id=selected_target_planet_id,
        response_labels=response_labels,
    )


def _budgetless_runtime_config() -> RuntimeTurnConfig:
    return RuntimeTurnConfig(
        planner_config=RuntimePlannerConfig(
            candidate_config=CandidateGenerationConfig(
                max_candidates=8,
                max_validation_attempts=8,
            ),
            strategy_dispatch_config=StrategyDispatchConfig(
                two_player_config=TwoPlayerSelectionConfig(minimum_total_score=-100.0),
                four_player_config=FourPlayerSelectionConfig(minimum_total_score=-100.0),
            ),
        ),
    )


def _summarize_case_results(
    case_results: Sequence[V0ReplayRegressionCaseResult],
) -> V0ReplayRegressionMetrics:
    total_cases = len(case_results)
    live_action_count = sum(1 for case in case_results if case.live_emitted_action)
    live_no_action_count = total_cases - live_action_count
    budgetless_action_count = sum(
        1 for case in case_results if case.budgetless_emitted_action
    )
    pressure_cases = tuple(case for case in case_results if case.pressure_or_retention_case)
    pressure_action_count = sum(
        1 for case in pressure_cases if case.budgetless_emitted_action
    )
    conservative_pressure_action_count = sum(
        1 for case in pressure_cases if case.conservative_budgetless_action
    )
    budget_guarded_no_action_count = sum(
        1 for case in case_results if case.budget_guarded_no_action
    )
    risky_thin_capture_proxy_count = sum(
        1 for case in case_results if case.risky_thin_capture_proxy
    )
    unresolved_planner_no_action_count = sum(
        1
        for case in case_results
        if not case.budgetless_emitted_action and not case.budget_guarded_no_action
    )
    return V0ReplayRegressionMetrics(
        total_cases=total_cases,
        live_action_count=live_action_count,
        live_action_rate=_rate(live_action_count, total_cases),
        live_no_action_count=live_no_action_count,
        live_max_no_action_streak=_max_no_action_streak(case_results),
        budget_guarded_no_action_count=budget_guarded_no_action_count,
        budgetless_action_count=budgetless_action_count,
        budgetless_action_rate=_rate(budgetless_action_count, total_cases),
        pressure_retention_case_count=len(pressure_cases),
        pressure_retention_budgetless_action_count=pressure_action_count,
        pressure_retention_budgetless_action_rate=_rate(
            pressure_action_count,
            len(pressure_cases),
        ),
        conservative_pressure_retention_action_count=(
            conservative_pressure_action_count
        ),
        risky_thin_capture_proxy_count=risky_thin_capture_proxy_count,
        unresolved_planner_no_action_count=unresolved_planner_no_action_count,
    )


def _max_no_action_streak(
    case_results: Sequence[V0ReplayRegressionCaseResult],
) -> int:
    longest = 0
    current = 0
    for case in case_results:
        if case.live_emitted_action:
            current = 0
            continue
        current += 1
        longest = max(longest, current)
    return longest


def _summary_text(metrics: V0ReplayRegressionMetrics) -> str:
    return (
        "v0_replay_regression "
        f"cases={metrics.total_cases} "
        f"live_actions={metrics.live_action_count} "
        f"live_no_actions={metrics.live_no_action_count} "
        f"budget_guarded={metrics.budget_guarded_no_action_count} "
        f"budgetless_actions={metrics.budgetless_action_count} "
        f"pressure_actions={metrics.pressure_retention_budgetless_action_count} "
        f"risky_thin_captures={metrics.risky_thin_capture_proxy_count} "
        f"unresolved_planner_no_actions={metrics.unresolved_planner_no_action_count}"
    )


def _pressure_or_retention_case(
    leak_class: str,
    response_labels: Sequence[str],
    selected_mission_type: str | None,
) -> bool:
    _ = response_labels
    if leak_class in PRESSURE_OR_RETENTION_LEAK_CLASSES:
        return True
    if selected_mission_type in RETENTION_MISSION_TYPES:
        return True
    return False


def _risky_thin_capture_proxy(
    selected_mission_type: str | None,
    selected_commitment_type: str | None,
    response_labels: Sequence[str],
) -> bool:
    if selected_mission_type not in RISKY_CAPTURE_MISSION_TYPES:
        return False
    if not any(label in CAPTURE_HOLD_RISK_LABELS for label in response_labels):
        return False
    return selected_commitment_type not in CONSERVATIVE_COMMITMENT_TYPES


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
    "V0ReplayRegressionCaseResult",
    "V0ReplayRegressionMetrics",
    "V0ReplayRegressionReport",
    "default_v0_replay_fixture_dir",
    "run_v0_replay_regression",
)
