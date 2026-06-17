"""Isolated first-pass mission scoring policy.

Mission Evaluation Cycle 7 consumes deterministic ``MissionValueFacts`` and
returns tunable score components. It does not generate, rank, prune, select,
simulate, or mutate missions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Sequence

from .evaluation import MissionEvaluation, MissionValueFacts, ScoreComponent


@dataclass(frozen=True, slots=True)
class MissionScoringConfig:
    """Tunable weights for first-pass mission scoring."""

    production_delta_weight: float = 10.0
    target_ship_delta_weight: float = 1.0
    source_ship_delta_weight: float = 1.0
    ships_spent_weight: float = -0.25
    invalid_mission_penalty: float = -1000.0

    def __post_init__(self) -> None:
        for field_name in (
            "production_delta_weight",
            "target_ship_delta_weight",
            "source_ship_delta_weight",
            "ships_spent_weight",
            "invalid_mission_penalty",
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
        components, total_score = score_mission_value_facts(
            value_facts,
            config=config,
        )
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
    "score_mission_value_facts",
)
