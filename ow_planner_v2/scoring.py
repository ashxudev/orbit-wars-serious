"""Planner V2 bounded scenario scoring."""

from __future__ import annotations

from collections.abc import Sequence

from .types import ActionSetPlan, BoardDiagnosis, EvaluatedPlan, MissionFamily, PlannerV2Config


def score_action_set_plans(
    action_sets: Sequence[ActionSetPlan],
    diagnosis: BoardDiagnosis,
    config: PlannerV2Config | None = None,
) -> tuple[EvaluatedPlan, ...]:
    """Return deterministic scores for candidate action sets."""

    effective_config = PlannerV2Config() if config is None else config
    horizons = _scoring_horizons(diagnosis, effective_config)
    evaluated = [
        _evaluated_plan(plan, diagnosis, horizons)
        for plan in action_sets
    ]
    return tuple(
        sorted(
            evaluated,
            key=lambda plan: (-plan.score, plan.plan.plan_id),
        )
    )


def _evaluated_plan(
    plan: ActionSetPlan,
    diagnosis: BoardDiagnosis,
    horizons: tuple[int, ...],
) -> EvaluatedPlan:
    base_components = _score_components(plan, diagnosis)
    base_score = sum(value for _name, value in base_components)
    horizon_scores = tuple(
        (horizon, _score_for_horizon(base_score, plan, diagnosis, horizon))
        for horizon in horizons
    )
    selected_horizon, selected_score = max(
        horizon_scores,
        key=lambda item: (item[1], -item[0]),
    )
    return EvaluatedPlan(
        plan=plan,
        score=selected_score,
        score_components=base_components,
        horizon_scores=horizon_scores,
        selected_horizon=selected_horizon,
        labels=plan.labels,
    )


def _score_components(
    plan: ActionSetPlan,
    diagnosis: BoardDiagnosis,
) -> tuple[tuple[str, float], ...]:
    family = plan.missions[0].family if plan.missions else None
    components: list[tuple[str, float]] = []
    components.append(("mission_priority", plan.missions[0].priority if plan.missions else 0.0))
    components.append(("action_tempo", 5.0 if plan.launches else -50.0))
    components.append(("reserve_bonus", 10.0 if "reserve_preserving" in plan.labels else 0.0))
    if diagnosis.vulnerable_owned_planet_ids and family is MissionFamily.URGENT_DEFEND:
        components.append(("owned_production_survival", 100.0))
    if family is MissionFamily.ENEMY_PRODUCTION_DENIAL:
        components.append(("enemy_production_denial", 30.0))
    if family is MissionFamily.HOLD_CAPTURE:
        components.append(("recapture_risk_control", 15.0))
    if family in (MissionFamily.LEADER_PRESSURE, MissionFamily.RANK_SWING):
        components.append(("rank_swing", 25.0))
    if family is MissionFamily.LATE_LIQUIDATION:
        components.append(("late_liquidation", 35.0))
    if family is MissionFamily.SAFE_EXPAND:
        components.append(("production_gain", 20.0))
    if len(plan.missions) > 1:
        components.append(("coordination_bonus", 12.0))
    if "own_transfer_context_visible" in diagnosis.labels and family is MissionFamily.FUNNEL_FOR_DOWNSTREAM_ATTACK:
        components.append(("own_transfer_spam_cost", -20.0))
    if diagnosis.mode.value == "four_player" and family in (
        MissionFamily.LEADER_PRESSURE,
        MissionFamily.RANK_SWING,
        MissionFamily.SAFE_EXPAND,
    ):
        components.append(("four_player_continuation", 15.0))
    ships_committed = sum(launch.ships for launch in plan.launches)
    components.append(("source_vulnerability_cost", -0.1 * ships_committed))
    if diagnosis.source_drain_risk_planet_ids:
        risky_source_ids = set(diagnosis.source_drain_risk_planet_ids)
        risky_committed = sum(
            launch.ships for launch in plan.launches if launch.source_planet_id in risky_source_ids
        )
        components.append(("source_drain_risk_cost", -0.5 * risky_committed))
    return tuple(components)


def _scoring_horizons(
    diagnosis: BoardDiagnosis,
    config: PlannerV2Config,
) -> tuple[int, ...]:
    horizons = list(config.horizons)
    if diagnosis.mode.value == "endgame" or "late_game_state" in diagnosis.labels:
        horizons.append(config.endgame_horizon)
    return tuple(dict.fromkeys(horizons))


def _score_for_horizon(
    base_score: float,
    plan: ActionSetPlan,
    diagnosis: BoardDiagnosis,
    horizon: int,
) -> float:
    family = plan.missions[0].family if plan.missions else None
    score = base_score
    if horizon >= 25 and family in (
        MissionFamily.SAFE_EXPAND,
        MissionFamily.ENEMY_PRODUCTION_DENIAL,
        MissionFamily.LEADER_PRESSURE,
        MissionFamily.RANK_SWING,
    ):
        score += 5.0
    if horizon >= 50 and diagnosis.mode.value == "four_player" and family in (
        MissionFamily.LEADER_PRESSURE,
        MissionFamily.RANK_SWING,
    ):
        score += 10.0
    if horizon >= 50 and diagnosis.vulnerable_owned_planet_ids and family is not MissionFamily.URGENT_DEFEND:
        score -= 15.0
    if horizon >= 75 and family is MissionFamily.LATE_LIQUIDATION:
        score += 20.0
    return score


__all__ = ("score_action_set_plans",)
