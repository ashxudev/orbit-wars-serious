"""JSON-safe Planner V2 diagnostics helpers."""

from __future__ import annotations

from .types import PlannerV2Result


def planner_v2_diagnostics(result: PlannerV2Result) -> dict[str, object]:
    """Return compact JSON-safe diagnostics for a V2 result."""

    if not isinstance(result, PlannerV2Result):
        raise ValueError("result must be a PlannerV2Result")
    selected = result.selected_plan
    return {
        "planner_v2_action_count": len(result.actions),
        "planner_v2_action_set_count": len(result.action_sets),
        "planner_v2_diagnosis_labels": list(result.diagnosis.labels),
        "planner_v2_evaluated_plan_count": len(result.evaluated_plans),
        "planner_v2_mission_count": len(result.missions),
        "planner_v2_no_action_reason": result.no_action_reason,
        "planner_v2_selected_family": (
            None
            if selected is None or not selected.plan.missions
            else selected.plan.missions[0].family.value
        ),
        "planner_v2_selected_horizon": None if selected is None else selected.selected_horizon,
        "planner_v2_selected_plan_id": None if selected is None else selected.plan.plan_id,
        "planner_v2_selected_score": None if selected is None else selected.score,
    }


__all__ = ("planner_v2_diagnostics",)
