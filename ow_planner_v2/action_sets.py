"""Planner V2 action-set construction."""

from __future__ import annotations

from collections.abc import Sequence

from ow_planner import (
    CandidateCommitmentOptions,
    CommitmentOption,
    CommitmentOptionStatus,
    CommitmentOptionType,
)

from .types import (
    ActionSetCoverageReport,
    ActionSetPlan,
    ActionSetPruneRecord,
    MissionFamily,
    MissionPlan,
    PlannerV2Config,
)


def build_action_set_plans(
    missions: Sequence[MissionPlan],
    commitment_options: Sequence[CandidateCommitmentOptions],
    config: PlannerV2Config | None = None,
) -> tuple[ActionSetPlan, ...]:
    """Build bounded action-set plans from generated missions."""

    return build_action_set_report(
        missions,
        commitment_options,
        config,
    ).kept_action_sets


def build_action_set_report(
    missions: Sequence[MissionPlan],
    commitment_options: Sequence[CandidateCommitmentOptions],
    config: PlannerV2Config | None = None,
) -> ActionSetCoverageReport:
    """Build bounded action-set plans with minimal funnel diagnostics."""

    effective_config = PlannerV2Config() if config is None else config
    if effective_config.max_action_sets == 0:
        return ActionSetCoverageReport(
            single_action_sets=(),
            kept_action_sets=(),
        )
    commitments_by_candidate = {
        id(candidate_options.candidate): candidate_options
        for candidate_options in commitment_options
    }
    plans: list[ActionSetPlan] = []
    pruned: list[ActionSetPruneRecord] = []
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
                plan_id=f"action-set-{len(single_plans):04d}",
                missions=(mission,),
                launches=option.launches,
                commitment_option=option,
                labels=_action_set_labels(mission, option),
            )
        )
        single_plans.append(plan)
    selected_singles, pruned_singles = _diverse_single_action_sets(
        single_plans,
        effective_config,
    )
    plans.extend(selected_singles)
    pruned.extend(pruned_singles)
    if (
        effective_config.max_action_sets is not None
        and len(plans) >= effective_config.max_action_sets
    ):
        return ActionSetCoverageReport(
            single_action_sets=tuple(single_plans),
            kept_action_sets=tuple(plans),
            pruned_action_sets=tuple(pruned),
        )
    if effective_config.max_missions_per_action_set > 1:
        for first in single_plans:
            for second in single_plans:
                if first.plan_id >= second.plan_id:
                    continue
                if _source_ids(first) & _source_ids(second):
                    pruned.append(
                        ActionSetPruneRecord(
                            reason="shared_source_conflict",
                            mission_ids=_mission_ids(first, second),
                        )
                    )
                    continue
                combined = _combined_action_set(first, second, plan_index=len(plans))
                if combined is None:
                    continue
                if (
                    effective_config.max_action_sets is not None
                    and len(plans) >= effective_config.max_action_sets
                ):
                    pruned.append(
                        ActionSetPruneRecord(
                            reason="combined_plan_not_reached",
                            plan=combined,
                            mission_ids=_mission_ids(first, second),
                        )
                    )
                    continue
                plans.append(combined)
    return ActionSetCoverageReport(
        single_action_sets=tuple(single_plans),
        kept_action_sets=tuple(plans),
        pruned_action_sets=tuple(pruned),
    )


def _diverse_single_action_sets(
    single_plans: Sequence[ActionSetPlan],
    config: PlannerV2Config,
) -> tuple[tuple[ActionSetPlan, ...], tuple[ActionSetPruneRecord, ...]]:
    if config.max_action_sets is None:
        return tuple(single_plans), ()
    if config.max_action_sets <= 0:
        return (), tuple(
            ActionSetPruneRecord(reason="family_cap", plan=plan)
            for plan in single_plans
        )

    selected: list[ActionSetPlan] = []
    selected_ids: set[str] = set()
    pruned_by_priority_ids: set[str] = set()
    for family in _family_diversity_order():
        family_plans = tuple(
            plan
            for plan in single_plans
            if plan.missions and plan.missions[0].family is family
        )
        if not family_plans:
            continue
        plan = min(family_plans, key=_single_plan_preference_key)
        selected.append(plan)
        selected_ids.add(plan.plan_id)
        for lower_priority_plan in family_plans:
            if lower_priority_plan.plan_id == plan.plan_id:
                continue
            pruned_by_priority_ids.add(lower_priority_plan.plan_id)
        if len(selected) >= config.max_action_sets:
            return (
                tuple(selected),
                _single_prune_records(
                    single_plans,
                    selected_ids=selected_ids,
                    lower_priority_ids=pruned_by_priority_ids,
                ),
            )

    for plan in sorted(single_plans, key=_single_plan_preference_key):
        if plan.plan_id in selected_ids:
            continue
        selected.append(plan)
        selected_ids.add(plan.plan_id)
        if len(selected) >= config.max_action_sets:
            break
    return (
        tuple(selected),
        _single_prune_records(
            single_plans,
            selected_ids=selected_ids,
            lower_priority_ids=pruned_by_priority_ids,
        ),
    )


def _single_prune_records(
    single_plans: Sequence[ActionSetPlan],
    *,
    selected_ids: set[str],
    lower_priority_ids: set[str],
) -> tuple[ActionSetPruneRecord, ...]:
    records: list[ActionSetPruneRecord] = []
    for plan in single_plans:
        if plan.plan_id in selected_ids:
            continue
        reason = (
            "lower_family_priority"
            if plan.plan_id in lower_priority_ids
            else "family_cap"
        )
        records.append(ActionSetPruneRecord(reason=reason, plan=plan))
    return tuple(records)


def _family_diversity_order() -> tuple[MissionFamily, ...]:
    return (
        MissionFamily.SAFE_EXPAND,
        MissionFamily.URGENT_DEFEND,
        MissionFamily.HOLD_CAPTURE,
        MissionFamily.RECAPTURE,
        MissionFamily.ENEMY_PRODUCTION_DENIAL,
        MissionFamily.LEADER_PRESSURE,
        MissionFamily.RANK_SWING,
        MissionFamily.MULTI_SOURCE_CAPTURE,
        MissionFamily.FUNNEL_FOR_DOWNSTREAM_ATTACK,
        MissionFamily.LATE_LIQUIDATION,
    )


def _single_plan_preference_key(plan: ActionSetPlan) -> tuple[object, ...]:
    mission = plan.missions[0] if plan.missions else None
    return (
        -mission.priority if mission is not None else 0.0,
        0 if "reserve_preserving" in plan.labels else 1,
        sum(launch.ships for launch in plan.launches),
        mission.target_planet_id if mission is not None and mission.target_planet_id is not None else 10**9,
        plan.plan_id,
    )


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


def _mission_ids(first: ActionSetPlan, second: ActionSetPlan) -> tuple[str, ...]:
    return tuple(
        mission.mission_id
        for mission in first.missions + second.missions
    )


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


__all__ = ("build_action_set_plans", "build_action_set_report")
