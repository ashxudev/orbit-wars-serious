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
from .candidates import CandidateOutcome, MissionType
from .four_player_missions import (
    FourPlayerMissionFacts,
    four_player_mission_facts_for_bundles,
)
from .four_player_plateau import FourPlayerPlateauReport
from .four_player_rank import FourPlayerRankReport
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
    four_player_plateau_report: FourPlayerPlateauReport | None = None
    four_player_rank_report: FourPlayerRankReport | None = None

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
        if self.four_player_plateau_report is not None and not isinstance(
            self.four_player_plateau_report,
            FourPlayerPlateauReport,
        ):
            raise ValueError(
                "four_player_plateau_report must be None or FourPlayerPlateauReport"
            )
        if self.four_player_rank_report is not None and not isinstance(
            self.four_player_rank_report,
            FourPlayerRankReport,
        ):
            raise ValueError(
                "four_player_rank_report must be None or FourPlayerRankReport"
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
    plateau_recovery_eligible: list[
        tuple[FourPlayerMissionFacts, int, CommitmentOption]
    ] = []
    for index, facts in enumerate(facts_by_input_order):
        if not _has_complete_four_player_facts(facts):
            continue
        if facts.bundle.candidate.outcome is not CandidateOutcome.VALIDATED:
            ineligible_reasons.add("candidate not validated")
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
        if facts.target_was_current_player_owned is True:
            if _is_plateau_recovery_candidate(
                facts,
                commitment_option,
                effective_config.four_player_plateau_report,
            ):
                plateau_recovery_eligible.append((facts, index, commitment_option))
            continue
        if facts.evaluation_total_score < effective_config.minimum_total_score:
            if _is_plateau_recovery_candidate(
                facts,
                commitment_option,
                effective_config.four_player_plateau_report,
            ):
                plateau_recovery_eligible.append((facts, index, commitment_option))
            else:
                ineligible_reasons.add("below minimum total score")
            continue
        eligible.append((facts, index, commitment_option))

    if not eligible:
        recovery_pool, recovery_note = _plateau_recovery_pool(
            plateau_recovery_eligible,
            effective_config.four_player_plateau_report,
        )
        if recovery_pool:
            selected_facts, _index, selected_commitment = max(
                recovery_pool,
                key=lambda item: _selection_key(
                    item,
                    effective_config.four_player_rank_report,
                ),
            )
            return selected_strategy_result(
                selected_facts.bundle,
                selected_commitment,
                notes=(
                    *_selected_notes(
                        selected_facts,
                        selected_commitment,
                        effective_config.four_player_rank_report,
                    ),
                    recovery_note,
                ),
            )
        return no_action_strategy_result(
            strategy_mode_facts=strategy_mode_facts,
            notes=_no_action_notes(ineligible_reasons),
        )

    selected_facts, _index, selected_commitment = max(
        eligible,
        key=lambda item: _selection_key(
            item,
            effective_config.four_player_rank_report,
        ),
    )
    return selected_strategy_result(
        selected_facts.bundle,
        selected_commitment,
        notes=_selected_notes(
            selected_facts,
            selected_commitment,
            effective_config.four_player_rank_report,
        ),
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


def _plateau_recovery_pool(
    eligible: list[tuple[FourPlayerMissionFacts, int, CommitmentOption]],
    plateau_report: FourPlayerPlateauReport | None,
) -> tuple[list[tuple[FourPlayerMissionFacts, int, CommitmentOption]], str | None]:
    if not _is_plateau_recovery_context(plateau_report) or not eligible:
        return [], None
    productive = [
        item for item in eligible if _is_productive_plateau_recovery_candidate(item[0])
    ]
    if productive:
        return productive, "four-player plateau recovery: productive candidate"
    retention = [
        item
        for item in eligible
        if _is_owned_retention_candidate(item[0])
        and item[2].option_type is CommitmentOptionType.RESERVE_PRESERVING
    ]
    if retention:
        return retention, "four-player plateau recovery: reserve_preserving retention"
    return [], None


def _is_plateau_recovery_candidate(
    facts: FourPlayerMissionFacts,
    commitment_option: CommitmentOption,
    plateau_report: FourPlayerPlateauReport | None,
) -> bool:
    if not _is_plateau_recovery_context(plateau_report):
        return False
    if commitment_option.option_type is CommitmentOptionType.NO_ATTACK:
        return False
    return (
        _is_productive_plateau_recovery_candidate(facts)
        or (
            _is_owned_retention_candidate(facts)
            and commitment_option.option_type is CommitmentOptionType.RESERVE_PRESERVING
        )
    )


def _is_plateau_recovery_context(
    plateau_report: FourPlayerPlateauReport | None,
) -> bool:
    return (
        plateau_report is not None
        and plateau_report.is_four_player_context
        and plateau_report.underexpanded
    )


def _is_productive_plateau_recovery_candidate(
    facts: FourPlayerMissionFacts,
) -> bool:
    if facts.bundle.candidate.mission_type not in (
        MissionType.CAPTURE_NEUTRAL,
        MissionType.ATTACK_ENEMY,
    ):
        return False
    if facts.target_was_current_player_owned is True:
        return False
    return (
        facts.target_captured_by_player is True
        or _int_or_zero(facts.production_delta_vs_baseline) > 0
        or _int_or_zero(facts.leader_production_denied) > 0
    )


def _is_owned_retention_candidate(facts: FourPlayerMissionFacts) -> bool:
    return facts.bundle.candidate.mission_type in (
        MissionType.DEFEND_OWN,
        MissionType.REINFORCE,
    )


def _is_rank_aware_continuation_candidate(
    facts: FourPlayerMissionFacts,
    rank_report: FourPlayerRankReport | None,
) -> bool:
    if rank_report is None:
        return False
    if not (
        rank_report.leader_pressure
        or rank_report.underexpanded_trailing
        or rank_report.swing_opportunity
    ):
        return False
    if facts.bundle.candidate.mission_type not in (
        MissionType.CAPTURE_NEUTRAL,
        MissionType.ATTACK_ENEMY,
    ):
        return False
    if facts.target_was_current_player_owned is True:
        return False
    target_ids = {
        target_facts.target_planet_id
        for target_facts in rank_report.swing_target_facts
        if (
            target_facts.high_value_swing_target
            or target_facts.target_owner_is_leader
            or target_facts.plausible_with_nearest_source
        )
    }
    return facts.bundle.candidate.target_planet_id in target_ids


def _selection_key(
    item: tuple[FourPlayerMissionFacts, int, CommitmentOption],
    rank_report: FourPlayerRankReport | None = None,
) -> tuple[bool, bool, bool, int, int, float, float, int, int]:
    facts, input_index, _commitment_option = item
    return (
        facts.target_taken_from_production_leader is True,
        facts.target_taken_from_total_ship_leader is True,
        _is_rank_aware_continuation_candidate(facts, rank_report),
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
    rank_report: FourPlayerRankReport | None = None,
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
    if _is_rank_aware_continuation_candidate(facts, rank_report):
        notes.append("rank-aware four-player continuation")
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
