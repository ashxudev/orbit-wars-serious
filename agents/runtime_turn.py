"""Safe runtime turn orchestration.

Runtime / Submission Cycle 4 composes observation parsing, planner pipeline
execution, and action conversion behind a non-crashing turn boundary. Errors
are represented in ``RuntimeTurnResult`` and fall back to fresh no-action
lists.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from ow_planner.actions import KaggleActionRow
from ow_sim.state import GameState

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


@dataclass(frozen=True, slots=True)
class RuntimeTurnConfig:
    """Configuration for safe runtime turn orchestration."""

    planner_config: RuntimePlannerConfig | None = None


@dataclass(frozen=True, slots=True)
class RuntimeTurnResult:
    """Structured runtime turn result with safe fallback details."""

    actions: list[KaggleActionRow]
    status: RuntimeTurnStatus
    state: GameState | None = None
    planner_result: RuntimePlannerResult | None = None
    error: str | None = None
    notes: tuple[str, ...] = ()


def run_runtime_turn(
    observation: Mapping[str, object],
    configuration: object | None = None,
    config: RuntimeTurnConfig | None = None,
) -> RuntimeTurnResult:
    """Safely run one parsed-planner-action turn from a Kaggle observation."""

    _ = configuration
    effective_config = RuntimeTurnConfig() if config is None else config

    try:
        state = observation_to_game_state(observation)
    except Exception as exc:
        return RuntimeTurnResult(
            actions=[],
            status=RuntimeTurnStatus.PARSE_ERROR,
            error=_error_text(exc),
            notes=("parse error",),
        )

    try:
        planner_result = run_planner_pipeline(state, effective_config.planner_config)
    except Exception as exc:
        return RuntimeTurnResult(
            actions=[],
            status=RuntimeTurnStatus.PLANNER_ERROR,
            state=state,
            error=_error_text(exc),
            notes=("planner error",),
        )

    try:
        raw_actions = planner_result_to_actions(planner_result)
    except Exception as exc:
        return RuntimeTurnResult(
            actions=[],
            status=RuntimeTurnStatus.ACTION_ERROR,
            state=state,
            planner_result=planner_result,
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
        notes=("actions",) if actions else ("no action",),
    )


def safe_actions_for_observation(
    observation: Mapping[str, object],
    configuration: object | None = None,
    config: RuntimeTurnConfig | None = None,
) -> list[KaggleActionRow]:
    """Return only safe Kaggle action rows for a runtime observation."""

    return run_runtime_turn(observation, configuration, config).actions


def _error_text(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


__all__ = (
    "RuntimeTurnConfig",
    "RuntimeTurnResult",
    "RuntimeTurnStatus",
    "run_runtime_turn",
    "safe_actions_for_observation",
)
