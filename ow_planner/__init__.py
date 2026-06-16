"""Planner-layer package for Orbit Wars mission generation.

Mission Generation Cycle 0 defines typed candidate containers and an explicit
empty generation boundary. Mission Generation Cycle 1 adds legal action
conversion helpers. Mission Generation Cycle 2 adds board feature extraction.
Mission Generation Cycle 3 adds factual source-target pair enumeration.
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

__all__ = (
    "BoardFeatures",
    "CandidateGenerationConfig",
    "CandidateOutcome",
    "LaunchCandidate",
    "MissionCandidate",
    "MissionType",
    "NearestTarget",
    "OwnerTotals",
    "PlanetDistance",
    "PlanetFacts",
    "ROUGH_TRAVEL_SHIPS",
    "SourceTargetPair",
    "TargetCategory",
    "extract_board_features",
    "enumerate_source_target_pairs",
    "enumerate_source_target_pairs_from_features",
    "generate_candidates",
    "launch_candidate_to_action",
    "launch_candidate_to_order",
    "mission_candidate_to_actions",
    "mission_candidate_to_orders",
)
