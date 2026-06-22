"""Safe runtime turn orchestration.

Runtime / Submission Cycle 4 composes observation parsing, planner pipeline
execution, and action conversion behind a non-crashing turn boundary. Errors
are represented in ``RuntimeTurnResult`` and fall back to fresh no-action
lists. Cycle 5 adds deterministic stage-start budget checks without
interrupting work after a stage begins.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from ow_planner.actions import KaggleActionRow
from ow_sim.state import GameState

from .runtime_budget import (
    RuntimeBudgetCheck,
    RuntimeBudgetConfig,
    RuntimeBudgetStatus,
    runtime_budget_check,
    start_runtime_budget,
)
from .runtime_actions import planner_result_to_actions
from .runtime_planner import (
    RuntimePlannerConfig,
    RuntimePlannerResult,
    run_planner_pipeline,
)
from .runtime_state import observation_to_game_state


class RuntimeTurnStatus(str, Enum):
    """Runtime turn lifecycle status."""

    ACTIONS = "actions"
    NO_ACTION = "no_action"
    PARSE_ERROR = "parse_error"
    PLANNER_ERROR = "planner_error"
    ACTION_ERROR = "action_error"
    LOW_BUDGET = "low_budget"
    BUDGET_EXHAUSTED = "budget_exhausted"


@dataclass(frozen=True, slots=True)
class RuntimeTurnConfig:
    """Configuration for safe runtime turn orchestration."""

    planner_config: RuntimePlannerConfig | None = None
    budget_config: RuntimeBudgetConfig | None = None


@dataclass(frozen=True, slots=True)
class RuntimeTurnResult:
    """Structured runtime turn result with safe fallback details."""

    actions: list[KaggleActionRow]
    status: RuntimeTurnStatus
    state: GameState | None = None
    planner_result: RuntimePlannerResult | None = None
    budget_check: RuntimeBudgetCheck | None = None
    error: str | None = None
    notes: tuple[str, ...] = ()


_LAST_RUNTIME_DIAGNOSTIC_METADATA: tuple[tuple[str, str], ...] = ()


def run_runtime_turn(
    observation: Mapping[str, object],
    configuration: object | None = None,
    config: RuntimeTurnConfig | None = None,
) -> RuntimeTurnResult:
    """Safely run one parsed-planner-action turn from a Kaggle observation."""

    _ = configuration
    effective_config = RuntimeTurnConfig() if config is None else config
    budget = start_runtime_budget(effective_config.budget_config)

    budget_check = runtime_budget_check(budget, "parse")
    if not budget_check.can_start:
        return _budget_guard_result(budget_check)

    try:
        state = observation_to_game_state(observation)
    except Exception as exc:
        return RuntimeTurnResult(
            actions=[],
            status=RuntimeTurnStatus.PARSE_ERROR,
            budget_check=budget_check,
            error=_error_text(exc),
            notes=("parse error",),
        )

    budget_check = runtime_budget_check(budget, "planner")
    if not budget_check.can_start:
        return _budget_guard_result(budget_check, state=state)

    try:
        planner_result = run_planner_pipeline(state, effective_config.planner_config)
    except Exception as exc:
        return RuntimeTurnResult(
            actions=[],
            status=RuntimeTurnStatus.PLANNER_ERROR,
            state=state,
            budget_check=budget_check,
            error=_error_text(exc),
            notes=("planner error",),
        )

    budget_check = runtime_budget_check(budget, "action conversion")
    if not budget_check.can_start:
        return _budget_guard_result(
            budget_check,
            state=state,
            planner_result=planner_result,
        )

    try:
        raw_actions = planner_result_to_actions(planner_result)
    except Exception as exc:
        return RuntimeTurnResult(
            actions=[],
            status=RuntimeTurnStatus.ACTION_ERROR,
            state=state,
            planner_result=planner_result,
            budget_check=budget_check,
            error=_error_text(exc),
            notes=("action error",),
        )

    actions = [list(action) for action in raw_actions]
    status = RuntimeTurnStatus.ACTIONS if actions else RuntimeTurnStatus.NO_ACTION
    return RuntimeTurnResult(
        actions=actions,
        status=status,
        state=state,
        planner_result=planner_result,
        budget_check=budget_check,
        notes=("actions",) if actions else ("no action",),
    )


def safe_actions_for_observation(
    observation: Mapping[str, object],
    configuration: object | None = None,
    config: RuntimeTurnConfig | None = None,
) -> list[KaggleActionRow]:
    """Return only safe Kaggle action rows for a runtime observation."""

    result = run_runtime_turn(observation, configuration, config)
    _record_runtime_diagnostic_metadata(result)
    return result.actions


def last_runtime_diagnostic_metadata() -> tuple[tuple[str, str], ...]:
    """Return diagnostic metadata for the most recent safe runtime turn."""

    return _LAST_RUNTIME_DIAGNOSTIC_METADATA


def _error_text(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


def _budget_guard_result(
    budget_check: RuntimeBudgetCheck,
    *,
    state: GameState | None = None,
    planner_result: RuntimePlannerResult | None = None,
) -> RuntimeTurnResult:
    status = (
        RuntimeTurnStatus.BUDGET_EXHAUSTED
        if budget_check.status is RuntimeBudgetStatus.EXHAUSTED
        else RuntimeTurnStatus.LOW_BUDGET
    )
    note = budget_check.note or f"budget unavailable before {budget_check.stage}"
    return RuntimeTurnResult(
        actions=[],
        status=status,
        state=state,
        planner_result=planner_result,
        budget_check=budget_check,
        error=note,
        notes=(note,),
    )


def _record_runtime_diagnostic_metadata(result: RuntimeTurnResult) -> None:
    global _LAST_RUNTIME_DIAGNOSTIC_METADATA
    _LAST_RUNTIME_DIAGNOSTIC_METADATA = _runtime_diagnostic_metadata(result)


def _runtime_diagnostic_metadata(
    result: RuntimeTurnResult,
) -> tuple[tuple[str, str], ...]:
    planner_result = result.planner_result
    metadata: list[tuple[str, str]] = [
        ("runtime_diagnostic_status", result.status.value),
        ("runtime_diagnostic_no_action_reason", _no_action_reason(result)),
        ("runtime_diagnostic_action_count", str(len(result.actions))),
    ]
    if result.error is not None:
        metadata.append(("runtime_diagnostic_error", result.error))
    if result.budget_check is not None:
        metadata.extend(
            (
                ("runtime_diagnostic_budget_stage", result.budget_check.stage),
                (
                    "runtime_diagnostic_budget_status",
                    result.budget_check.status.value,
                ),
            )
        )

    if planner_result is not None:
        metadata.extend(
            (
                (
                    "runtime_diagnostic_candidate_count",
                    str(len(planner_result.candidates)),
                ),
                (
                    "runtime_diagnostic_evaluation_count",
                    str(len(planner_result.evaluations)),
                ),
                (
                    "runtime_diagnostic_response_evaluation_count",
                    str(len(planner_result.response_evaluations)),
                ),
                (
                    "runtime_diagnostic_commitment_candidate_count",
                    str(len(planner_result.commitment_options)),
                ),
                (
                    "runtime_diagnostic_commitment_option_count",
                    str(_commitment_option_count(planner_result)),
                ),
                (
                    "runtime_diagnostic_validated_commitment_count",
                    str(_commitment_status_count(planner_result, "validated")),
                ),
                (
                    "runtime_diagnostic_rejected_commitment_count",
                    str(_commitment_status_count(planner_result, "rejected")),
                ),
                ("runtime_diagnostic_bundle_count", str(len(planner_result.bundles))),
                (
                    "runtime_diagnostic_selection_status",
                    planner_result.selection.status.value,
                ),
                (
                    "runtime_diagnostic_selection_notes",
                    "|".join(planner_result.selection.notes),
                ),
            )
        )
        selected_commitment = planner_result.selection.selected_commitment_option
        if selected_commitment is not None:
            metadata.extend(
                (
                    (
                        "runtime_diagnostic_selected_commitment_type",
                        selected_commitment.option_type.value,
                    ),
                    (
                        "runtime_diagnostic_selected_commitment_status",
                        selected_commitment.status.value,
                    ),
                    (
                        "runtime_diagnostic_selected_commitment_launch_count",
                        str(len(selected_commitment.launches)),
                    ),
                )
            )
    return tuple(metadata)


def _no_action_reason(result: RuntimeTurnResult) -> str:
    if result.status is RuntimeTurnStatus.ACTIONS:
        return "actions_emitted"
    if result.status is RuntimeTurnStatus.PARSE_ERROR:
        return "runtime_parse_error"
    if result.status is RuntimeTurnStatus.PLANNER_ERROR:
        return "runtime_planner_error"
    if result.status is RuntimeTurnStatus.ACTION_ERROR:
        return "runtime_action_conversion_error"
    if result.status in (RuntimeTurnStatus.LOW_BUDGET, RuntimeTurnStatus.BUDGET_EXHAUSTED):
        return f"budget_guard_{result.status.value}"

    planner_result = result.planner_result
    if planner_result is None:
        return "no_planner_result"
    if not planner_result.candidates:
        if _has_no_owned_planets(result.state):
            return "no_owned_planets"
        return "no_candidates_generated"
    if not planner_result.evaluations or not planner_result.bundles:
        return "candidates_generated_but_missing_evaluation_or_bundles"

    selection = planner_result.selection
    if selection.status.value in ("rejected", "no_action"):
        return f"strategy_selection_{selection.status.value}"

    selected_commitment = selection.selected_commitment_option
    if selected_commitment is None:
        return "selected_commitment_missing"
    if selected_commitment.status.value != "validated":
        return "selected_commitment_not_validated"
    if selected_commitment.option_type.value == "no_attack":
        return "strategy_selected_no_attack"
    if not selected_commitment.launches:
        return "selected_commitment_has_no_launches"
    return "action_conversion_produced_no_actions"


def _commitment_option_count(result: RuntimePlannerResult) -> int:
    return sum(
        len(candidate_options.options)
        for candidate_options in result.commitment_options
    )


def _commitment_status_count(result: RuntimePlannerResult, status: str) -> int:
    return sum(
        1
        for candidate_options in result.commitment_options
        for option in candidate_options.options
        if option.status.value == status
    )


def _has_no_owned_planets(state: GameState | None) -> bool:
    if state is None or state.player_id is None:
        return False
    return not any(planet.owner == state.player_id for planet in state.planets)


__all__ = (
    "RuntimeTurnConfig",
    "RuntimeTurnResult",
    "RuntimeTurnStatus",
    "last_runtime_diagnostic_metadata",
    "run_runtime_turn",
    "safe_actions_for_observation",
)
