"""Planner-layer package for Orbit Wars mission generation.

Mission Generation Cycle 0 defines typed candidate containers and an explicit
empty generation boundary. Mission Generation Cycle 1 adds legal action
conversion helpers. Strategy and scoring are intentionally deferred.
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

__all__ = (
    "CandidateGenerationConfig",
    "CandidateOutcome",
    "LaunchCandidate",
    "MissionCandidate",
    "MissionType",
    "generate_candidates",
    "launch_candidate_to_action",
    "launch_candidate_to_order",
    "mission_candidate_to_actions",
    "mission_candidate_to_orders",
)
