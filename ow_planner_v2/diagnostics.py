"""JSON-safe Planner V2 diagnostics helpers."""

from __future__ import annotations

from .types import PlannerV2Result


def planner_v2_diagnostics(result: PlannerV2Result) -> dict[str, object]:
    """Return compact JSON-safe diagnostics for a V2 result."""

    if not isinstance(result, PlannerV2Result):
        raise ValueError("result must be a PlannerV2Result")
    selected = result.selected_plan
    scenario = None if selected is None else selected.scenario_evaluation
    funnel = result.funnel_diagnostics
    action_set_report = None if funnel is None else funnel.action_set_report
    selected_outcome = None
    if scenario is not None and selected is not None:
        for outcome in scenario.outcomes:
            if outcome.horizon == selected.selected_horizon:
                selected_outcome = outcome
                break
    selected_fallback_rank = None
    if funnel is not None and selected is not None:
        for record in funnel.fallback_ranks:
            if record.selected:
                selected_fallback_rank = record.rank
                break
    return {
        "planner_v2_action_count": len(result.actions),
        "planner_v2_action_set_count": len(result.action_sets),
        "planner_v2_diagnosis_labels": list(result.diagnosis.labels),
        "planner_v2_evaluated_plan_count": len(result.evaluated_plans),
        "planner_v2_kept_action_set_count": (
            len(result.action_sets)
            if action_set_report is None
            else len(action_set_report.kept_action_sets)
        ),
        "planner_v2_mission_count": len(result.missions),
        "planner_v2_mission_family_counts": _mission_family_counts(result),
        "planner_v2_no_action_reason": result.no_action_reason,
        "planner_v2_pre_cap_single_action_set_count": (
            None
            if action_set_report is None
            else len(action_set_report.single_action_sets)
        ),
        "planner_v2_pruned_action_set_count": (
            None
            if action_set_report is None
            else len(action_set_report.pruned_action_sets)
        ),
        "planner_v2_prune_reason_counts": (
            {}
            if action_set_report is None
            else _prune_reason_counts(result)
        ),
        "planner_v2_selected_family": (
            None
            if selected is None or not selected.plan.missions
            else selected.plan.missions[0].family.value
        ),
        "planner_v2_selected_fallback_rank": selected_fallback_rank,
        "planner_v2_selected_horizon": None if selected is None else selected.selected_horizon,
        "planner_v2_selected_plan_id": None if selected is None else selected.plan.plan_id,
        "planner_v2_selected_score": None if selected is None else selected.score,
        "planner_v2_selected_score_components": (
            []
            if selected is None
            else [
                {"name": name, "value": value}
                for name, value in selected.score_components
            ]
        ),
        "planner_v2_selected_scenario_notes": (
            []
            if selected_outcome is None
            else list(selected_outcome.notes)
        ),
        "planner_v2_selected_scenario_valid": (
            None
            if scenario is None
            else scenario.valid
        ),
    }


def _mission_family_counts(result: PlannerV2Result) -> dict[str, int]:
    counts: dict[str, int] = {}
    for mission in result.missions:
        counts[mission.family.value] = counts.get(mission.family.value, 0) + 1
    return {key: counts[key] for key in sorted(counts)}


def _prune_reason_counts(result: PlannerV2Result) -> dict[str, int]:
    if result.funnel_diagnostics is None:
        return {}
    counts: dict[str, int] = {}
    for record in result.funnel_diagnostics.action_set_report.pruned_action_sets:
        counts[record.reason] = counts.get(record.reason, 0) + 1
    return {key: counts[key] for key in sorted(counts)}


__all__ = ("planner_v2_diagnostics",)
