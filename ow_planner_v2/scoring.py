"""Planner V2 bounded scenario scoring."""

from __future__ import annotations

from collections.abc import Sequence

from .types import (
    ActionSetPlan,
    BoardDiagnosis,
    EvaluatedPlan,
    MissionFamily,
    PlannerV2Config,
    PlannerV2Mode,
    ScenarioEvaluation,
    ScenarioOutcome,
    TrajectoryDiagnosis,
    TrajectoryObjective,
)


def score_action_set_plans(
    action_sets: Sequence[ActionSetPlan],
    diagnosis: BoardDiagnosis,
    config: PlannerV2Config | None = None,
    *,
    scenario_evaluations: Sequence[ScenarioEvaluation] = (),
    trajectory_diagnosis: TrajectoryDiagnosis | None = None,
) -> tuple[EvaluatedPlan, ...]:
    """Return deterministic scores for candidate action sets."""

    effective_config = PlannerV2Config() if config is None else config
    horizons = _scoring_horizons(diagnosis, effective_config)
    scenarios_by_plan_id = {
        evaluation.plan_id: evaluation
        for evaluation in scenario_evaluations
    }
    evaluated = [
        _evaluated_plan(
            plan,
            diagnosis,
            horizons,
            scenarios_by_plan_id.get(plan.plan_id),
            trajectory_diagnosis,
        )
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
    scenario_evaluation: ScenarioEvaluation | None,
    trajectory_diagnosis: TrajectoryDiagnosis | None,
) -> EvaluatedPlan:
    if scenario_evaluation is not None:
        return _scenario_evaluated_plan(
            plan,
            diagnosis,
            scenario_evaluation,
            trajectory_diagnosis,
        )

    base_components = _legacy_score_components(plan, diagnosis)
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
        scenario_evaluation=None,
        labels=plan.labels,
    )


def _scenario_evaluated_plan(
    plan: ActionSetPlan,
    diagnosis: BoardDiagnosis,
    scenario_evaluation: ScenarioEvaluation,
    trajectory_diagnosis: TrajectoryDiagnosis | None,
) -> EvaluatedPlan:
    components = _scenario_score_components(
        plan,
        diagnosis,
        scenario_evaluation,
        trajectory_diagnosis,
    )
    horizon_scores = tuple(
        (outcome.horizon, outcome.score)
        for outcome in scenario_evaluation.outcomes
    )
    if horizon_scores:
        selected_horizon, selected_score = max(
            horizon_scores,
            key=lambda item: (item[1], -item[0]),
        )
    else:
        selected_horizon, selected_score = None, -10000.0
    score = selected_score + sum(value for _name, value in components)
    return EvaluatedPlan(
        plan=plan,
        score=score,
        score_components=components,
        horizon_scores=horizon_scores,
        selected_horizon=selected_horizon,
        scenario_evaluation=scenario_evaluation,
        labels=plan.labels,
    )


def _legacy_score_components(
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


def _scenario_score_components(
    plan: ActionSetPlan,
    diagnosis: BoardDiagnosis,
    scenario_evaluation: ScenarioEvaluation,
    trajectory_diagnosis: TrajectoryDiagnosis | None = None,
) -> tuple[tuple[str, float], ...]:
    family = plan.missions[0].family if plan.missions else None
    components: list[tuple[str, float]] = []
    valid_outcomes = tuple(
        outcome for outcome in scenario_evaluation.outcomes if outcome.valid
    )
    if not scenario_evaluation.valid or not valid_outcomes:
        return (("invalid_scenario", -10000.0),)

    selected_outcome = max(
        valid_outcomes,
        key=lambda outcome: (outcome.score, -outcome.horizon),
    )
    worst_outcome = min(valid_outcomes, key=lambda outcome: (outcome.score, outcome.horizon))
    if len(valid_outcomes) > 1:
        components.append(("scenario_worst_score_guard", worst_outcome.score * 0.25))
    components.append(("mission_priority_tiebreak", _family_tiebreak(family) * 0.5))
    if plan.missions:
        components.append(("mission_priority_small", plan.missions[0].priority * 0.02))
    if "reserve_preserving" in plan.labels:
        components.append(("reserve_tiebreak", 1.0))
    if len(plan.missions) > 1:
        components.append(("coordination_tiebreak", 1.0))
    if diagnosis.vulnerable_owned_planet_ids and family is MissionFamily.URGENT_DEFEND:
        components.append(("urgent_defense_tiebreak", 2.0))
    if _should_delay_pressure_until_base_secured(family, trajectory_diagnosis):
        components.append(("base_security_ordering_guard", -50.0))
    if _should_delay_denial_until_trajectory_unlocked(family, trajectory_diagnosis):
        components.append(("trajectory_denial_locked_guard", -80.0))
    preservation_bonus = _trajectory_preservation_bonus(
        plan,
        diagnosis,
        valid_outcomes,
        trajectory_diagnosis,
    )
    if preservation_bonus:
        components.append(("trajectory_preservation_bonus", preservation_bonus))
    if _should_guard_fragile_non_improving_plan(
        family,
        diagnosis,
        valid_outcomes,
        trajectory_diagnosis,
    ):
        components.append(("fragile_base_non_improving_plan_guard", -120.0))
    if any(outcome.eliminated for outcome in valid_outcomes):
        components.append(("elimination_guard", -1000.0))
    if scenario_evaluation.has_source_loss:
        components.append(("source_loss_guard", -120.0))
        critical_source_loss = _critical_source_lost_production(
            valid_outcomes,
            diagnosis,
        )
        if critical_source_loss:
            components.append(
                (
                    "critical_source_production_loss_guard",
                    -180.0 * critical_source_loss,
                )
            )
    if selected_outcome.source_counterattack_lost_ids:
        components.append(("source_counterattack_guard", -180.0))
        counterattack_loss = selected_outcome.source_counterattack_lost_production
        if counterattack_loss:
            components.append(
                (
                    "source_counterattack_production_guard",
                    -140.0 * counterattack_loss,
                )
            )
    if selected_outcome.target_hold_failure_ids:
        components.append(("target_hold_failure_guard", -140.0))
        target_hold_failure_production = selected_outcome.target_hold_failure_production
        if target_hold_failure_production:
            components.append(
                (
                    "target_hold_failure_production_guard",
                    -80.0 * target_hold_failure_production,
                )
            )
    if scenario_evaluation.has_preservation_target_loss:
        components.append(("preservation_target_loss_guard", -160.0))
        preservation_loss = max(
            (
                outcome.preservation_target_lost_production
                for outcome in valid_outcomes
            ),
            default=0,
        )
        if preservation_loss:
            components.append(
                (
                    "preservation_target_production_loss_guard",
                    -120.0 * preservation_loss,
                )
            )
    if scenario_evaluation.has_vulnerable_loss:
        components.append(("vulnerable_loss_guard", -160.0))
        vulnerable_loss = max(
            (
                outcome.vulnerable_planet_lost_production
                for outcome in valid_outcomes
            ),
            default=0,
        )
        if vulnerable_loss:
            components.append(
                (
                    "vulnerable_production_loss_guard",
                    -120.0 * vulnerable_loss,
                )
            )
    ships_committed = sum(launch.ships for launch in plan.launches)
    components.append(("ship_commitment_cost", -0.05 * ships_committed))
    return tuple(components)


def _critical_source_lost_production(
    outcomes: Sequence[ScenarioOutcome],
    diagnosis: BoardDiagnosis,
) -> int:
    max_lost_production = max(
        (outcome.source_planet_lost_production for outcome in outcomes),
        default=0,
    )
    if max_lost_production <= 0:
        return 0
    if diagnosis.owned_planet_count <= 2:
        return max_lost_production
    if max_lost_production * 2 >= max(1, diagnosis.owned_production):
        return max_lost_production
    return 0


def _should_delay_pressure_until_base_secured(
    family: MissionFamily | None,
    trajectory_diagnosis: TrajectoryDiagnosis | None,
) -> bool:
    if trajectory_diagnosis is None:
        return False
    if family not in (
        MissionFamily.ENEMY_PRODUCTION_DENIAL,
        MissionFamily.LEADER_PRESSURE,
        MissionFamily.RANK_SWING,
    ):
        return False
    objectives = set(trajectory_diagnosis.recommended_objectives)
    if TrajectoryObjective.DELAY_ENEMY_DENIAL_UNTIL_BASE_SECURED not in objectives:
        return False
    labels = set(trajectory_diagnosis.labels)
    return bool({"under_expanded", "single_source_fragile"} & labels)


def _should_guard_fragile_non_improving_plan(
    family: MissionFamily | None,
    diagnosis: BoardDiagnosis,
    outcomes: Sequence[ScenarioOutcome],
    trajectory_diagnosis: TrajectoryDiagnosis | None,
) -> bool:
    if trajectory_diagnosis is None:
        return False
    if diagnosis.mode is not PlannerV2Mode.FOUR_PLAYER:
        return False
    if family is MissionFamily.URGENT_DEFEND:
        return False
    if trajectory_diagnosis.turn is None or trajectory_diagnosis.turn < 20:
        return False
    labels = set(trajectory_diagnosis.labels)
    if not {"under_expanded", "single_source_fragile"} & labels:
        return False
    objectives = set(trajectory_diagnosis.recommended_objectives)
    if not (
        TrajectoryObjective.SECURE_SECOND_SOURCE in objectives
        or TrajectoryObjective.CAPTURE_NEAREST_PRODUCTIVE_NEUTRAL in objectives
    ):
        return False
    return not any(
        outcome.target_owned_by_player_count > 0
        or outcome.own_production_delta > 0
        or outcome.own_planet_delta > 0
        for outcome in outcomes
        if outcome.valid
    )


def _should_delay_denial_until_trajectory_unlocked(
    family: MissionFamily | None,
    trajectory_diagnosis: TrajectoryDiagnosis | None,
) -> bool:
    if trajectory_diagnosis is None or trajectory_diagnosis.denial_unlocked:
        return False
    if family not in (
        MissionFamily.ENEMY_PRODUCTION_DENIAL,
        MissionFamily.LEADER_PRESSURE,
        MissionFamily.RANK_SWING,
    ):
        return False
    objectives = set(trajectory_diagnosis.recommended_objectives)
    return bool(
        {
            TrajectoryObjective.PRESERVE_PRIMARY_SOURCE,
            TrajectoryObjective.HOLD_RECENT_CAPTURE,
            TrajectoryObjective.SECURE_SECOND_SOURCE,
        }
        & objectives
    )


def _trajectory_preservation_bonus(
    plan: ActionSetPlan,
    diagnosis: BoardDiagnosis,
    outcomes: Sequence[ScenarioOutcome],
    trajectory_diagnosis: TrajectoryDiagnosis | None,
) -> float:
    if trajectory_diagnosis is None:
        return 0.0
    if diagnosis.mode is not PlannerV2Mode.FOUR_PLAYER:
        return 0.0
    if not plan.missions:
        return 0.0
    if not trajectory_diagnosis.preservation_target_planet_ids:
        return 0.0
    if not any(
        objective in plan.missions[0].trajectory_objectives
        for objective in (
            TrajectoryObjective.PRESERVE_PRIMARY_SOURCE,
            TrajectoryObjective.HOLD_RECENT_CAPTURE,
        )
    ):
        return 0.0
    if any(outcome.preservation_target_lost_ids for outcome in outcomes if outcome.valid):
        return 0.0
    target_count = len(plan.missions[0].trajectory_target_planet_ids)
    return 85.0 + target_count * 15.0


def _family_tiebreak(family: MissionFamily | None) -> float:
    order = {
        MissionFamily.URGENT_DEFEND: 7.0,
        MissionFamily.SAFE_EXPAND: 6.0,
        MissionFamily.HOLD_CAPTURE: 5.0,
        MissionFamily.RECAPTURE: 5.0,
        MissionFamily.ENEMY_PRODUCTION_DENIAL: 4.0,
        MissionFamily.LEADER_PRESSURE: 3.0,
        MissionFamily.RANK_SWING: 3.0,
        MissionFamily.MULTI_SOURCE_CAPTURE: 2.0,
        MissionFamily.FUNNEL_FOR_DOWNSTREAM_ATTACK: 1.0,
        MissionFamily.LATE_LIQUIDATION: 1.0,
    }
    return order.get(family, 0.0)


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
