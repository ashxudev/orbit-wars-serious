"""Planner V2 action-set construction."""

from __future__ import annotations

from collections.abc import Sequence

from ow_planner import (
    CandidateCommitmentOptions,
    CommitmentOption,
    CommitmentOptionStatus,
    CommitmentOptionType,
)

from .types import ActionSetPlan, MissionFamily, MissionPlan, PlannerV2Config


def build_action_set_plans(
    missions: Sequence[MissionPlan],
    commitment_options: Sequence[CandidateCommitmentOptions],
    config: PlannerV2Config | None = None,
) -> tuple[ActionSetPlan, ...]:
    """Build bounded action-set plans from generated missions."""

    effective_config = PlannerV2Config() if config is None else config
    if effective_config.max_action_sets == 0:
        return ()
    commitments_by_candidate = {
        id(candidate_options.candidate): candidate_options
        for candidate_options in commitment_options
    }
    plans: list[ActionSetPlan] = []
    single_plans: list[ActionSetPlan] = []
    for mission in missions:
        if mission.candidate is None:
            continue
        candidate_options = commitments_by_candidate.get(id(mission.candidate))
        option = _best_commitment_option(candidate_options)
        if option is None:
            continue
        plan = (
            ActionSetPlan(
                plan_id=f"action-set-{len(plans):04d}",
                missions=(mission,),
                launches=option.launches,
                commitment_option=option,
                labels=_action_set_labels(mission, option),
            )
        )
        plans.append(plan)
        single_plans.append(plan)
        if (
            effective_config.max_action_sets is not None
            and len(plans) >= effective_config.max_action_sets
        ):
            return tuple(plans)
    if effective_config.max_missions_per_action_set > 1:
        for first in single_plans:
            for second in single_plans:
                if first.plan_id >= second.plan_id:
                    continue
                combined = _combined_action_set(first, second, plan_index=len(plans))
                if combined is None:
                    continue
                plans.append(combined)
                if (
                    effective_config.max_action_sets is not None
                    and len(plans) >= effective_config.max_action_sets
                ):
                    return tuple(plans)
    return tuple(plans)


def _best_commitment_option(
    candidate_options: CandidateCommitmentOptions | None,
) -> CommitmentOption | None:
    if candidate_options is None:
        return None
    validated = tuple(
        option
        for option in candidate_options.options
        if (
            option.status is CommitmentOptionStatus.VALIDATED
            and option.option_type is not CommitmentOptionType.NO_ATTACK
            and option.launches
        )
    )
    if not validated:
        return None
    preference = {
        CommitmentOptionType.RESERVE_PRESERVING: 0,
        CommitmentOptionType.CAPTURE_AND_HOLD: 1,
        CommitmentOptionType.COORDINATED_MULTI_SOURCE: 2,
        CommitmentOptionType.MINIMUM_CAPTURE: 3,
        CommitmentOptionType.FULL_SOURCE: 4,
    }
    return min(
        validated,
        key=lambda option: (
            preference.get(option.option_type, 99),
            option.ships_committed,
            option.option_type.value,
        ),
    )


def _action_set_labels(
    mission: MissionPlan,
    option: CommitmentOption,
) -> tuple[str, ...]:
    labels = [mission.family.value, option.option_type.value]
    if mission.family in (
        MissionFamily.URGENT_DEFEND,
        MissionFamily.ENEMY_PRODUCTION_DENIAL,
        MissionFamily.LEADER_PRESSURE,
        MissionFamily.RANK_SWING,
    ):
        labels.append("productive_response")
    if len(option.launches) > 1:
        labels.append("coordinated")
    return tuple(dict.fromkeys(labels))


def _combined_action_set(
    first: ActionSetPlan,
    second: ActionSetPlan,
    *,
    plan_index: int,
) -> ActionSetPlan | None:
    if _source_ids(first) & _source_ids(second):
        return None
    if not _useful_combination(first, second):
        return None
    labels = [
        "coordinated_action_set",
        *first.labels,
        *second.labels,
    ]
    return ActionSetPlan(
        plan_id=f"action-set-{plan_index:04d}",
        missions=first.missions + second.missions,
        launches=first.launches + second.launches,
        commitment_option=first.commitment_option,
        labels=tuple(dict.fromkeys(labels)),
    )


def _source_ids(plan: ActionSetPlan) -> set[int]:
    return {launch.source_planet_id for launch in plan.launches}


def _useful_combination(first: ActionSetPlan, second: ActionSetPlan) -> bool:
    families = {
        mission.family
        for mission in first.missions + second.missions
    }
    if MissionFamily.URGENT_DEFEND in families and (
        MissionFamily.SAFE_EXPAND in families
        or MissionFamily.ENEMY_PRODUCTION_DENIAL in families
        or MissionFamily.LEADER_PRESSURE in families
        or MissionFamily.RANK_SWING in families
    ):
        return True
    if MissionFamily.LEADER_PRESSURE in families and MissionFamily.FUNNEL_FOR_DOWNSTREAM_ATTACK in families:
        return True
    return False


__all__ = ("build_action_set_plans",)
