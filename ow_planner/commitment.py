"""Structural commitment policy API boundary.

Commitment Policy Cycle 0 defines immutable containers for future ship-sizing
decisions. Cycle 1 adds an explicit no-attack option. Cycle 2 adds a
minimum-capture option that mirrors existing candidate launches. It does not
recompute attack sizes, evaluate, score, rank, prune, select, or convert
commitment options.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from ow_sim.state import GameState

from .candidates import LaunchCandidate, MissionCandidate


class CommitmentOptionType(str, Enum):
    """Planned commitment option families for future sizing cycles."""

    NO_ATTACK = "no_attack"
    MINIMUM_CAPTURE = "minimum_capture"
    CAPTURE_AND_HOLD = "capture_and_hold"
    RESERVE_PRESERVING = "reserve_preserving"
    FULL_SOURCE = "full_source"
    COORDINATED_MULTI_SOURCE = "coordinated_multi_source"


class CommitmentOptionStatus(str, Enum):
    """Lifecycle status for a commitment option."""

    UNTESTED = "untested"
    VALIDATED = "validated"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class CommitmentPolicyConfig:
    """Configuration boundary for commitment option generation."""

    max_options_per_candidate: int | None = None

    def __post_init__(self) -> None:
        if self.max_options_per_candidate is None:
            return
        if (
            isinstance(self.max_options_per_candidate, bool)
            or not isinstance(self.max_options_per_candidate, int)
            or self.max_options_per_candidate < 0
        ):
            raise ValueError(
                "max_options_per_candidate must be None or an integer >= 0"
            )


@dataclass(frozen=True, slots=True)
class CommitmentOption:
    """One future commitment sizing option for a mission candidate."""

    option_type: CommitmentOptionType
    candidate: MissionCandidate | None = None
    launches: tuple[LaunchCandidate, ...] = ()
    source_planet_ids: tuple[int, ...] = ()
    ships_committed: int = 0
    status: CommitmentOptionStatus = CommitmentOptionStatus.UNTESTED
    note: str | None = None


@dataclass(frozen=True, slots=True)
class CandidateCommitmentOptions:
    """Commitment option wrapper for one mission candidate."""

    candidate: MissionCandidate
    options: tuple[CommitmentOption, ...] = ()
    notes: tuple[str, ...] = ()


def commitment_options_for_candidates(
    state: GameState,
    candidates: Sequence[MissionCandidate],
    config: CommitmentPolicyConfig | None = None,
) -> tuple[CandidateCommitmentOptions, ...]:
    """Return structural commitment option wrappers in candidate order.

    Cycle 2 returns no-attack first and minimum-capture second when the option
    limit allows them. ``state`` is accepted to preserve the future API
    boundary.
    """

    effective_config = CommitmentPolicyConfig() if config is None else config
    return tuple(
        CandidateCommitmentOptions(
            candidate=candidate,
            options=_options_for_candidate(candidate, effective_config),
        )
        for candidate in candidates
    )


def no_attack_commitment_option(
    candidate: MissionCandidate | None = None,
) -> CommitmentOption:
    """Return a validated explicit no-attack commitment option."""

    return CommitmentOption(
        option_type=CommitmentOptionType.NO_ATTACK,
        candidate=candidate,
        status=CommitmentOptionStatus.VALIDATED,
        note="no attack",
    )


def minimum_capture_commitment_option(candidate: MissionCandidate) -> CommitmentOption:
    """Return a minimum-capture option based on a candidate's current launches."""

    if not candidate.launches:
        return CommitmentOption(
            option_type=CommitmentOptionType.MINIMUM_CAPTURE,
            candidate=candidate,
            status=CommitmentOptionStatus.REJECTED,
            note="candidate has no launches",
        )

    return CommitmentOption(
        option_type=CommitmentOptionType.MINIMUM_CAPTURE,
        candidate=candidate,
        launches=candidate.launches,
        source_planet_ids=tuple(launch.source_planet_id for launch in candidate.launches),
        ships_committed=sum(launch.ships for launch in candidate.launches),
        status=CommitmentOptionStatus.VALIDATED,
        note="minimum capture",
    )


def _options_for_candidate(
    candidate: MissionCandidate,
    config: CommitmentPolicyConfig,
) -> tuple[CommitmentOption, ...]:
    options = (
        no_attack_commitment_option(candidate),
        minimum_capture_commitment_option(candidate),
    )
    if config.max_options_per_candidate is None:
        return options
    return options[: config.max_options_per_candidate]


__all__ = (
    "CandidateCommitmentOptions",
    "CommitmentOption",
    "CommitmentOptionStatus",
    "CommitmentOptionType",
    "CommitmentPolicyConfig",
    "commitment_options_for_candidates",
    "minimum_capture_commitment_option",
    "no_attack_commitment_option",
)
