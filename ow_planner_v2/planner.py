"""Planner V2 mission/search orchestration."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from ow_planner import (
    CandidateCommitmentOptions,
    CandidateGenerationConfig,
    CommitmentPolicyConfig,
    EvaluationConfig,
    MissionCandidate,
    MissionEvaluation,
    MissionResponseEvaluation,
    MissionScoringConfig,
    PlannerDecisionBundle,
    ResponseConfig,
    StrategyModeFacts,
    StrategySelectionResult,
    commitment_options_for_candidates,
    evaluate_and_score_candidates,
    evaluate_responses,
    generate_candidates,
    no_action_strategy_result,
    planner_decision_bundles,
    selected_strategy_result,
    strategy_mode_facts,
)
from ow_sim.state import GameState

from .action_sets import build_action_set_report
from .diagnosis import diagnose_board
from .fallback import fallback_rank_records, select_evaluated_plan
from .mission_generation import generate_mission_plans
from .mission_surfaces import generate_surface_candidates
from .scenario_eval import evaluate_action_set_scenarios
from .scoring import score_action_set_plans
from .trajectory import diagnose_trajectory
from .types import PlannerV2Config, PlannerV2FunnelDiagnostics, PlannerV2Result


def run_planner_v2(
    state: GameState,
    config: PlannerV2Config | None = None,
) -> PlannerV2Result:
    """Run Planner V2 using the current planner primitives as its substrate."""

    candidates = generate_candidates(state, CandidateGenerationConfig())
    effective_config = PlannerV2Config() if config is None else config
    diagnosis = diagnose_board(state)
    candidates = candidates + generate_surface_candidates(
        state,
        candidates,
        effective_config,
        diagnosis,
    )
    evaluations = evaluate_and_score_candidates(
        state,
        candidates,
        evaluation_config=EvaluationConfig(),
        scoring_config=MissionScoringConfig(),
    )
    response_evaluations = evaluate_responses(state, evaluations, ResponseConfig())
    commitment_options = commitment_options_for_candidates(
        state,
        candidates,
        CommitmentPolicyConfig(),
    )
    mode_facts = strategy_mode_facts(state)
    bundles = planner_decision_bundles(
        candidates,
        strategy_mode_facts=mode_facts,
        evaluations=evaluations,
        response_evaluations=response_evaluations,
        commitment_options=commitment_options,
    )
    return run_planner_v2_from_artifacts(
        state,
        candidates=candidates,
        evaluations=evaluations,
        response_evaluations=response_evaluations,
        commitment_options=commitment_options,
        bundles=bundles,
        config=effective_config,
        diagnosis=diagnosis,
    )


def run_planner_v2_from_artifacts(
    state: GameState,
    *,
    candidates: Sequence[MissionCandidate],
    evaluations: Sequence[MissionEvaluation],
    response_evaluations: Sequence[MissionResponseEvaluation],
    commitment_options: Sequence[CandidateCommitmentOptions],
    bundles: Sequence[PlannerDecisionBundle],
    config: PlannerV2Config | None = None,
    diagnosis=None,
) -> PlannerV2Result:
    """Run V2 diagnosis, mission, action-set, scoring, and fallback stages."""

    _ = response_evaluations, bundles
    effective_config = PlannerV2Config() if config is None else config
    diagnosis = diagnose_board(state) if diagnosis is None else diagnosis
    trajectory_diagnosis = diagnose_trajectory(state)
    missions = generate_mission_plans(
        diagnosis,
        candidates,
        evaluations,
        effective_config,
    )
    action_set_report = build_action_set_report(
        missions,
        commitment_options,
        effective_config,
    )
    action_sets = action_set_report.kept_action_sets
    scenario_evaluations = evaluate_action_set_scenarios(
        state,
        action_sets,
        diagnosis,
        effective_config,
    )
    evaluated_plans = score_action_set_plans(
        action_sets,
        diagnosis,
        effective_config,
        scenario_evaluations=scenario_evaluations,
        trajectory_diagnosis=trajectory_diagnosis,
    )
    selected_plan, no_action_reason, notes = select_evaluated_plan(
        evaluated_plans,
        diagnosis,
        effective_config,
    )
    funnel_diagnostics = PlannerV2FunnelDiagnostics(
        action_set_report=action_set_report,
        fallback_ranks=fallback_rank_records(
            evaluated_plans,
            diagnosis,
            selected_plan,
        ),
    )
    return PlannerV2Result(
        actions=(
            ()
            if selected_plan is None
            else selected_plan.plan.launches
        ),
        diagnosis=diagnosis,
        missions=missions,
        action_sets=action_sets,
        evaluated_plans=evaluated_plans,
        selected_plan=selected_plan,
        no_action_reason=no_action_reason,
        notes=notes,
        funnel_diagnostics=funnel_diagnostics,
        trajectory_diagnosis=trajectory_diagnosis,
    )


def planner_v2_result_to_strategy_selection(
    result: PlannerV2Result,
    *,
    strategy_mode_facts: StrategyModeFacts | None,
    bundles: Sequence[PlannerDecisionBundle],
) -> StrategySelectionResult:
    """Map a V2 selected action set back to the existing selection contract."""

    if result.selected_plan is None:
        return no_action_strategy_result(
            strategy_mode_facts,
            notes=("planner_v2", result.no_action_reason or "no action"),
        )
    option = result.selected_plan.plan.commitment_option
    if option is None:
        return no_action_strategy_result(
            strategy_mode_facts,
            notes=("planner_v2", "selected plan missing commitment option"),
        )
    if tuple(option.launches) != tuple(result.selected_plan.plan.launches):
        option = replace(
            option,
            launches=result.selected_plan.plan.launches,
            source_planet_ids=tuple(
                dict.fromkeys(
                    launch.source_planet_id
                    for launch in result.selected_plan.plan.launches
                )
            ),
            ships_committed=sum(
                launch.ships for launch in result.selected_plan.plan.launches
            ),
        )
    candidate = option.candidate
    for bundle in bundles:
        if candidate is not None and bundle.candidate is candidate:
            return selected_strategy_result(
                bundle,
                option,
                notes=("planner_v2", *result.selected_plan.labels),
            )
    return no_action_strategy_result(
        strategy_mode_facts,
        notes=("planner_v2", "selected candidate missing bundle"),
    )


__all__ = (
    "planner_v2_result_to_strategy_selection",
    "run_planner_v2",
    "run_planner_v2_from_artifacts",
)
