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
    mission_value_facts,
    planet_evaluation_facts,
    planet_future_delta_facts,
)
from .scoring import (
    MissionScoringConfig,
    score_evaluations,
    score_mission_value_facts,
)

__all__ = (
    "BoardFeatures",
    "CandidateGenerationConfig",
    "CandidateOutcome",
    "CandidateOutcomeReport",
    "CandidateValidationStatus",
    "DEFAULT_CAPTURE_BUFFER_SHIPS",
    "EstimatedPair",
    "EvaluationConfig",
    "LaunchCandidate",
    "MissionCandidate",
    "MissionEvaluation",
    "MissionEvaluationFacts",
    "MissionEvaluationStatus",
    "MissionFutureDeltaFacts",
    "MissionScoringConfig",
    "MissionValueFacts",
    "MissionType",
    "NearestTarget",
    "OwnerTotals",
    "PlanetDistance",
    "PlanetEvaluationFacts",
    "PlanetFutureDeltaFacts",
    "PlanetFacts",
    "ROUGH_TRAVEL_SHIPS",
    "ScoreComponent",
    "ShipEstimate",
    "ShipEstimateStatus",
    "SourceTargetPair",
    "TargetCategory",
    "baseline_state_after_horizon",
    "candidate_state_after_horizon",
    "extract_board_features",
    "enumerate_source_target_pairs",
    "enumerate_source_target_pairs_from_features",
    "estimate_required_ships_for_pair",
    "estimate_source_target_pairs",
    "evaluate_and_score_candidates",
    "evaluate_candidates",
    "extract_candidate_facts",
    "generate_candidates",
    "launch_candidate_to_action",
    "launch_candidate_to_order",
    "launch_candidate_from_pair",
    "mission_candidate_to_actions",
    "mission_candidate_to_orders",
    "mission_future_delta_facts",
    "mission_value_facts",
    "planet_evaluation_facts",
    "planet_future_delta_facts",
    "score_evaluations",
    "score_mission_value_facts",
    "validate_estimated_pair_outcome",
    "validate_estimated_pair_outcomes",
)
