"""Deterministic runtime turn budget primitives.

Runtime / Submission Cycle 5 adds an injectable-clock timing boundary for
checking whether there is enough budget left before starting each runtime
stage. It does not interrupt stages that are already running.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from numbers import Real


class RuntimeBudgetStatus(str, Enum):
    """Stage-start budget availability status."""

    DISABLED = "disabled"
    AVAILABLE = "available"
    LOW_BUDGET = "low_budget"
    EXHAUSTED = "exhausted"


@dataclass(frozen=True, slots=True)
class RuntimeBudgetConfig:
    """Configuration for per-turn budget checks."""

    turn_budget_seconds: float | None = None
    minimum_stage_start_seconds: float = 0.0
    clock: Callable[[], float] = time.monotonic

    def __post_init__(self) -> None:
        if self.turn_budget_seconds is not None:
            _validate_nonnegative_seconds(
                self.turn_budget_seconds,
                "turn_budget_seconds",
            )
        _validate_nonnegative_seconds(
            self.minimum_stage_start_seconds,
            "minimum_stage_start_seconds",
        )
        if not callable(self.clock):
            raise ValueError("clock must be callable")


@dataclass(frozen=True, slots=True)
class RuntimeBudget:
    """Started runtime budget state."""

    config: RuntimeBudgetConfig
    started_at: float


@dataclass(frozen=True, slots=True)
class RuntimeBudgetCheck:
    """Result of checking whether a runtime stage may start."""

    stage: str
    status: RuntimeBudgetStatus
    can_start: bool
    elapsed_seconds: float
    remaining_seconds: float | None
    turn_budget_seconds: float | None
    minimum_stage_start_seconds: float
    note: str | None = None


def start_runtime_budget(
    config: RuntimeBudgetConfig | None = None,
) -> RuntimeBudget:
    """Start a runtime budget using the configured clock."""

    effective_config = RuntimeBudgetConfig() if config is None else config
    return RuntimeBudget(
        config=effective_config,
        started_at=float(effective_config.clock()),
    )


def runtime_budget_check(
    budget: RuntimeBudget,
    stage: str,
) -> RuntimeBudgetCheck:
    """Return deterministic stage-start budget availability facts."""

    now = float(budget.config.clock())
    elapsed_seconds = max(0.0, now - budget.started_at)
    turn_budget_seconds = budget.config.turn_budget_seconds
    minimum_stage_start_seconds = budget.config.minimum_stage_start_seconds

    if turn_budget_seconds is None:
        return RuntimeBudgetCheck(
            stage=stage,
            status=RuntimeBudgetStatus.DISABLED,
            can_start=True,
            elapsed_seconds=elapsed_seconds,
            remaining_seconds=None,
            turn_budget_seconds=None,
            minimum_stage_start_seconds=minimum_stage_start_seconds,
        )

    remaining_seconds = turn_budget_seconds - elapsed_seconds
    if remaining_seconds <= 0.0:
        return RuntimeBudgetCheck(
            stage=stage,
            status=RuntimeBudgetStatus.EXHAUSTED,
            can_start=False,
            elapsed_seconds=elapsed_seconds,
            remaining_seconds=remaining_seconds,
            turn_budget_seconds=turn_budget_seconds,
            minimum_stage_start_seconds=minimum_stage_start_seconds,
            note=f"budget exhausted before {stage}",
        )

    if remaining_seconds < minimum_stage_start_seconds:
        return RuntimeBudgetCheck(
            stage=stage,
            status=RuntimeBudgetStatus.LOW_BUDGET,
            can_start=False,
            elapsed_seconds=elapsed_seconds,
            remaining_seconds=remaining_seconds,
            turn_budget_seconds=turn_budget_seconds,
            minimum_stage_start_seconds=minimum_stage_start_seconds,
            note=f"budget below stage-start reserve before {stage}",
        )

    return RuntimeBudgetCheck(
        stage=stage,
        status=RuntimeBudgetStatus.AVAILABLE,
        can_start=True,
        elapsed_seconds=elapsed_seconds,
        remaining_seconds=remaining_seconds,
        turn_budget_seconds=turn_budget_seconds,
        minimum_stage_start_seconds=minimum_stage_start_seconds,
    )


def _validate_nonnegative_seconds(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a non-negative number")
    if not math.isfinite(float(value)) or float(value) < 0.0:
        raise ValueError(f"{name} must be a non-negative number")


__all__ = (
    "RuntimeBudget",
    "RuntimeBudgetCheck",
    "RuntimeBudgetConfig",
    "RuntimeBudgetStatus",
    "runtime_budget_check",
    "start_runtime_budget",
)
