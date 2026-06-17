"""Isolated first-pass mission scoring policy.

Mission Evaluation Cycle 7 consumes deterministic ``MissionValueFacts`` and
returns tunable score components. Mission Evaluation Cycle 10 adds timing-aware
components from deterministic ``MissionTimingFacts``. Mission Evaluation Cycle
11 adds explicit capture-outcome components. This module does not generate,
rank, prune, select, simulate, or mutate missions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Sequence

from .evaluation import (
    MissionEvaluation,
    MissionTimingFacts,
    MissionValueFacts,
    ScoreComponent,
)


@dataclass(frozen=True, slots=True)
class MissionScoringConfig:
    """Tunable weights for first-pass mission scoring."""

    production_delta_weight: float = 10.0
    target_ship_delta_weight: float = 1.0
    source_ship_delta_weight: float = 1.0
    ships_spent_weight: float = -0.25
    invalid_mission_penalty: float = -1000.0
    arrival_tick_weight: float = -0.05
    incomplete_timing_penalty: float = -25.0
    capture_success_weight: float = 5.0
    retain_control_weight: float = 2.0
    target_loss_penalty: float = -10.0

    def __post_init__(self) -> None:
        for field_name in (
            "production_delta_weight",
            "target_ship_delta_weight",
            "source_ship_delta_weight",
            "ships_spent_weight",
            "invalid_mission_penalty",
            "arrival_tick_weight",
            "incomplete_timing_penalty",
            "capture_success_weight",
            "retain_control_weight",
            "target_loss_penalty",
        ):
            _validate_weight(getattr(self, field_name), field_name)


def score_mission_value_facts(
    value_facts: MissionValueFacts,
    config: MissionScoringConfig | None = None,
) -> tuple[tuple[ScoreComponent, ...], float]:
    """Return score components and total score for deterministic value facts."""

    effective_config = config or MissionScoringConfig()
    if not value_facts.mission_valid_for_value:
        components = (
            ScoreComponent(
                name="invalid_mission_penalty",
                value=1.0,
                weight=effective_config.invalid_mission_penalty,
            ),
        )
        return (components, _total_score(components))

    components = (
        ScoreComponent(
            name="production_delta_vs_baseline",
            value=_float_or_zero(value_facts.production_delta_vs_baseline),
            weight=effective_config.production_delta_weight,
        ),
        ScoreComponent(
            name="target_ship_delta_vs_baseline",
            value=_float_or_zero(value_facts.target_ship_delta_vs_baseline),
            weight=effective_config.target_ship_delta_weight,
        ),
        ScoreComponent(
            name="source_ship_delta_vs_baseline",
            value=_float_or_zero(value_facts.total_source_ship_delta_vs_baseline),
            weight=effective_config.source_ship_delta_weight,
        ),
        ScoreComponent(
            name="ships_spent",
            value=float(value_facts.ships_spent),
            weight=effective_config.ships_spent_weight,
        ),
    )
    return (components, _total_score(components))


def score_mission_outcome_facts(
    value_facts: MissionValueFacts,
    config: MissionScoringConfig | None = None,
) -> tuple[tuple[ScoreComponent, ...], float]:
    """Return capture-outcome score components for deterministic value facts."""

    if not value_facts.mission_valid_for_value:
        return ((), 0.0)

    effective_config = config or MissionScoringConfig()
    components: list[ScoreComponent] = []
    if value_facts.target_captured_by_player is True:
        components.append(
            ScoreComponent(
                name="target_captured_by_player",
                value=1.0,
                weight=effective_config.capture_success_weight,
            )
        )
    if value_facts.target_retained_by_player is True:
        components.append(
            ScoreComponent(
                name="target_retained_by_player",
                value=1.0,
                weight=effective_config.retain_control_weight,
            )
        )
    if value_facts.target_lost_by_player is True:
        components.append(
            ScoreComponent(
                name="target_lost_by_player",
                value=1.0,
                weight=effective_config.target_loss_penalty,
            )
        )

    outcome_components = tuple(components)
    return (outcome_components, _total_score(outcome_components))


def score_mission_timing_facts(
    timing_facts: MissionTimingFacts,
    config: MissionScoringConfig | None = None,
) -> tuple[tuple[ScoreComponent, ...], float]:
    """Return timing score components for deterministic arrival facts."""

    effective_config = config or MissionScoringConfig()
    if timing_facts.timing_complete and not timing_facts.launch_arrival_ticks:
        return ((), 0.0)
    if timing_facts.timing_complete and timing_facts.max_arrival_ticks is not None:
        components = (
            ScoreComponent(
                name="max_arrival_ticks",
                value=float(timing_facts.max_arrival_ticks),
                weight=effective_config.arrival_tick_weight,
            ),
        )
        return (components, _total_score(components))

    components = (
        ScoreComponent(
            name="incomplete_timing_penalty",
            value=1.0,
            weight=effective_config.incomplete_timing_penalty,
        ),
    )
    return (components, _total_score(components))


def score_evaluations(
    evaluations: Sequence[MissionEvaluation],
    config: MissionScoringConfig | None = None,
) -> tuple[MissionEvaluation, ...]:
    """Return evaluations with score components populated in input order."""

    scored: list[MissionEvaluation] = []
    for evaluation in evaluations:
        value_facts = (
            MissionValueFacts()
            if evaluation.facts is None
            else evaluation.facts.value_facts
        )
        value_components, value_total = score_mission_value_facts(
            value_facts,
            config=config,
        )
        components = value_components
        total_score = value_total
        if value_facts.mission_valid_for_value and evaluation.facts is not None:
            timing_components, timing_total = score_mission_timing_facts(
                evaluation.facts.timing_facts,
                config=config,
            )
            outcome_components, outcome_total = score_mission_outcome_facts(
                value_facts,
                config=config,
            )
            components = value_components + timing_components + outcome_components
            total_score = value_total + timing_total + outcome_total
        scored.append(
            replace(
                evaluation,
                score_components=components,
                total_score=total_score,
            )
        )
    return tuple(scored)


def _total_score(components: tuple[ScoreComponent, ...]) -> float:
    return sum(component.value * component.weight for component in components)


def _float_or_zero(value: int | float | None) -> float:
    if value is None:
        return 0.0
    return float(value)


def _validate_weight(value: object, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a finite real number")
    if not math.isfinite(float(value)):
        raise ValueError(f"{field_name} must be a finite real number")


__all__ = (
    "MissionScoringConfig",
    "score_evaluations",
    "score_mission_outcome_facts",
    "score_mission_timing_facts",
    "score_mission_value_facts",
)
