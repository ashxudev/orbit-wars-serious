"""Planner-layer package for Orbit Wars mission generation.

Mission Generation Cycle 0 defines typed candidate containers and an explicit
empty generation boundary. Mission Generation Cycle 1 adds legal action
conversion helpers. Mission Generation Cycle 2 adds board feature extraction.
Mission Generation Cycle 3 adds factual source-target pair enumeration.
Mission Generation Cycle 4 adds first-pass required ship estimation.
Strategy and scoring are intentionally deferred.
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

__all__ = (
    "BoardFeatures",
    "CandidateGenerationConfig",
    "CandidateOutcome",
    "DEFAULT_CAPTURE_BUFFER_SHIPS",
    "EstimatedPair",
    "LaunchCandidate",
    "MissionCandidate",
    "MissionType",
    "NearestTarget",
    "OwnerTotals",
    "PlanetDistance",
    "PlanetFacts",
    "ROUGH_TRAVEL_SHIPS",
    "ShipEstimate",
    "ShipEstimateStatus",
    "SourceTargetPair",
    "TargetCategory",
    "extract_board_features",
    "enumerate_source_target_pairs",
    "enumerate_source_target_pairs_from_features",
    "estimate_required_ships_for_pair",
    "estimate_source_target_pairs",
    "generate_candidates",
    "launch_candidate_to_action",
    "launch_candidate_to_order",
    "launch_candidate_from_pair",
    "mission_candidate_to_actions",
    "mission_candidate_to_orders",
)
