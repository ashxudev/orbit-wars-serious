"""Planner V2 mission surface generation."""

from __future__ import annotations

from collections.abc import Sequence

from ow_planner import MissionCandidate, MissionEvaluation

from .missions import mission_family_for_candidate, mission_priority
from .types import (
    BoardDiagnosis,
    MissionFamily,
    MissionPlan,
    PlannerV2Config,
    TrajectoryDiagnosis,
    TrajectoryObjective,
)


def generate_mission_plans(
    diagnosis: BoardDiagnosis,
    candidates: Sequence[MissionCandidate],
    evaluations: Sequence[MissionEvaluation] = (),
    config: PlannerV2Config | None = None,
    trajectory_diagnosis: TrajectoryDiagnosis | None = None,
) -> tuple[MissionPlan, ...]:
    """Generate bounded V2 missions from current candidates and diagnosis."""

    effective_config = PlannerV2Config() if config is None else config
    if effective_config.max_missions == 0:
        return ()
    evaluations_by_candidate = {id(evaluation.candidate): evaluation for evaluation in evaluations}
    missions: list[MissionPlan] = []
    for index, candidate in enumerate(candidates):
        evaluation = evaluations_by_candidate.get(id(candidate))
        family = mission_family_for_candidate(candidate, diagnosis, evaluation)
        missions.append(
            MissionPlan(
                mission_id=f"mission-{index:04d}",
                family=family,
                mission_type=candidate.mission_type,
                candidate=candidate,
                evaluation=evaluation,
                target_planet_id=candidate.target_planet_id,
                source_planet_ids=candidate.source_planet_ids,
                trajectory_objectives=_trajectory_objectives_for_candidate(
                    candidate,
                    trajectory_diagnosis,
                ),
                trajectory_target_planet_ids=_trajectory_targets_for_candidate(
                    candidate,
                    trajectory_diagnosis,
                ),
                priority=mission_priority(family, diagnosis),
                labels=_mission_labels(candidate, diagnosis),
            )
        )
        if (
            effective_config.max_missions is not None
            and len(missions) >= effective_config.max_missions
        ):
            break
    if missions:
        return tuple(missions)
    return _diagnostic_missions(diagnosis, effective_config)


def _trajectory_objectives_for_candidate(
    candidate: MissionCandidate,
    trajectory_diagnosis: TrajectoryDiagnosis | None,
) -> tuple[TrajectoryObjective, ...]:
    if trajectory_diagnosis is None:
        return ()
    if candidate.note == "planner_v2_surface:trajectory_preserve_source":
        return tuple(
            objective
            for objective in (
                TrajectoryObjective.PRESERVE_PRIMARY_SOURCE,
                TrajectoryObjective.HOLD_RECENT_CAPTURE,
            )
            if objective in trajectory_diagnosis.recommended_objectives
        )
    if candidate.note == "planner_v2_surface:trajectory_second_source":
        return tuple(
            objective
            for objective in (
                TrajectoryObjective.SECURE_SECOND_SOURCE,
                TrajectoryObjective.CAPTURE_NEAREST_PRODUCTIVE_NEUTRAL,
            )
            if objective in trajectory_diagnosis.recommended_objectives
        )
    return ()


def _trajectory_targets_for_candidate(
    candidate: MissionCandidate,
    trajectory_diagnosis: TrajectoryDiagnosis | None,
) -> tuple[int, ...]:
    if trajectory_diagnosis is None:
        return ()
    if (
        candidate.note == "planner_v2_surface:trajectory_preserve_source"
        and candidate.target_planet_id in trajectory_diagnosis.preservation_target_planet_ids
    ):
        return (candidate.target_planet_id,)
    if (
        candidate.note == "planner_v2_surface:trajectory_second_source"
        and candidate.target_planet_id in trajectory_diagnosis.nearest_productive_neutral_ids
    ):
        return (candidate.target_planet_id,)
    return ()


def _mission_labels(candidate: MissionCandidate, diagnosis: BoardDiagnosis) -> tuple[str, ...]:
    labels = []
    if candidate.target_planet_id in diagnosis.vulnerable_owned_planet_ids:
        labels.append("targets_vulnerable_owned_planet")
    if candidate.target_planet_id in diagnosis.high_value_target_ids:
        labels.append("targets_high_value_planet")
    if candidate.note == "planner_v2_surface:trajectory_preserve_source":
        labels.append("trajectory_preserve_source")
    if candidate.note == "planner_v2_surface:trajectory_second_source":
        labels.append("trajectory_second_source")
    if len(candidate.launches) > 1:
        labels.append("multi_launch")
    return tuple(labels)


def _diagnostic_missions(
    diagnosis: BoardDiagnosis,
    config: PlannerV2Config,
) -> tuple[MissionPlan, ...]:
    if config.max_missions == 0:
        return ()
    labels = ("diagnostic_only", "no_backing_candidate")
    if diagnosis.vulnerable_owned_planet_ids:
        return (
            MissionPlan(
                mission_id="mission-diagnostic-urgent-defense",
                family=MissionFamily.URGENT_DEFEND,
                priority=100.0,
                labels=labels,
            ),
        )
    return ()


__all__ = ("generate_mission_plans",)
