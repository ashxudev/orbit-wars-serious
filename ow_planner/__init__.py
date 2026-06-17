"""Planner-layer package for Orbit Wars mission generation.

Mission Generation Cycle 0 defines typed candidate containers and an explicit
empty generation boundary. Mission Generation Cycle 1 adds legal action
conversion helpers. Mission Generation Cycle 2 adds board feature extraction.
Mission Generation Cycle 3 adds factual source-target pair enumeration.
Mission Generation Cycle 4 adds first-pass required ship estimation.
Mission Generation Cycle 5 adds simulator-backed factual outcome validation.
Mission Generation Cycle 6 adds the bounded public generation API.
Mission Evaluation Cycle 0 adds structural evaluation contracts.
Mission Evaluation Cycle 1 adds candidate-derived evaluation facts.
Mission Evaluation Cycle 2 adds before-state planet lookup facts.
Mission Evaluation Cycle 3 adds idle baseline future lookup facts.
Mission Evaluation Cycle 4 adds mechanical candidate future lookup facts.
Mission Evaluation Cycle 5 adds deterministic mission-vs-baseline deltas.
Mission Evaluation Cycle 6 adds deterministic mission value feature facts.
Mission Evaluation Cycle 7 adds an isolated first-pass scoring policy.
Mission Evaluation Cycle 8 adds evaluated-and-scored composition.
Mission Evaluation Cycle 9 adds deterministic arrival timing facts.
Mission Evaluation Cycle 10 adds timing-aware scoring components.
Mission Evaluation Cycle 11 adds capture-outcome scoring components.
Mission Evaluation Cycle 12 adds source-drain opportunity-cost scoring.
Opponent Response Model Cycle 0 adds structural response-evaluation contracts.
Opponent Response Model Cycle 1 adds reinforcement feasibility facts.
Opponent Response Model Cycle 2 adds target race-risk facts.
Opponent Response Model Cycle 3 adds source counterattack-risk facts.
Opponent Response Model Cycle 4 adds FFA third-party benefit facts.
Opponent Response Model Cycle 5 adds deterministic response summary labels.
Opponent Response Model Cycle 6 adds pinned/threatened response-source facts.
Opponent Response Model Cycle 7 adds first-pass response classification labels.
Commitment Policy Cycle 0 adds structural commitment option contracts.
Commitment Policy Cycle 1 adds explicit no-attack options.
Commitment Policy Cycle 2 adds minimum-capture options.
Commitment Policy Cycle 3 adds capture-and-hold options.
Commitment Policy Cycle 4 adds reserve-preserving options.
Commitment Policy Cycle 5 adds full-source options.
Commitment Policy Cycle 6 adds coordinated multi-source options.
Strategy Modes Cycle 0 adds deterministic 2p / 4p mode facts.
Strategy Modes Cycle 1 adds planner decision bundle composition.
Strategy Modes Cycle 2 adds structural strategy-selection results.
Strategy Modes Cycle 3 adds deterministic two-player direct-advantage facts.
Strategy Modes Cycle 4 adds first-pass two-player direct-advantage selection.
Strategy, ranking, pruning, and selection are intentionally deferred.
"""

from .actions import (
    launch_candidate_to_action,
    launch_candidate_to_order,
    mission_candidate_to_actions,
    mission_candidate_to_orders,
)
from .candidates import (
    CandidateGenerationConfig,
    CandidateOutcome,
    LaunchCandidate,
    MissionCandidate,
    MissionType,
    generate_candidates,
)
from .commitment import (
    CandidateCommitmentOptions,
    CommitmentOption,
    CommitmentOptionStatus,
    CommitmentOptionType,
    CommitmentPolicyConfig,
    capture_and_hold_commitment_option,
    coordinated_multi_source_commitment_option,
    commitment_options_for_candidates,
    full_source_commitment_option,
    minimum_capture_commitment_option,
    no_attack_commitment_option,
    reserve_preserving_commitment_option,
)
from .features import (
    BoardFeatures,
    NearestTarget,
    OwnerTotals,
    PlanetDistance,
    PlanetFacts,
    extract_board_features,
)
from .enumeration import (
    ROUGH_TRAVEL_SHIPS,
    SourceTargetPair,
    TargetCategory,
    enumerate_source_target_pairs,
    enumerate_source_target_pairs_from_features,
)
from .estimation import (
    DEFAULT_CAPTURE_BUFFER_SHIPS,
    EstimatedPair,
    ShipEstimate,
    ShipEstimateStatus,
    estimate_required_ships_for_pair,
    estimate_source_target_pairs,
    launch_candidate_from_pair,
)
from .outcomes import (
    CandidateOutcomeReport,
    CandidateValidationStatus,
    validate_estimated_pair_outcome,
    validate_estimated_pair_outcomes,
)
from .evaluation import (
    EvaluationConfig,
    MissionEvaluation,
    MissionEvaluationFacts,
    MissionEvaluationStatus,
    MissionFutureDeltaFacts,
    MissionTimingFacts,
    MissionValueFacts,
    PlanetEvaluationFacts,
    PlanetFutureDeltaFacts,
    ScoreComponent,
    baseline_state_after_horizon,
    candidate_state_after_horizon,
    evaluate_and_score_candidates,
    evaluate_candidates,
    extract_candidate_facts,
    mission_future_delta_facts,
    mission_timing_facts,
    mission_value_facts,
    planet_evaluation_facts,
    planet_future_delta_facts,
)
from .scoring import (
    MissionScoringConfig,
    score_evaluations,
    score_mission_outcome_facts,
    score_mission_timing_facts,
    score_mission_value_facts,
    score_source_opportunity_facts,
)
from .response import (
    CounterattackSourceFacts,
    MissionResponseEvaluation,
    MissionResponseFacts,
    RaceSourceFacts,
    ReinforcementSourceFacts,
    RespondingSourcePressureFacts,
    ResponseConfig,
    ResponseEvaluationStatus,
    ResponseSourcePressureFacts,
    ResponseSummaryFacts,
    SourceCounterattackFacts,
    TargetRaceFacts,
    TargetReinforcementFacts,
    ThirdPartyBenefitFacts,
    ThirdPartyOwnerFacts,
    evaluate_responses,
    response_source_pressure_facts,
    response_summary_facts,
    source_counterattack_facts,
    target_race_facts,
    target_reinforcement_facts,
    third_party_benefit_facts,
)
from .response_classification import (
    ResponseClassificationFacts,
    classify_response_facts,
)
from .strategy_modes import (
    StrategyMode,
    StrategyModeFacts,
    detect_strategy_mode,
    strategy_mode_facts,
)
from .strategy_decisions import (
    PlannerDecisionBundle,
    StrategySelectionResult,
    StrategySelectionStatus,
    no_action_strategy_result,
    planner_decision_bundles,
    rejected_strategy_result,
    selected_strategy_result,
)
from .two_player_strategy import (
    TwoPlayerAdvantageFacts,
    two_player_advantage_facts,
    two_player_advantage_facts_for_bundles,
)
from .two_player_selection import (
    TwoPlayerSelectionConfig,
    select_two_player_direct_advantage,
)

__all__ = (
    "BoardFeatures",
    "CandidateGenerationConfig",
    "CandidateCommitmentOptions",
    "CandidateOutcome",
    "CandidateOutcomeReport",
    "CandidateValidationStatus",
    "CommitmentOption",
    "CommitmentOptionStatus",
    "CommitmentOptionType",
    "CommitmentPolicyConfig",
    "CounterattackSourceFacts",
    "DEFAULT_CAPTURE_BUFFER_SHIPS",
    "EstimatedPair",
    "EvaluationConfig",
    "LaunchCandidate",
    "MissionCandidate",
    "MissionEvaluation",
    "MissionEvaluationFacts",
    "MissionEvaluationStatus",
    "MissionFutureDeltaFacts",
    "MissionResponseEvaluation",
    "MissionResponseFacts",
    "MissionTimingFacts",
    "MissionScoringConfig",
    "MissionValueFacts",
    "MissionType",
    "NearestTarget",
    "OwnerTotals",
    "PlanetDistance",
    "PlanetEvaluationFacts",
    "PlanetFutureDeltaFacts",
    "PlanetFacts",
    "PlannerDecisionBundle",
    "ROUGH_TRAVEL_SHIPS",
    "RaceSourceFacts",
    "ReinforcementSourceFacts",
    "RespondingSourcePressureFacts",
    "ResponseConfig",
    "ResponseClassificationFacts",
    "ResponseEvaluationStatus",
    "ResponseSourcePressureFacts",
    "ResponseSummaryFacts",
    "ScoreComponent",
    "ShipEstimate",
    "ShipEstimateStatus",
    "SourceCounterattackFacts",
    "SourceTargetPair",
    "StrategyMode",
    "StrategyModeFacts",
    "StrategySelectionResult",
    "StrategySelectionStatus",
    "TargetCategory",
    "TargetRaceFacts",
    "TargetReinforcementFacts",
    "ThirdPartyBenefitFacts",
    "ThirdPartyOwnerFacts",
    "TwoPlayerAdvantageFacts",
    "TwoPlayerSelectionConfig",
    "baseline_state_after_horizon",
    "candidate_state_after_horizon",
    "classify_response_facts",
    "capture_and_hold_commitment_option",
    "coordinated_multi_source_commitment_option",
    "commitment_options_for_candidates",
    "detect_strategy_mode",
    "extract_board_features",
    "enumerate_source_target_pairs",
    "enumerate_source_target_pairs_from_features",
    "estimate_required_ships_for_pair",
    "estimate_source_target_pairs",
    "evaluate_and_score_candidates",
    "evaluate_candidates",
    "evaluate_responses",
    "extract_candidate_facts",
    "full_source_commitment_option",
    "generate_candidates",
    "launch_candidate_to_action",
    "launch_candidate_to_order",
    "launch_candidate_from_pair",
    "mission_candidate_to_actions",
    "mission_candidate_to_orders",
    "mission_future_delta_facts",
    "mission_timing_facts",
    "mission_value_facts",
    "minimum_capture_commitment_option",
    "no_action_strategy_result",
    "no_attack_commitment_option",
    "planet_evaluation_facts",
    "planet_future_delta_facts",
    "planner_decision_bundles",
    "rejected_strategy_result",
    "score_evaluations",
    "score_mission_outcome_facts",
    "score_mission_timing_facts",
    "score_mission_value_facts",
    "score_source_opportunity_facts",
    "selected_strategy_result",
    "select_two_player_direct_advantage",
    "reserve_preserving_commitment_option",
    "response_source_pressure_facts",
    "response_summary_facts",
    "source_counterattack_facts",
    "strategy_mode_facts",
    "target_race_facts",
    "target_reinforcement_facts",
    "third_party_benefit_facts",
    "two_player_advantage_facts",
    "two_player_advantage_facts_for_bundles",
    "validate_estimated_pair_outcome",
    "validate_estimated_pair_outcomes",
)
