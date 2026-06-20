"""Runtime default configuration derivation.

Runtime / Submission Cycle 6 converts Kaggle observation/configuration inputs
into a safe ``RuntimeTurnConfig``. The builder is intentionally thin: it only
derives the per-turn budget guard and leaves observation parsing to the safe
runtime turn boundary.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from numbers import Real

from ow_planner import (
    CandidateGenerationConfig,
    FourPlayerSelectionConfig,
    StrategyDispatchConfig,
    TwoPlayerSelectionConfig,
)

from .runtime_planner import RuntimePlannerConfig
from .runtime_budget import RuntimeBudgetConfig
from .runtime_turn import RuntimeTurnConfig


@dataclass(frozen=True, slots=True)
class RuntimeDefaultConfig:
    """Defaults for constructing runtime turn configuration."""

    default_turn_budget_seconds: float = 1.0
    minimum_stage_start_seconds: float = 0.05
    remaining_overage_reserve_seconds: float = 0.25
    runtime_max_candidates: int | None = 8
    runtime_max_validation_attempts: int | None = 8
    runtime_minimum_total_score: float = -100.0
    clock: Callable[[], float] = time.monotonic

    def __post_init__(self) -> None:
        _validate_nonnegative_number(
            self.default_turn_budget_seconds,
            "default_turn_budget_seconds",
        )
        _validate_nonnegative_number(
            self.minimum_stage_start_seconds,
            "minimum_stage_start_seconds",
        )
        _validate_nonnegative_number(
            self.remaining_overage_reserve_seconds,
            "remaining_overage_reserve_seconds",
        )
        _validate_optional_nonnegative_int(
            self.runtime_max_candidates,
            "runtime_max_candidates",
        )
        _validate_optional_nonnegative_int(
            self.runtime_max_validation_attempts,
            "runtime_max_validation_attempts",
        )
        _validate_finite_number(
            self.runtime_minimum_total_score,
            "runtime_minimum_total_score",
        )
        if not callable(self.clock):
            raise ValueError("clock must be callable")


def runtime_turn_config_for_observation(
    observation: Mapping[str, object],
    configuration: object | None = None,
    defaults: RuntimeDefaultConfig | None = None,
) -> RuntimeTurnConfig:
    """Build the safe runtime turn config for a Kaggle call."""

    _ = configuration
    effective_defaults = RuntimeDefaultConfig() if defaults is None else defaults
    turn_budget_seconds = effective_defaults.default_turn_budget_seconds
    remaining_overage_time = _numeric_remaining_overage_time(observation)

    if remaining_overage_time is not None:
        usable_remaining_time = max(
            0.0,
            remaining_overage_time
            - effective_defaults.remaining_overage_reserve_seconds,
        )
        turn_budget_seconds = min(turn_budget_seconds, usable_remaining_time)

    return RuntimeTurnConfig(
        planner_config=RuntimePlannerConfig(
            candidate_config=CandidateGenerationConfig(
                max_candidates=effective_defaults.runtime_max_candidates,
                max_validation_attempts=(
                    effective_defaults.runtime_max_validation_attempts
                ),
            ),
            strategy_dispatch_config=StrategyDispatchConfig(
                two_player_config=TwoPlayerSelectionConfig(
                    minimum_total_score=(
                        effective_defaults.runtime_minimum_total_score
                    ),
                ),
                four_player_config=FourPlayerSelectionConfig(
                    minimum_total_score=(
                        effective_defaults.runtime_minimum_total_score
                    ),
                ),
            ),
        ),
        budget_config=RuntimeBudgetConfig(
            turn_budget_seconds=turn_budget_seconds,
            minimum_stage_start_seconds=(
                effective_defaults.minimum_stage_start_seconds
            ),
            clock=effective_defaults.clock,
        ),
    )


def _numeric_remaining_overage_time(observation: object) -> float | None:
    if not isinstance(observation, Mapping):
        return None

    value = observation.get("remainingOverageTime")
    if isinstance(value, bool) or not isinstance(value, Real):
        return None

    numeric_value = float(value)
    if not math.isfinite(numeric_value):
        return None
    return numeric_value


def _validate_nonnegative_number(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a non-negative number")

    numeric_value = float(value)
    if not math.isfinite(numeric_value) or numeric_value < 0.0:
        raise ValueError(f"{name} must be a non-negative number")


def _validate_finite_number(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite number")

    if not math.isfinite(float(value)):
        raise ValueError(f"{name} must be a finite number")


def _validate_optional_nonnegative_int(value: object, name: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be None or an integer >= 0")


__all__ = (
    "RuntimeDefaultConfig",
    "runtime_turn_config_for_observation",
)
