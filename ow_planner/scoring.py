"""Isolated first-pass mission scoring policy.

Mission Evaluation Cycle 7 consumes deterministic ``MissionValueFacts`` and
returns tunable score components. Mission Evaluation Cycle 10 adds timing-aware
components from deterministic ``MissionTimingFacts``. Mission Evaluation Cycle
11 adds explicit capture-outcome components. Mission Evaluation Cycle 12 adds
source-drain opportunity-cost components. This module does not generate, rank,
prune, select, simulate, or mutate missions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Sequence

from .evaluation import (
    MissionEvaluation,
    MissionEvaluationFacts,
    MissionTimingFacts,
    MissionValueFacts,
    PlanetEvaluationFacts,
    PlanetFutureDeltaFacts,
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
    source_drain_fraction_weight: float = -2.0
    source_depleted_count_weight: float = -3.0
    incomplete_source_opportunity_penalty: float = -15.0

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
            "source_drain_fraction_weight",
            "source_depleted_count_weight",
            "incomplete_source_opportunity_penalty",
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


def score_source_opportunity_facts(
    facts: MissionEvaluationFacts,
    config: MissionScoringConfig | None = None,
) -> tuple[tuple[ScoreComponent, ...], float]:
    """Return source-drain opportunity-cost components for evaluation facts."""

    if not facts.value_facts.mission_valid_for_value:
        return ((), 0.0)

    source_planet_ids = _unique_source_planet_ids(facts.source_planet_ids)
    if not source_planet_ids:
        return ((), 0.0)

    effective_config = config or MissionScoringConfig()
    before_by_id = _planet_facts_by_id(facts.sources_before)
    mission_by_id = _planet_facts_by_id(facts.sources_mission)
    delta_by_id = _delta_facts_by_id(facts.future_delta.sources)
    if (
        facts.missing_source_planet_ids
        or facts.missing_mission_source_planet_ids
        or any(source_id not in before_by_id for source_id in source_planet_ids)
        or any(source_id not in mission_by_id for source_id in source_planet_ids)
        or any(source_id not in delta_by_id for source_id in source_planet_ids)
        or any(
            delta_by_id[source_id].mission_ship_delta_vs_before is None
            for source_id in source_planet_ids
            if source_id in delta_by_id
        )
    ):
        return _incomplete_source_opportunity_score(effective_config)

    total_before_ships = sum(
        max(0, before_by_id[source_id].ships)
        for source_id in source_planet_ids
    )
    if total_before_ships <= 0:
        return _incomplete_source_opportunity_score(effective_config)

    total_drained_ships = sum(
        max(0, -delta_by_id[source_id].mission_ship_delta_vs_before)
        for source_id in source_planet_ids
    )
    source_drain_fraction = max(0.0, total_drained_ships / total_before_ships)
    source_depleted_count = sum(
        1
        for source_id in source_planet_ids
        if mission_by_id[source_id].ships <= 0
    )
    components = (
        ScoreComponent(
            name="source_drain_fraction",
            value=source_drain_fraction,
            weight=effective_config.source_drain_fraction_weight,
        ),
        ScoreComponent(
            name="source_depleted_count",
            value=float(source_depleted_count),
            weight=effective_config.source_depleted_count_weight,
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
            source_components, source_total = score_source_opportunity_facts(
                evaluation.facts,
                config=config,
            )
            components = (
                value_components
                + timing_components
                + outcome_components
                + source_components
            )
            total_score = value_total + timing_total + outcome_total + source_total
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


def _unique_source_planet_ids(source_planet_ids: tuple[int, ...]) -> tuple[int, ...]:
    seen: set[int] = set()
    unique: list[int] = []
    for source_planet_id in source_planet_ids:
        if source_planet_id in seen:
            continue
        seen.add(source_planet_id)
        unique.append(source_planet_id)
    return tuple(unique)


def _planet_facts_by_id(
    facts: tuple[PlanetEvaluationFacts, ...],
) -> dict[int, PlanetEvaluationFacts]:
    by_id: dict[int, PlanetEvaluationFacts] = {}
    for fact in facts:
        if fact.planet_id not in by_id:
            by_id[fact.planet_id] = fact
    return by_id


def _delta_facts_by_id(
    facts: tuple[PlanetFutureDeltaFacts, ...],
) -> dict[int, PlanetFutureDeltaFacts]:
    by_id: dict[int, PlanetFutureDeltaFacts] = {}
    for fact in facts:
        if fact.planet_id is not None and fact.planet_id not in by_id:
            by_id[fact.planet_id] = fact
    return by_id


def _incomplete_source_opportunity_score(
    config: MissionScoringConfig,
) -> tuple[tuple[ScoreComponent, ...], float]:
    components = (
        ScoreComponent(
            name="incomplete_source_opportunity_penalty",
            value=1.0,
            weight=config.incomplete_source_opportunity_penalty,
        ),
    )
    return (components, _total_score(components))


__all__ = (
    "MissionScoringConfig",
    "score_evaluations",
    "score_mission_outcome_facts",
    "score_mission_timing_facts",
    "score_mission_value_facts",
    "score_source_opportunity_facts",
)
