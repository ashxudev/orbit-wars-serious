"""Typed planner candidate containers.

This module is an infrastructure boundary only. It defines stable value types
for future mission generation and a deterministic placeholder generator that
returns no strategic candidates yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

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
    """Configuration placeholder for future candidate generation."""

    max_candidates: int | None = None


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
    """Return deterministic placeholder candidates for ``state``.

    Mission generation is intentionally not implemented in this cycle. The
    parameters establish the public planner boundary and are kept side-effect
    free for future extension.
    """

    _ = state
    _ = config
    return ()


__all__ = (
    "CandidateGenerationConfig",
    "CandidateOutcome",
    "LaunchCandidate",
    "MissionCandidate",
    "MissionType",
    "generate_candidates",
)
