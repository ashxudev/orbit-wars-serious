"""Runtime planner pipeline composition boundary.

Runtime / Submission Cycle 2 composes already-existing planner stages from an
already-parsed ``GameState`` through strategy selection. It intentionally does
not parse observations, emit Kaggle actions, add fallback policy, or wire the
pipeline into the runtime ``agent`` entrypoint.
"""

from __future__ import annotations

from dataclasses import dataclass

from ow_planner import (
    CandidateCommitmentOptions,
    CandidateGenerationConfig,
    CommitmentPolicyConfig,
    EvaluationConfig,
    FourPlayerBoardFacts,
    FourPlayerSelectionConfig,
    MissionCandidate,
    MissionEvaluation,
    MissionResponseEvaluation,
    MissionScoringConfig,
    PlannerDecisionBundle,
    ResponseConfig,
    StrategyDispatchConfig,
    StrategyMode,
    StrategyModeFacts,
    StrategySelectionResult,
    TwoPlayerSelectionConfig,
    commitment_options_for_candidates,
    enemy_denial_opportunity_facts,
    evaluate_and_score_candidates,
    evaluate_responses,
    four_player_board_facts,
    four_player_plateau_facts,
    generate_candidates,
    own_transfer_intent_facts,
    planner_decision_bundles,
    owned_production_threat_facts,
    select_strategy_for_mode,
    strategy_mode_facts,
)
from ow_sim.state import GameState


@dataclass(frozen=True, slots=True)
class RuntimePlannerConfig:
    """Configuration pass-through for runtime planner composition."""

    candidate_config: CandidateGenerationConfig | None = None
    evaluation_config: EvaluationConfig | None = None
    scoring_config: MissionScoringConfig | None = None
    response_config: ResponseConfig | None = None
    commitment_config: CommitmentPolicyConfig | None = None
    strategy_dispatch_config: StrategyDispatchConfig | None = None


@dataclass(frozen=True, slots=True)
class RuntimePlannerResult:
    """Structured runtime planner pipeline artifacts and final selection."""

    state: GameState
    candidates: tuple[MissionCandidate, ...]
    evaluations: tuple[MissionEvaluation, ...]
    response_evaluations: tuple[MissionResponseEvaluation, ...]
    commitment_options: tuple[CandidateCommitmentOptions, ...]
    strategy_mode_facts: StrategyModeFacts
    four_player_board_facts: FourPlayerBoardFacts | None
    bundles: tuple[PlannerDecisionBundle, ...]
    selection: StrategySelectionResult


def run_planner_pipeline(
    state: GameState,
    config: RuntimePlannerConfig | None = None,
) -> RuntimePlannerResult:
    """Run the existing planner stack for an already-parsed game state."""

    effective_config = RuntimePlannerConfig() if config is None else config

    candidates = generate_candidates(state, effective_config.candidate_config)
    evaluations = evaluate_and_score_candidates(
        state,
        candidates,
        evaluation_config=effective_config.evaluation_config,
        scoring_config=effective_config.scoring_config,
    )
    response_evaluations = evaluate_responses(
        state,
        evaluations,
        effective_config.response_config,
    )
    commitment_options = commitment_options_for_candidates(
        state,
        candidates,
        effective_config.commitment_config,
    )
    mode_facts = strategy_mode_facts(state)
    board_facts = (
        four_player_board_facts(state, mode_facts)
        if mode_facts.mode is StrategyMode.FOUR_PLAYER
        else None
    )
    dispatch_config = _dispatch_config_with_runtime_facts(
        effective_config.strategy_dispatch_config,
        state,
        mode_facts,
    )
    bundles = planner_decision_bundles(
        candidates,
        strategy_mode_facts=mode_facts,
        evaluations=evaluations,
        response_evaluations=response_evaluations,
        commitment_options=commitment_options,
    )
    selection = select_strategy_for_mode(
        bundles,
        strategy_mode_facts=mode_facts,
        four_player_board_facts=board_facts,
        config=dispatch_config,
    )

    return RuntimePlannerResult(
        state=state,
        candidates=candidates,
        evaluations=evaluations,
        response_evaluations=response_evaluations,
        commitment_options=commitment_options,
        strategy_mode_facts=mode_facts,
        four_player_board_facts=board_facts,
        bundles=bundles,
        selection=selection,
    )


def _dispatch_config_with_runtime_facts(
    config: StrategyDispatchConfig | None,
    state: GameState,
    mode_facts: StrategyModeFacts,
) -> StrategyDispatchConfig | None:
    base_config = StrategyDispatchConfig() if config is None else config
    if mode_facts.mode is StrategyMode.FOUR_PLAYER:
        four_player_config = (
            FourPlayerSelectionConfig()
            if base_config.four_player_config is None
            else base_config.four_player_config
        )
        if four_player_config.four_player_plateau_report is not None:
            plateau_report = four_player_config.four_player_plateau_report
        else:
            plateau_report = four_player_plateau_facts(state)
        return StrategyDispatchConfig(
            two_player_config=base_config.two_player_config,
            four_player_config=FourPlayerSelectionConfig(
                minimum_total_score=four_player_config.minimum_total_score,
                allow_source_counterattack_risk=(
                    four_player_config.allow_source_counterattack_risk
                ),
                allow_third_party_benefit=(
                    four_player_config.allow_third_party_benefit
                ),
                commitment_preference_order=(
                    four_player_config.commitment_preference_order
                ),
                four_player_plateau_report=plateau_report,
            ),
        )
    if mode_facts.mode is not StrategyMode.TWO_PLAYER:
        return config

    two_player_config = (
        TwoPlayerSelectionConfig()
        if base_config.two_player_config is None
        else base_config.two_player_config
    )
    if two_player_config.owned_production_threat_report is not None:
        threat_report = two_player_config.owned_production_threat_report
    else:
        threat_report = owned_production_threat_facts(state)

    if two_player_config.own_transfer_intent_report is not None:
        transfer_report = two_player_config.own_transfer_intent_report
    else:
        transfer_report = own_transfer_intent_facts(
            state,
            threat_report=threat_report,
        )
    if two_player_config.enemy_denial_opportunity_report is not None:
        denial_report = two_player_config.enemy_denial_opportunity_report
    else:
        denial_report = enemy_denial_opportunity_facts(state)
    return StrategyDispatchConfig(
        two_player_config=TwoPlayerSelectionConfig(
            minimum_total_score=two_player_config.minimum_total_score,
            allow_source_counterattack_risk=(
                two_player_config.allow_source_counterattack_risk
            ),
            commitment_preference_order=two_player_config.commitment_preference_order,
            owned_production_threat_report=threat_report,
            own_transfer_intent_report=transfer_report,
            enemy_denial_opportunity_report=denial_report,
        ),
        four_player_config=base_config.four_player_config,
    )


__all__ = (
    "RuntimePlannerConfig",
    "RuntimePlannerResult",
    "run_planner_pipeline",
)
