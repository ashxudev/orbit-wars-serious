"""Deterministic two-player strategy facts.

Strategy Modes Cycle 3 extracts direct-advantage facts from existing planner
decision bundles. It does not generate, evaluate, score, respond, commit, rank,
prune, compare, select, convert actions, or run simulator rollouts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .strategy_decisions import PlannerDecisionBundle
from .strategy_modes import StrategyMode


@dataclass(frozen=True, slots=True)
class TwoPlayerAdvantageFacts:
    """Deterministic direct-advantage facts for one two-player bundle."""

    bundle: PlannerDecisionBundle
    is_two_player_mode: bool = False
    player_id: int | None = None
    opponent_player_id: int | None = None
    target_owner_before: int | None = None
    target_owner_baseline: int | None = None
    target_owner_mission: int | None = None
    target_was_opponent_owned: bool | None = None
    target_taken_from_opponent: bool | None = None
    target_captured_by_player: bool | None = None
    production_delta_vs_baseline: int | None = None
    opponent_production_denied: int | None = None
    target_ship_delta_vs_baseline: int | None = None
    total_source_ship_delta_vs_baseline: int | None = None
    net_ship_delta_vs_baseline: int | None = None
    ships_spent: int = 0
    source_counterattack_risk: bool | None = None
    response_labels: tuple[str, ...] = ()
    evaluation_total_score: float | None = None
    notes: tuple[str, ...] = ()


def two_player_advantage_facts(
    bundle: PlannerDecisionBundle,
) -> TwoPlayerAdvantageFacts:
    """Return deterministic two-player direct-advantage facts for ``bundle``."""

    notes: list[str] = []
    strategy_mode_facts = bundle.strategy_mode_facts
    is_two_player_mode = False
    player_id = None
    opponent_player_id = None
    if strategy_mode_facts is None:
        notes.append("missing strategy mode facts")
    else:
        is_two_player_mode = strategy_mode_facts.mode is StrategyMode.TWO_PLAYER
        player_id = strategy_mode_facts.player_id
        if not is_two_player_mode:
            notes.append("not two-player mode")
        if player_id is None:
            notes.append("missing player id")
        if len(strategy_mode_facts.opponent_player_ids) == 1:
            opponent_player_id = strategy_mode_facts.opponent_player_ids[0]
        else:
            notes.append("missing opponent player id")

    evaluation = bundle.evaluation
    evaluation_facts = None
    value_facts = None
    evaluation_total_score = None
    if evaluation is None:
        notes.append("missing evaluation")
    else:
        evaluation_total_score = evaluation.total_score
        evaluation_facts = evaluation.facts
        if evaluation_facts is None:
            notes.append("missing evaluation facts")
        else:
            value_facts = evaluation_facts.value_facts

    response_evaluation = bundle.response_evaluation
    source_counterattack_risk = None
    response_labels: tuple[str, ...] = ()
    if response_evaluation is None:
        notes.append("missing response evaluation")
    elif response_evaluation.facts is None:
        notes.append("missing response facts")
    else:
        response_summary = response_evaluation.facts.response_summary
        source_counterattack_risk = response_summary.source_counterattack_risk
        response_labels = response_summary.labels

    target_owner_before = None
    target_owner_baseline = None
    target_owner_mission = None
    target_captured_by_player = None
    production_delta_vs_baseline = None
    target_ship_delta_vs_baseline = None
    total_source_ship_delta_vs_baseline = None
    ships_spent = 0
    target_production_before = None
    if value_facts is not None:
        target_owner_before = value_facts.target_owner_before
        target_owner_baseline = value_facts.target_owner_baseline
        target_owner_mission = value_facts.target_owner_mission
        target_captured_by_player = value_facts.target_captured_by_player
        production_delta_vs_baseline = value_facts.production_delta_vs_baseline
        target_ship_delta_vs_baseline = value_facts.target_ship_delta_vs_baseline
        total_source_ship_delta_vs_baseline = (
            value_facts.total_source_ship_delta_vs_baseline
        )
        ships_spent = value_facts.ships_spent
        target_production_before = value_facts.target_production_before

    target_was_opponent_owned = _target_was_opponent_owned(
        target_owner_baseline,
        opponent_player_id,
    )
    target_taken_from_opponent = _target_taken_from_opponent(
        target_was_opponent_owned,
        target_owner_mission,
        player_id,
    )
    opponent_production_denied = _opponent_production_denied(
        target_taken_from_opponent,
        target_production_before,
    )
    net_ship_delta_vs_baseline = _net_ship_delta_vs_baseline(
        target_ship_delta_vs_baseline,
        total_source_ship_delta_vs_baseline,
    )

    return TwoPlayerAdvantageFacts(
        bundle=bundle,
        is_two_player_mode=is_two_player_mode,
        player_id=player_id,
        opponent_player_id=opponent_player_id,
        target_owner_before=target_owner_before,
        target_owner_baseline=target_owner_baseline,
        target_owner_mission=target_owner_mission,
        target_was_opponent_owned=target_was_opponent_owned,
        target_taken_from_opponent=target_taken_from_opponent,
        target_captured_by_player=target_captured_by_player,
        production_delta_vs_baseline=production_delta_vs_baseline,
        opponent_production_denied=opponent_production_denied,
        target_ship_delta_vs_baseline=target_ship_delta_vs_baseline,
        total_source_ship_delta_vs_baseline=total_source_ship_delta_vs_baseline,
        net_ship_delta_vs_baseline=net_ship_delta_vs_baseline,
        ships_spent=ships_spent,
        source_counterattack_risk=source_counterattack_risk,
        response_labels=response_labels,
        evaluation_total_score=evaluation_total_score,
        notes=tuple(notes),
    )


def two_player_advantage_facts_for_bundles(
    bundles: Sequence[PlannerDecisionBundle],
) -> tuple[TwoPlayerAdvantageFacts, ...]:
    """Return two-player direct-advantage facts in bundle input order."""

    return tuple(two_player_advantage_facts(bundle) for bundle in bundles)


def _target_was_opponent_owned(
    target_owner_baseline: int | None,
    opponent_player_id: int | None,
) -> bool | None:
    if target_owner_baseline is None or opponent_player_id is None:
        return None
    return target_owner_baseline == opponent_player_id


def _target_taken_from_opponent(
    target_was_opponent_owned: bool | None,
    target_owner_mission: int | None,
    player_id: int | None,
) -> bool | None:
    if (
        target_was_opponent_owned is None
        or target_owner_mission is None
        or player_id is None
    ):
        return None
    return target_was_opponent_owned and target_owner_mission == player_id


def _opponent_production_denied(
    target_taken_from_opponent: bool | None,
    target_production_before: int | None,
) -> int | None:
    if target_taken_from_opponent is None or target_production_before is None:
        return None
    if target_taken_from_opponent:
        return target_production_before
    return 0


def _net_ship_delta_vs_baseline(
    target_ship_delta_vs_baseline: int | None,
    total_source_ship_delta_vs_baseline: int | None,
) -> int | None:
    if (
        target_ship_delta_vs_baseline is None
        or total_source_ship_delta_vs_baseline is None
    ):
        return None
    return target_ship_delta_vs_baseline + total_source_ship_delta_vs_baseline


__all__ = (
    "TwoPlayerAdvantageFacts",
    "two_player_advantage_facts",
    "two_player_advantage_facts_for_bundles",
)
