"""Deterministic four-player mission and target facts.

Strategy Modes Cycle 6 extracts 4-player mission/target facts from existing
planner decision bundles and 4-player board facts. It does not generate,
evaluate, score, model responses, build commitments, select, convert actions,
or run simulator rollouts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .four_player_strategy import FourPlayerBoardFacts, FourPlayerStandingFacts
from .strategy_decisions import PlannerDecisionBundle


@dataclass(frozen=True, slots=True)
class FourPlayerMissionFacts:
    """Deterministic 4-player mission/target facts for one bundle."""

    bundle: PlannerDecisionBundle
    board_facts: FourPlayerBoardFacts | None = None
    is_four_player_mode: bool = False
    player_id: int | None = None
    production_leader_player_id: int | None = None
    total_ship_leader_player_id: int | None = None
    survival_pressure: bool | None = None
    target_owner_before: int | None = None
    target_owner_baseline: int | None = None
    target_owner_mission: int | None = None
    target_owner_production_rank: int | None = None
    target_owner_total_ship_rank: int | None = None
    target_was_current_player_owned: bool | None = None
    target_was_non_player_owned: bool | None = None
    target_was_production_leader_owned: bool | None = None
    target_was_total_ship_leader_owned: bool | None = None
    target_captured_by_player: bool | None = None
    target_taken_from_production_leader: bool | None = None
    target_taken_from_total_ship_leader: bool | None = None
    production_delta_vs_baseline: int | None = None
    leader_production_denied: int | None = None
    target_ship_delta_vs_baseline: int | None = None
    total_source_ship_delta_vs_baseline: int | None = None
    net_ship_delta_vs_baseline: int | None = None
    ships_spent: int = 0
    third_party_benefit_possible: bool | None = None
    source_counterattack_risk: bool | None = None
    response_labels: tuple[str, ...] = ()
    evaluation_total_score: float | None = None
    notes: tuple[str, ...] = ()


def four_player_mission_facts(
    bundle: PlannerDecisionBundle,
    board_facts: FourPlayerBoardFacts | None,
) -> FourPlayerMissionFacts:
    """Return deterministic 4-player mission/target facts for ``bundle``."""

    notes: list[str] = []
    is_four_player_mode = False
    player_id = None
    production_leader_player_id = None
    total_ship_leader_player_id = None
    survival_pressure = None
    standings_by_player: dict[int, FourPlayerStandingFacts] = {}
    if board_facts is None:
        notes.append("missing board facts")
    else:
        is_four_player_mode = board_facts.is_four_player_mode
        player_id = board_facts.player_id
        production_leader_player_id = board_facts.production_leader_player_id
        total_ship_leader_player_id = board_facts.total_ship_leader_player_id
        survival_pressure = board_facts.survival_pressure
        standings_by_player = {
            standing.player_id: standing for standing in board_facts.standings
        }
        if not board_facts.is_four_player_mode:
            notes.append("not four-player mode")
        if board_facts.player_id is None:
            notes.append("missing player id")

    evaluation = bundle.evaluation
    value_facts = None
    evaluation_total_score = None
    if evaluation is None:
        notes.append("missing evaluation")
    else:
        evaluation_total_score = evaluation.total_score
        if evaluation.facts is None:
            notes.append("missing evaluation facts")
        else:
            value_facts = evaluation.facts.value_facts

    response_evaluation = bundle.response_evaluation
    third_party_benefit_possible = None
    source_counterattack_risk = None
    response_labels: tuple[str, ...] = ()
    if response_evaluation is None:
        notes.append("missing response evaluation")
    elif response_evaluation.facts is None:
        notes.append("missing response facts")
    else:
        response_summary = response_evaluation.facts.response_summary
        third_party_benefit_possible = response_summary.third_party_benefit_possible
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

    target_owner_standing = _target_owner_standing(
        target_owner_baseline,
        standings_by_player,
    )
    if (
        target_owner_baseline is not None
        and target_owner_baseline >= 0
        and board_facts is not None
        and target_owner_standing is None
    ):
        notes.append("target owner not active player")

    target_was_current_player_owned = _same_owner(target_owner_baseline, player_id)
    target_was_non_player_owned = (
        None if target_owner_baseline is None else target_owner_baseline < 0
    )
    target_was_production_leader_owned = _same_owner(
        target_owner_baseline,
        production_leader_player_id,
    )
    target_was_total_ship_leader_owned = _same_owner(
        target_owner_baseline,
        total_ship_leader_player_id,
    )
    target_taken_from_production_leader = _target_taken_from_owner(
        target_was_production_leader_owned,
        target_owner_mission,
        player_id,
    )
    target_taken_from_total_ship_leader = _target_taken_from_owner(
        target_was_total_ship_leader_owned,
        target_owner_mission,
        player_id,
    )
    leader_production_denied = _leader_production_denied(
        target_taken_from_production_leader,
        target_production_before,
    )

    return FourPlayerMissionFacts(
        bundle=bundle,
        board_facts=board_facts,
        is_four_player_mode=is_four_player_mode,
        player_id=player_id,
        production_leader_player_id=production_leader_player_id,
        total_ship_leader_player_id=total_ship_leader_player_id,
        survival_pressure=survival_pressure,
        target_owner_before=target_owner_before,
        target_owner_baseline=target_owner_baseline,
        target_owner_mission=target_owner_mission,
        target_owner_production_rank=(
            None
            if target_owner_standing is None
            else target_owner_standing.production_rank
        ),
        target_owner_total_ship_rank=(
            None
            if target_owner_standing is None
            else target_owner_standing.total_ship_rank
        ),
        target_was_current_player_owned=target_was_current_player_owned,
        target_was_non_player_owned=target_was_non_player_owned,
        target_was_production_leader_owned=target_was_production_leader_owned,
        target_was_total_ship_leader_owned=target_was_total_ship_leader_owned,
        target_captured_by_player=target_captured_by_player,
        target_taken_from_production_leader=target_taken_from_production_leader,
        target_taken_from_total_ship_leader=target_taken_from_total_ship_leader,
        production_delta_vs_baseline=production_delta_vs_baseline,
        leader_production_denied=leader_production_denied,
        target_ship_delta_vs_baseline=target_ship_delta_vs_baseline,
        total_source_ship_delta_vs_baseline=total_source_ship_delta_vs_baseline,
        net_ship_delta_vs_baseline=_net_ship_delta_vs_baseline(
            target_ship_delta_vs_baseline,
            total_source_ship_delta_vs_baseline,
        ),
        ships_spent=ships_spent,
        third_party_benefit_possible=third_party_benefit_possible,
        source_counterattack_risk=source_counterattack_risk,
        response_labels=response_labels,
        evaluation_total_score=evaluation_total_score,
        notes=tuple(notes),
    )


def four_player_mission_facts_for_bundles(
    bundles: Sequence[PlannerDecisionBundle],
    board_facts: FourPlayerBoardFacts | None,
) -> tuple[FourPlayerMissionFacts, ...]:
    """Return 4-player mission/target facts in bundle input order."""

    return tuple(four_player_mission_facts(bundle, board_facts) for bundle in bundles)


def _target_owner_standing(
    target_owner_baseline: int | None,
    standings_by_player: dict[int, FourPlayerStandingFacts],
) -> FourPlayerStandingFacts | None:
    if target_owner_baseline is None or target_owner_baseline < 0:
        return None
    return standings_by_player.get(target_owner_baseline)


def _same_owner(owner: int | None, other_owner: int | None) -> bool | None:
    if owner is None or other_owner is None:
        return None
    return owner == other_owner


def _target_taken_from_owner(
    target_was_owner_owned: bool | None,
    target_owner_mission: int | None,
    player_id: int | None,
) -> bool | None:
    if (
        target_was_owner_owned is None
        or target_owner_mission is None
        or player_id is None
    ):
        return None
    return target_was_owner_owned and target_owner_mission == player_id


def _leader_production_denied(
    target_taken_from_production_leader: bool | None,
    target_production_before: int | None,
) -> int | None:
    if target_taken_from_production_leader is None or target_production_before is None:
        return None
    if target_taken_from_production_leader:
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
    "FourPlayerMissionFacts",
    "four_player_mission_facts",
    "four_player_mission_facts_for_bundles",
)
