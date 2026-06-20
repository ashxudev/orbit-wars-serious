"""First-pass deterministic four-player strategy selection.

Strategy Modes Cycle 7 selects from existing planner decision bundles using
Cycle 5 board facts, Cycle 6 mission facts, and existing commitment options
only. It does not generate, evaluate, score, model responses, build
commitments, convert actions, run simulator rollouts, or dispatch runtime
strategy.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Real
from typing import Sequence

from .commitment import CommitmentOption, CommitmentOptionStatus, CommitmentOptionType
from .candidates import CandidateOutcome
from .four_player_missions import (
    FourPlayerMissionFacts,
    four_player_mission_facts_for_bundles,
)
from .four_player_strategy import FourPlayerBoardFacts
from .strategy_decisions import (
    PlannerDecisionBundle,
    StrategySelectionResult,
    no_action_strategy_result,
    rejected_strategy_result,
    selected_strategy_result,
)


DEFAULT_FOUR_PLAYER_COMMITMENT_PREFERENCE_ORDER = (
    CommitmentOptionType.RESERVE_PRESERVING,
    CommitmentOptionType.MINIMUM_CAPTURE,
    CommitmentOptionType.CAPTURE_AND_HOLD,
    CommitmentOptionType.COORDINATED_MULTI_SOURCE,
    CommitmentOptionType.FULL_SOURCE,
)


@dataclass(frozen=True, slots=True)
class FourPlayerSelectionConfig:
    """Configuration for first-pass four-player strategy selection."""

    minimum_total_score: float = -100.0
    allow_source_counterattack_risk: bool = False
    allow_third_party_benefit: bool = False
    commitment_preference_order: tuple[CommitmentOptionType, ...] = (
        DEFAULT_FOUR_PLAYER_COMMITMENT_PREFERENCE_ORDER
    )

    def __post_init__(self) -> None:
        if (
            isinstance(self.minimum_total_score, bool)
            or not isinstance(self.minimum_total_score, Real)
            or not math.isfinite(float(self.minimum_total_score))
        ):
            raise ValueError("minimum_total_score must be a finite real number")
        if not isinstance(self.allow_source_counterattack_risk, bool):
            raise ValueError("allow_source_counterattack_risk must be a boolean")
        if not isinstance(self.allow_third_party_benefit, bool):
            raise ValueError("allow_third_party_benefit must be a boolean")
        if not isinstance(self.commitment_preference_order, tuple) or any(
            not isinstance(option_type, CommitmentOptionType)
            for option_type in self.commitment_preference_order
        ):
            raise ValueError(
                "commitment_preference_order must be a tuple of CommitmentOptionType"
            )


def select_four_player_strategy(
    bundles: Sequence[PlannerDecisionBundle],
    board_facts: FourPlayerBoardFacts | None,
    config: FourPlayerSelectionConfig | None = None,
) -> StrategySelectionResult:
    """Select one deterministic four-player mission bundle if eligible."""

    effective_config = FourPlayerSelectionConfig() if config is None else config
    strategy_mode_facts = (
        None if board_facts is None else board_facts.strategy_mode_facts
    )
    if not bundles:
        return rejected_strategy_result(
            strategy_mode_facts=strategy_mode_facts,
            notes=("no bundles",),
        )
    if board_facts is None:
        return rejected_strategy_result(notes=("missing board facts",))
    if not board_facts.is_four_player_mode:
        return rejected_strategy_result(
            strategy_mode_facts=strategy_mode_facts,
            notes=("not four-player mode",),
        )

    facts_by_input_order = four_player_mission_facts_for_bundles(
        bundles,
        board_facts,
    )
    complete_facts = tuple(
        facts
        for facts in facts_by_input_order
        if _has_complete_four_player_facts(facts)
    )
    if not complete_facts:
        return rejected_strategy_result(
            strategy_mode_facts=strategy_mode_facts,
            notes=("no complete four-player facts",),
        )

    ineligible_reasons: set[str] = set()
    eligible: list[tuple[FourPlayerMissionFacts, int, CommitmentOption]] = []
    for index, facts in enumerate(facts_by_input_order):
        if not _has_complete_four_player_facts(facts):
            continue
        if facts.bundle.candidate.outcome is not CandidateOutcome.VALIDATED:
            ineligible_reasons.add("candidate not validated")
            continue
        if facts.target_was_current_player_owned is True:
            continue
        if facts.evaluation_total_score < effective_config.minimum_total_score:
            ineligible_reasons.add("below minimum total score")
            continue
        if (
            not effective_config.allow_source_counterattack_risk
            and facts.source_counterattack_risk is True
        ):
            ineligible_reasons.add("source counterattack risk excluded")
            continue
        if (
            not effective_config.allow_third_party_benefit
            and facts.third_party_benefit_possible is True
        ):
            ineligible_reasons.add("third-party benefit excluded")
            continue
        commitment_option = _preferred_commitment_option(
            facts.bundle,
            effective_config.commitment_preference_order,
        )
        if commitment_option is None:
            ineligible_reasons.add("missing validated commitment option")
            continue
        eligible.append((facts, index, commitment_option))

    if not eligible:
        return no_action_strategy_result(
            strategy_mode_facts=strategy_mode_facts,
            notes=_no_action_notes(ineligible_reasons),
        )

    selected_facts, _index, selected_commitment = max(eligible, key=_selection_key)
    return selected_strategy_result(
        selected_facts.bundle,
        selected_commitment,
        notes=_selected_notes(selected_facts, selected_commitment),
    )


def _has_complete_four_player_facts(facts: FourPlayerMissionFacts) -> bool:
    return (
        facts.is_four_player_mode
        and facts.player_id is not None
        and facts.evaluation_total_score is not None
        and "missing evaluation" not in facts.notes
        and "missing evaluation facts" not in facts.notes
    )


def _preferred_commitment_option(
    bundle: PlannerDecisionBundle,
    commitment_preference_order: tuple[CommitmentOptionType, ...],
) -> CommitmentOption | None:
    if bundle.commitment_options is None:
        return None
    for preferred_option_type in commitment_preference_order:
        if preferred_option_type is CommitmentOptionType.NO_ATTACK:
            continue
        for option in bundle.commitment_options.options:
            if (
                option.option_type is preferred_option_type
                and option.status is CommitmentOptionStatus.VALIDATED
                and option.option_type is not CommitmentOptionType.NO_ATTACK
            ):
                return option
    return None


def _selection_key(
    item: tuple[FourPlayerMissionFacts, int, CommitmentOption],
) -> tuple[bool, bool, int, int, float, float, int, int]:
    facts, input_index, _commitment_option = item
    return (
        facts.target_taken_from_production_leader is True,
        facts.target_taken_from_total_ship_leader is True,
        _int_or_zero(facts.leader_production_denied),
        _int_or_zero(facts.production_delta_vs_baseline),
        float(facts.evaluation_total_score),
        _float_or_low(facts.net_ship_delta_vs_baseline),
        -facts.ships_spent,
        -input_index,
    )


def _selected_notes(
    facts: FourPlayerMissionFacts,
    commitment_option: CommitmentOption,
) -> tuple[str, ...]:
    notes = [
        "four-player strategy selected",
        f"selected commitment option: {commitment_option.option_type.value}",
    ]
    if facts.target_taken_from_production_leader is True:
        notes.append("production leader target")
    elif facts.target_taken_from_total_ship_leader is True:
        notes.append("total ship leader target")
    elif facts.survival_pressure is True:
        notes.append("survival pressure context")
    return tuple(notes)


def _no_action_notes(ineligible_reasons: set[str]) -> tuple[str, ...]:
    ordered_reasons = tuple(
        reason
        for reason in (
            "source counterattack risk excluded",
            "third-party benefit excluded",
            "below minimum total score",
            "missing validated commitment option",
            "candidate not validated",
        )
        if reason in ineligible_reasons
    )
    return ("no eligible four-player strategy", *ordered_reasons)


def _int_or_zero(value: int | None) -> int:
    return 0 if value is None else value


def _float_or_low(value: int | float | None) -> float:
    if value is None:
        return float("-inf")
    return float(value)


__all__ = (
    "DEFAULT_FOUR_PLAYER_COMMITMENT_PREFERENCE_ORDER",
    "FourPlayerSelectionConfig",
    "select_four_player_strategy",
)
