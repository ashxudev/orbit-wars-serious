"""Planner-layer package for Orbit Wars mission generation.

Mission Generation Cycle 0 defines typed candidate containers and an explicit
empty generation boundary. Strategy, scoring, and action conversion are
intentionally deferred.
"""

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
)
