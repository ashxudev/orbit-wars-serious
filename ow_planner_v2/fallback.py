"""Planner V2 fallback ladder and final plan selection."""

from __future__ import annotations

from collections.abc import Sequence

from .types import BoardDiagnosis, EvaluatedPlan, MissionFamily, PlannerV2Config


def select_evaluated_plan(
    evaluated_plans: Sequence[EvaluatedPlan],
    diagnosis: BoardDiagnosis,
    config: PlannerV2Config | None = None,
) -> tuple[EvaluatedPlan | None, str | None, tuple[str, ...]]:
    """Select a V2 plan or return an explicit no-action reason."""

    effective_config = PlannerV2Config() if config is None else config
    if not evaluated_plans:
        if diagnosis.owned_planet_count == 0:
            return None, "source_less_no_owned_planets", ("no owned planets",)
        return None, "no_action_sets_generated", ("no validated action sets",)

    ordered = sorted(
        evaluated_plans,
        key=lambda plan: (_fallback_rank(plan, diagnosis), -plan.score, plan.plan.plan_id),
    )
    selected = ordered[0]
    if selected.score < effective_config.minimum_plan_score:
        return (
            None,
            "all_plans_below_minimum_score",
            (
                f"best_score={selected.score}",
                f"minimum_plan_score={effective_config.minimum_plan_score}",
                f"evaluated_plan_count={len(evaluated_plans)}",
            ),
        )
    return selected, None, (
        "fallback ladder selected plan",
        f"family={selected.plan.missions[0].family.value if selected.plan.missions else 'none'}",
        f"score={selected.score}",
    )


def _fallback_rank(plan: EvaluatedPlan, diagnosis: BoardDiagnosis) -> int:
    family = plan.plan.missions[0].family if plan.plan.missions else None
    if diagnosis.vulnerable_owned_planet_ids and family is MissionFamily.URGENT_DEFEND:
        return 0
    if diagnosis.mode.value == "two_player" and family is MissionFamily.ENEMY_PRODUCTION_DENIAL:
        return 1
    if (
        diagnosis.mode.value == "four_player"
        and (diagnosis.rank_labels or diagnosis.plateau_labels)
        and family in (
        MissionFamily.LEADER_PRESSURE,
        MissionFamily.RANK_SWING,
        )
    ):
        return 1
    if diagnosis.mode.value == "endgame" and family is MissionFamily.LATE_LIQUIDATION:
        return 1
    order = {
        MissionFamily.SAFE_EXPAND: 2,
        MissionFamily.ENEMY_PRODUCTION_DENIAL: 3,
        MissionFamily.LEADER_PRESSURE: 4,
        MissionFamily.RANK_SWING: 5,
        MissionFamily.FUNNEL_FOR_DOWNSTREAM_ATTACK: 5,
        MissionFamily.LATE_LIQUIDATION: 6,
    }
    return order.get(family, 7)


__all__ = ("select_evaluated_plan",)
