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

from .candidates import MissionType
from .commitment import CommitmentOption, CommitmentOptionStatus, CommitmentOptionType
from .enemy_denial import EnemyDenialOpportunityReport
from .own_transfers import OwnTransferIntentReport
from .owned_threats import OwnedProductionThreatReport
from .strategy_decisions import (
    PlannerDecisionBundle,
    StrategySelectionResult,
    no_action_strategy_result,
    rejected_strategy_result,
    selected_strategy_result,
)
from .strategy_modes import StrategyModeFacts
from .two_player_pressure import (
    two_player_pressure_facts,
)
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

CAPTURE_HOLD_RISK_RESPONSE_LABELS = (
    "target_reinforcement_feasible",
    "target_race_risk",
)


@dataclass(frozen=True, slots=True)
class TwoPlayerSelectionConfig:
    """Configuration for first-pass two-player direct-advantage selection."""

    minimum_total_score: float = 0.0
    allow_source_counterattack_risk: bool = False
    commitment_preference_order: tuple[CommitmentOptionType, ...] = (
        DEFAULT_COMMITMENT_PREFERENCE_ORDER
    )
    owned_production_threat_report: OwnedProductionThreatReport | None = None
    own_transfer_intent_report: OwnTransferIntentReport | None = None
    enemy_denial_opportunity_report: EnemyDenialOpportunityReport | None = None

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
        if self.owned_production_threat_report is not None and not isinstance(
            self.owned_production_threat_report,
            OwnedProductionThreatReport,
        ):
            raise ValueError(
                "owned_production_threat_report must be None or "
                "OwnedProductionThreatReport"
            )
        if self.own_transfer_intent_report is not None and not isinstance(
            self.own_transfer_intent_report,
            OwnTransferIntentReport,
        ):
            raise ValueError(
                "own_transfer_intent_report must be None or OwnTransferIntentReport"
            )
        if self.enemy_denial_opportunity_report is not None and not isinstance(
            self.enemy_denial_opportunity_report,
            EnemyDenialOpportunityReport,
        ):
            raise ValueError(
                "enemy_denial_opportunity_report must be None or "
                "EnemyDenialOpportunityReport"
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
    owned_threat_report = effective_config.owned_production_threat_report
    for index, facts in enumerate(facts_by_input_order):
        if not _has_complete_two_player_facts(facts):
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
            prefer_capture_and_hold=_is_risky_capture_facts(facts),
        )
        if commitment_option is None:
            ineligible_reasons.add("missing validated commitment option")
            continue
        if facts.evaluation_total_score < effective_config.minimum_total_score:
            if not _allow_below_minimum_under_owned_pressure(
                facts,
                commitment_option,
                owned_threat_report,
            ):
                ineligible_reasons.add("below minimum total score")
                continue
        eligible.append((facts, index, commitment_option))

    if not eligible:
        return no_action_strategy_result(
            strategy_mode_facts=strategy_mode_facts,
            notes=_no_action_notes(ineligible_reasons),
        )

    selection_pool, preference_note = _owned_production_retention_pool(
        eligible,
        effective_config.owned_production_threat_report,
    )
    preference_notes: list[str] = []
    if preference_note is not None:
        preference_notes.append(preference_note)
    else:
        selection_pool, preference_note = _own_transfer_spam_reduction_pool(
            eligible,
            effective_config.own_transfer_intent_report,
        )
        if preference_note is not None:
            preference_notes.append(preference_note)
        selection_pool, preference_note = _pressure_retention_pool(selection_pool)
        if preference_note is not None:
            preference_notes.append(preference_note)
        else:
            selection_pool, preference_note = _enemy_denial_pool(
                selection_pool,
                effective_config.enemy_denial_opportunity_report,
            )
            if preference_note is not None:
                preference_notes.append(preference_note)
    selected_facts, _index, selected_commitment = max(
        selection_pool,
        key=_selection_key,
    )
    notes = [
        "two-player direct advantage selected",
        f"selected commitment option: {selected_commitment.option_type.value}",
    ]
    notes.extend(preference_notes)
    return selected_strategy_result(
        selected_facts.bundle,
        selected_commitment,
        notes=tuple(notes),
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
    *,
    prefer_capture_and_hold: bool = False,
) -> CommitmentOption | None:
    if bundle.commitment_options is None:
        return None
    if prefer_capture_and_hold:
        reserve = _validated_option(
            bundle,
            CommitmentOptionType.RESERVE_PRESERVING,
        )
        if reserve is None:
            capture_and_hold = _validated_option(
                bundle,
                CommitmentOptionType.CAPTURE_AND_HOLD,
            )
            if capture_and_hold is not None:
                return capture_and_hold
    for preferred_option_type in commitment_preference_order:
        if preferred_option_type is CommitmentOptionType.NO_ATTACK:
            continue
        option = _validated_option(bundle, preferred_option_type)
        if option is not None:
            return option
    return None


def _validated_option(
    bundle: PlannerDecisionBundle,
    option_type: CommitmentOptionType,
) -> CommitmentOption | None:
    if bundle.commitment_options is None:
        return None
    if option_type is CommitmentOptionType.NO_ATTACK:
        return None
    for option in bundle.commitment_options.options:
        if (
            option.option_type is option_type
            and option.status is CommitmentOptionStatus.VALIDATED
        ):
            return option
    return None


def _pressure_retention_pool(
    eligible: list[tuple[TwoPlayerAdvantageFacts, int, CommitmentOption]],
) -> tuple[list[tuple[TwoPlayerAdvantageFacts, int, CommitmentOption]], str | None]:
    pressure_facts = tuple(
        two_player_pressure_facts(facts, commitment_option)
        for facts, _index, commitment_option in eligible
    )
    if not any(facts.response_pressure_active for facts in pressure_facts):
        return eligible, None
    reserve_preserving = [
        item
        for item, facts in zip(eligible, pressure_facts)
        if facts.reserve_preserving_commitment
    ]
    retention_candidates = [
        item
        for item in reserve_preserving
        if _is_owned_retention_candidate(item[0].bundle)
    ]
    if retention_candidates:
        return retention_candidates, "pressure retention preference: reserve_preserving"
    hold_sized_captures = [
        item
        for item in eligible
        if (
            _is_risky_capture_facts(item[0])
            and item[2].option_type is CommitmentOptionType.CAPTURE_AND_HOLD
        )
    ]
    if hold_sized_captures:
        return hold_sized_captures, "pressure capture-hold preference: capture_and_hold"
    if not reserve_preserving:
        return eligible, None
    return reserve_preserving, "pressure retention preference: reserve_preserving"


def _owned_production_retention_pool(
    eligible: list[tuple[TwoPlayerAdvantageFacts, int, CommitmentOption]],
    threat_report: OwnedProductionThreatReport | None,
) -> tuple[list[tuple[TwoPlayerAdvantageFacts, int, CommitmentOption]], str | None]:
    if (
        threat_report is None
        or threat_report.player_id is None
        or threat_report.production_pressure_count <= 0
    ):
        return eligible, None

    retention_candidates = [
        item
        for item in eligible
        if _is_owned_retention_candidate(item[0].bundle)
        and item[2].option_type is CommitmentOptionType.RESERVE_PRESERVING
    ]
    if retention_candidates:
        return (
            retention_candidates,
            "owned-production pressure preference: reserve_preserving retention",
        )

    any_retention_candidates = [
        item for item in eligible if _is_owned_retention_candidate(item[0].bundle)
    ]
    if any_retention_candidates:
        return (
            any_retention_candidates,
            "owned-production pressure preference: owned retention",
        )

    non_draining_reserve_candidates = [
        item
        for item in eligible
        if item[2].option_type is CommitmentOptionType.RESERVE_PRESERVING
        and not _bundle_uses_pressured_source(item[0].bundle, threat_report)
    ]
    if non_draining_reserve_candidates:
        return (
            non_draining_reserve_candidates,
            "owned-production pressure preference: non-draining reserve",
        )

    reserve_candidates = [
        item
        for item in eligible
        if item[2].option_type is CommitmentOptionType.RESERVE_PRESERVING
    ]
    if reserve_candidates:
        return (
            reserve_candidates,
            "owned-production pressure preference: reserve_preserving",
        )

    return eligible, None


def _allow_below_minimum_under_owned_pressure(
    facts: TwoPlayerAdvantageFacts,
    commitment_option: CommitmentOption,
    threat_report: OwnedProductionThreatReport | None,
) -> bool:
    if (
        threat_report is None
        or threat_report.player_id is None
        or threat_report.production_pressure_count <= 0
    ):
        return False
    if _is_owned_retention_candidate(facts.bundle):
        return True
    return commitment_option.option_type is CommitmentOptionType.RESERVE_PRESERVING


def _own_transfer_spam_reduction_pool(
    eligible: list[tuple[TwoPlayerAdvantageFacts, int, CommitmentOption]],
    transfer_report: OwnTransferIntentReport | None,
) -> tuple[list[tuple[TwoPlayerAdvantageFacts, int, CommitmentOption]], str | None]:
    if (
        transfer_report is None
        or transfer_report.player_id is None
        or transfer_report.potentially_spammy_count <= 0
    ):
        return eligible, None
    productive_alternatives = [
        item for item in eligible if _is_productive_non_transfer_candidate(item[0])
    ]
    if not productive_alternatives:
        return eligible, None
    return (
        productive_alternatives,
        "own-transfer spam preference: productive alternative",
    )


def _enemy_denial_pool(
    eligible: list[tuple[TwoPlayerAdvantageFacts, int, CommitmentOption]],
    denial_report: EnemyDenialOpportunityReport | None,
) -> tuple[list[tuple[TwoPlayerAdvantageFacts, int, CommitmentOption]], str | None]:
    if (
        denial_report is None
        or denial_report.player_id is None
        or denial_report.high_value_denial_count <= 0
    ):
        return eligible, None
    high_value_target_ids = {
        facts.target_planet_id
        for facts in denial_report.target_facts
        if facts.high_value_denial
    }
    if not high_value_target_ids:
        return eligible, None
    high_value_denial_candidates = [
        item
        for item in eligible
        if _is_high_value_enemy_denial_candidate(item[0], high_value_target_ids)
    ]
    if not high_value_denial_candidates:
        return eligible, None
    return (
        high_value_denial_candidates,
        "enemy-production denial preference: high_value_denial",
    )


def _is_high_value_enemy_denial_candidate(
    facts: TwoPlayerAdvantageFacts,
    high_value_target_ids: set[int],
) -> bool:
    return (
        facts.bundle.candidate.mission_type is MissionType.ATTACK_ENEMY
        and facts.bundle.candidate.target_planet_id in high_value_target_ids
        and facts.target_taken_from_opponent is True
        and _int_or_zero(facts.opponent_production_denied) > 0
    )


def _is_productive_non_transfer_candidate(facts: TwoPlayerAdvantageFacts) -> bool:
    if _is_owned_retention_candidate(facts.bundle):
        return False
    if facts.bundle.candidate.mission_type not in (
        MissionType.CAPTURE_NEUTRAL,
        MissionType.ATTACK_ENEMY,
    ):
        return False
    return (
        facts.target_captured_by_player is True
        or facts.target_taken_from_opponent is True
        or _int_or_zero(facts.production_delta_vs_baseline) > 0
        or _int_or_zero(facts.opponent_production_denied) > 0
    )


def _is_owned_retention_candidate(bundle: PlannerDecisionBundle) -> bool:
    return bundle.candidate.mission_type in (
        MissionType.DEFEND_OWN,
        MissionType.REINFORCE,
    )


def _bundle_uses_pressured_source(
    bundle: PlannerDecisionBundle,
    threat_report: OwnedProductionThreatReport,
) -> bool:
    pressured_planet_ids = {
        facts.planet_id
        for facts in threat_report.planet_facts
        if facts.production_under_pressure
    }
    return any(
        source_planet_id in pressured_planet_ids
        for source_planet_id in bundle.candidate.source_planet_ids
    )


def _is_risky_capture_facts(facts: TwoPlayerAdvantageFacts) -> bool:
    if facts.bundle.candidate.mission_type not in (
        MissionType.CAPTURE_NEUTRAL,
        MissionType.ATTACK_ENEMY,
    ):
        return False
    return any(
        label in CAPTURE_HOLD_RISK_RESPONSE_LABELS
        for label in facts.response_labels
    )


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
