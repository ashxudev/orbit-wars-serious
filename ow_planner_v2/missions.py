"""Mission-family helpers for Planner V2."""

from __future__ import annotations

from ow_planner import MissionCandidate, MissionEvaluation, MissionType

from .types import BoardDiagnosis, MissionFamily


def mission_family_for_candidate(
    candidate: MissionCandidate,
    diagnosis: BoardDiagnosis,
    evaluation: MissionEvaluation | None = None,
) -> MissionFamily:
    """Classify a V1 candidate into a V2 mission family."""

    if candidate.note == "planner_v2_surface:trajectory_preserve_source":
        return MissionFamily.HOLD_CAPTURE
    if len(candidate.launches) > 1 or len(candidate.source_planet_ids) > 1:
        return MissionFamily.MULTI_SOURCE_CAPTURE
    if candidate.mission_type in (MissionType.DEFEND_OWN, MissionType.REINFORCE):
        if diagnosis.vulnerable_owned_planet_ids:
            return MissionFamily.URGENT_DEFEND
        return MissionFamily.FUNNEL_FOR_DOWNSTREAM_ATTACK
    if candidate.mission_type is MissionType.CAPTURE_NEUTRAL:
        if _looks_like_recapture(candidate, diagnosis):
            return MissionFamily.RECAPTURE
        if candidate.target_planet_id in diagnosis.high_value_target_ids:
            return MissionFamily.SAFE_EXPAND
        if _capture_needs_hold(evaluation):
            return MissionFamily.HOLD_CAPTURE
        return MissionFamily.HOLD_CAPTURE
    if candidate.mission_type is MissionType.ATTACK_ENEMY:
        if candidate.target_planet_id in diagnosis.high_value_target_ids:
            if diagnosis.mode.value == "four_player":
                return MissionFamily.LEADER_PRESSURE
            return MissionFamily.ENEMY_PRODUCTION_DENIAL
        if _is_late_liquidation(diagnosis):
            return MissionFamily.LATE_LIQUIDATION
        return MissionFamily.RANK_SWING
    return MissionFamily.FUNNEL_FOR_DOWNSTREAM_ATTACK


def mission_priority(family: MissionFamily, diagnosis: BoardDiagnosis) -> float:
    """Return deterministic family priority for the current diagnosis."""

    if diagnosis.vulnerable_owned_planet_ids and family is MissionFamily.URGENT_DEFEND:
        return 100.0
    priorities = {
        MissionFamily.SAFE_EXPAND: 80.0,
        MissionFamily.ENEMY_PRODUCTION_DENIAL: 75.0,
        MissionFamily.LEADER_PRESSURE: 70.0,
        MissionFamily.RANK_SWING: 65.0,
        MissionFamily.HOLD_CAPTURE: 60.0,
        MissionFamily.MULTI_SOURCE_CAPTURE: 58.0,
        MissionFamily.RECAPTURE: 55.0,
        MissionFamily.FUNNEL_FOR_DOWNSTREAM_ATTACK: 30.0,
        MissionFamily.LATE_LIQUIDATION: 25.0,
        MissionFamily.URGENT_DEFEND: 20.0,
    }
    return priorities[family]


def _looks_like_recapture(candidate: MissionCandidate, diagnosis: BoardDiagnosis) -> bool:
    return (
        candidate.target_planet_id in diagnosis.vulnerable_owned_planet_ids
        or "owned_planet_likely_flip" in diagnosis.pressure_labels
    )


def _capture_needs_hold(evaluation: MissionEvaluation | None) -> bool:
    if evaluation is None or evaluation.facts is None:
        return False
    target = evaluation.facts.target_mission
    return target is not None and target.owner is not None and target.ships <= 3


def _is_late_liquidation(diagnosis: BoardDiagnosis) -> bool:
    return (
        diagnosis.mode.value == "endgame"
        or (
            diagnosis.neutral_production == 0
            and diagnosis.owned_production <= diagnosis.opponent_production
            and diagnosis.owned_planet_count <= 2
        )
    )


__all__ = ("mission_family_for_candidate", "mission_priority")
