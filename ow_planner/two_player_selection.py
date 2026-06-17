"""First-pass deterministic two-player direct-advantage selection.

Strategy Modes Cycle 4 selects from existing planner decision bundles using
Cycle 3 two-player facts and existing commitment options only. It does not
generate, evaluate, score, respond, commit, convert actions, run simulator
rollouts, or implement four-player policy.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Real
from typing import Sequence

from .commitment import CommitmentOption, CommitmentOptionStatus, CommitmentOptionType
from .strategy_decisions import (
    PlannerDecisionBundle,
    StrategySelectionResult,
    no_action_strategy_result,
    rejected_strategy_result,
    selected_strategy_result,
)
from .strategy_modes import StrategyModeFacts
from .two_player_strategy import (
    TwoPlayerAdvantageFacts,
    two_player_advantage_facts_for_bundles,
)


DEFAULT_COMMITMENT_PREFERENCE_ORDER = (
    CommitmentOptionType.RESERVE_PRESERVING,
    CommitmentOptionType.MINIMUM_CAPTURE,
    CommitmentOptionType.CAPTURE_AND_HOLD,
    CommitmentOptionType.COORDINATED_MULTI_SOURCE,
    CommitmentOptionType.FULL_SOURCE,
)


@dataclass(frozen=True, slots=True)
class TwoPlayerSelectionConfig:
    """Configuration for first-pass two-player direct-advantage selection."""

    minimum_total_score: float = 0.0
    allow_source_counterattack_risk: bool = False
    commitment_preference_order: tuple[CommitmentOptionType, ...] = (
        DEFAULT_COMMITMENT_PREFERENCE_ORDER
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
        if not isinstance(self.commitment_preference_order, tuple) or any(
            not isinstance(option_type, CommitmentOptionType)
            for option_type in self.commitment_preference_order
        ):
            raise ValueError(
                "commitment_preference_order must be a tuple of CommitmentOptionType"
            )


def select_two_player_direct_advantage(
    bundles: Sequence[PlannerDecisionBundle],
    config: TwoPlayerSelectionConfig | None = None,
) -> StrategySelectionResult:
    """Select one deterministic two-player direct-advantage bundle if eligible."""

    effective_config = TwoPlayerSelectionConfig() if config is None else config
    if not bundles:
        return rejected_strategy_result(notes=("no bundles",))

    facts_by_input_order = two_player_advantage_facts_for_bundles(bundles)
    strategy_mode_facts = _first_strategy_mode_facts(facts_by_input_order)
    if not any(facts.is_two_player_mode for facts in facts_by_input_order):
        return rejected_strategy_result(
            strategy_mode_facts=strategy_mode_facts,
            notes=("not two-player mode",),
        )

    complete_facts = tuple(
        facts for facts in facts_by_input_order if _has_complete_two_player_facts(facts)
    )
    if not complete_facts:
        return rejected_strategy_result(
            strategy_mode_facts=strategy_mode_facts,
            notes=("no complete two-player facts",),
        )

    ineligible_reasons: set[str] = set()
    eligible: list[tuple[TwoPlayerAdvantageFacts, int, CommitmentOption]] = []
    for index, facts in enumerate(facts_by_input_order):
        if not _has_complete_two_player_facts(facts):
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

    selected_facts, _index, selected_commitment = max(
        eligible,
        key=_selection_key,
    )
    return selected_strategy_result(
        selected_facts.bundle,
        selected_commitment,
        notes=(
            "two-player direct advantage selected",
            f"selected commitment option: {selected_commitment.option_type.value}",
        ),
    )


def _has_complete_two_player_facts(facts: TwoPlayerAdvantageFacts) -> bool:
    return (
        facts.is_two_player_mode
        and facts.player_id is not None
        and facts.opponent_player_id is not None
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
    item: tuple[TwoPlayerAdvantageFacts, int, CommitmentOption],
) -> tuple[bool, int, int, float, float, int, int]:
    facts, input_index, _commitment_option = item
    return (
        facts.target_taken_from_opponent is True,
        _int_or_zero(facts.opponent_production_denied),
        _int_or_zero(facts.production_delta_vs_baseline),
        float(facts.evaluation_total_score),
        _float_or_low(facts.net_ship_delta_vs_baseline),
        -facts.ships_spent,
        -input_index,
    )


def _first_strategy_mode_facts(
    facts_by_input_order: tuple[TwoPlayerAdvantageFacts, ...],
) -> StrategyModeFacts | None:
    for facts in facts_by_input_order:
        if facts.bundle.strategy_mode_facts is not None:
            return facts.bundle.strategy_mode_facts
    return None


def _no_action_notes(ineligible_reasons: set[str]) -> tuple[str, ...]:
    ordered_reasons = tuple(
        reason
        for reason in (
            "source counterattack risk excluded",
            "below minimum total score",
            "missing validated commitment option",
        )
        if reason in ineligible_reasons
    )
    return ("no eligible two-player direct advantage", *ordered_reasons)


def _int_or_zero(value: int | None) -> int:
    return 0 if value is None else value


def _float_or_low(value: int | float | None) -> float:
    if value is None:
        return float("-inf")
    return float(value)


__all__ = (
    "DEFAULT_COMMITMENT_PREFERENCE_ORDER",
    "TwoPlayerSelectionConfig",
    "select_two_player_direct_advantage",
)
