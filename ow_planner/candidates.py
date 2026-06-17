"""Typed planner candidate containers and generation boundary.

Mission Generation Cycle 6 composes factual planner primitives into validated
mission candidates. It does not score, rank, compare, select, or execute
actions.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from ow_sim.state import GameState


class MissionType(str, Enum):
    """High-level mission categories for future planner candidates."""

    CAPTURE_NEUTRAL = "capture_neutral"
    ATTACK_ENEMY = "attack_enemy"
    DEFEND_OWN = "defend_own"
    REINFORCE = "reinforce"
    EVACUATE = "evacuate"


class CandidateOutcome(str, Enum):
    """Evaluation status for a candidate mission."""

    UNTESTED = "untested"
    VALIDATED = "validated"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class CandidateGenerationConfig:
    """Deterministic controls for candidate generation."""

    max_candidates: int | None = None

    def __post_init__(self) -> None:
        if self.max_candidates is None:
            return
        if (
            isinstance(self.max_candidates, bool)
            or not isinstance(self.max_candidates, int)
            or self.max_candidates < 0
        ):
            raise ValueError("max_candidates must be None or an integer >= 0")


@dataclass(frozen=True, slots=True)
class LaunchCandidate:
    """Typed launch component proposed by a mission candidate."""

    source_planet_id: int
    angle: float
    ships: int
    player_id: int | None = None


@dataclass(frozen=True, slots=True)
class MissionCandidate:
    """Typed mission candidate container for future planner work."""

    mission_type: MissionType
    target_planet_id: int | None = None
    source_planet_ids: tuple[int, ...] = ()
    launches: tuple[LaunchCandidate, ...] = ()
    outcome: CandidateOutcome = CandidateOutcome.UNTESTED
    note: str | None = None


def generate_candidates(
    state: GameState,
    config: CandidateGenerationConfig | None = None,
) -> tuple[MissionCandidate, ...]:
    """Return deterministic validated mission candidates for ``state``.

    This composes source-target enumeration, ship estimation, and simulator
    outcome validation. Candidate limiting is applied after validation in the
    deterministic order produced by the lower-level pipeline.
    """

    effective_config = config or CandidateGenerationConfig()
    from .enumeration import enumerate_source_target_pairs
    from .estimation import estimate_source_target_pairs
    from .outcomes import CandidateValidationStatus, validate_estimated_pair_outcomes

    pairs = enumerate_source_target_pairs(state, config=effective_config)
    estimated_pairs = estimate_source_target_pairs(pairs, config=effective_config)
    reports = validate_estimated_pair_outcomes(state, estimated_pairs)

    candidates = tuple(
        _mission_candidate_from_report(report)
        for report in reports
        if report.status is CandidateValidationStatus.VALIDATED
        and report.captured_target
        and report.launch is not None
    )
    if effective_config.max_candidates is None:
        return candidates
    return candidates[: effective_config.max_candidates]


def _mission_candidate_from_report(
    report: Any,
) -> MissionCandidate:
    from .enumeration import TargetCategory

    pair = report.estimated_pair.pair
    if pair.target_category is TargetCategory.NEUTRAL:
        mission_type = MissionType.CAPTURE_NEUTRAL
    else:
        mission_type = MissionType.ATTACK_ENEMY
    return MissionCandidate(
        mission_type=mission_type,
        target_planet_id=pair.target_planet_id,
        source_planet_ids=(pair.source_planet_id,),
        launches=(report.launch,),
        outcome=CandidateOutcome.VALIDATED,
    )


__all__ = (
    "CandidateGenerationConfig",
    "CandidateOutcome",
    "LaunchCandidate",
    "MissionCandidate",
    "MissionType",
    "generate_candidates",
)
