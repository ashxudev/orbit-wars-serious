"""First-pass opponent-response classification labels.

This module consumes already-extracted response facts and emits stable labels.
It intentionally does not extract response facts, run simulator rollouts,
score, rank, prune, or select missions.
"""

from __future__ import annotations

from dataclasses import dataclass

from .response import MissionResponseEvaluation, ResponseEvaluationStatus


@dataclass(frozen=True, slots=True)
class ResponseClassificationFacts:
    """Deterministic first-pass response classification labels."""

    labels: tuple[str, ...] = ()
    undefendable: bool = False
    defendable_profitable: bool = False
    donation: bool = False
    race_risk: bool = False
    source_drain_bait: bool = False
    notes: tuple[str, ...] = ()


def classify_response_facts(
    response: MissionResponseEvaluation,
) -> ResponseClassificationFacts:
    """Return deterministic first-pass classifications for ``response``."""

    if response.status is ResponseEvaluationStatus.INCOMPLETE:
        return ResponseClassificationFacts(
            notes=("response evaluation is incomplete",),
        )

    response_facts = response.facts
    evaluation_facts = response.evaluation.facts
    if evaluation_facts is None:
        return ResponseClassificationFacts(
            notes=("mission evaluation facts are missing",),
        )

    if not _has_response_evidence(response):
        return ResponseClassificationFacts(
            notes=("insufficient response facts for classification",),
        )

    race_risk = response_facts.response_summary.target_race_risk
    source_drain_bait = (
        response_facts.response_summary.source_counterattack_risk
        or response_facts.source_pressure.pinned_source_count > 0
        or response_facts.source_pressure.threatened_source_count > 0
    )
    third_party_benefit = response_facts.response_summary.third_party_benefit_possible
    opponent_can_defend_or_race = (
        response_facts.response_summary.target_reinforcement_feasible
        or race_risk
    )
    positive_value_context = _has_positive_value_context(response)
    player_durable_benefit = _has_player_durable_benefit(response)

    undefendable = (
        not opponent_can_defend_or_race
        and response_facts.source_pressure.threatened_source_count == 0
        and not third_party_benefit
    )
    defendable_profitable = opponent_can_defend_or_race and positive_value_context
    donation = third_party_benefit and not player_durable_benefit

    labels: list[str] = []
    if undefendable:
        labels.append("undefendable")
    if defendable_profitable:
        labels.append("defendable_profitable")
    if donation:
        labels.append("donation")
    if race_risk:
        labels.append("race_risk")
    if source_drain_bait:
        labels.append("source_drain_bait")

    notes: list[str] = []
    if not labels:
        notes.append("insufficient response facts for classification")

    return ResponseClassificationFacts(
        labels=tuple(labels),
        undefendable=undefendable,
        defendable_profitable=defendable_profitable,
        donation=donation,
        race_risk=race_risk,
        source_drain_bait=source_drain_bait,
        notes=tuple(notes),
    )


def _has_positive_value_context(response: MissionResponseEvaluation) -> bool:
    evaluation_facts = response.evaluation.facts
    if evaluation_facts is None:
        return False

    value_facts = evaluation_facts.value_facts
    if value_facts.mission_valid_for_value:
        if value_facts.production_delta_vs_baseline is not None:
            return value_facts.production_delta_vs_baseline > 0
        if value_facts.target_captured_by_player is True:
            return True
        if value_facts.target_retained_by_player is True:
            return True

    return response.evaluation.total_score is not None and response.evaluation.total_score > 0


def _has_response_evidence(response: MissionResponseEvaluation) -> bool:
    response_facts = response.facts
    return (
        response_facts.target_reinforcement.target_planet_id is not None
        or response_facts.target_race.target_planet_id is not None
        or bool(response_facts.source_counterattacks)
        or response_facts.third_party_benefit.target_planet_id is not None
        or bool(response_facts.source_pressure.source_facts)
        or bool(response_facts.response_labels)
    )


def _has_player_durable_benefit(response: MissionResponseEvaluation) -> bool:
    evaluation_facts = response.evaluation.facts
    if evaluation_facts is None:
        return False

    value_facts = evaluation_facts.value_facts
    return (
        value_facts.target_captured_by_player is True
        or value_facts.target_retained_by_player is True
        or (
            value_facts.production_delta_vs_baseline is not None
            and value_facts.production_delta_vs_baseline > 0
        )
    )


__all__ = (
    "ResponseClassificationFacts",
    "classify_response_facts",
)
