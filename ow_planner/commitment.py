"""Structural commitment policy API boundary.

Commitment Policy Cycle 0 defines immutable containers for future ship-sizing
decisions. Cycle 1 adds an explicit no-attack option. Cycle 2 adds a
minimum-capture option that mirrors existing candidate launches. Cycle 3 adds a
first-pass capture-and-hold option with a deterministic buffer. Cycle 4 adds a
reserve-preserving option. It does not evaluate, score, rank, prune, select, or
convert commitment options.
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
    capture_hold_buffer_ships: int = 5
    reserve_ships_per_source: int = 1

    def __post_init__(self) -> None:
        if self.max_options_per_candidate is not None and _invalid_nonnegative_int(
            self.max_options_per_candidate
        ):
            raise ValueError(
                "max_options_per_candidate must be None or an integer >= 0"
            )
        if _invalid_nonnegative_int(self.capture_hold_buffer_ships):
            raise ValueError("capture_hold_buffer_ships must be an integer >= 0")
        if _invalid_nonnegative_int(self.reserve_ships_per_source):
            raise ValueError("reserve_ships_per_source must be an integer >= 0")


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

    Cycle 4 returns no-attack, minimum-capture, capture-and-hold, and
    reserve-preserving options when the option limit allows them.
    """

    effective_config = CommitmentPolicyConfig() if config is None else config
    return tuple(
        CandidateCommitmentOptions(
            candidate=candidate,
            options=_options_for_candidate(state, candidate, effective_config),
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


def capture_and_hold_commitment_option(
    state: GameState,
    candidate: MissionCandidate,
    config: CommitmentPolicyConfig | None = None,
) -> CommitmentOption:
    """Return a buffered capture-and-hold option when sources can afford it."""

    effective_config = CommitmentPolicyConfig() if config is None else config
    if not candidate.launches:
        return _rejected_capture_and_hold(candidate, "candidate has no launches")

    planets_by_id = {planet.planet_id: planet for planet in state.planets}
    baseline_by_source: dict[int, int] = {}
    for launch in candidate.launches:
        planet = planets_by_id.get(launch.source_planet_id)
        if planet is None:
            return _rejected_capture_and_hold(candidate, "missing source planet")
        player_id = launch.player_id if launch.player_id is not None else state.player_id
        if player_id is None:
            return _rejected_capture_and_hold(candidate, "missing player id")
        if planet.owner != player_id:
            return _rejected_capture_and_hold(
                candidate,
                "source planet not owned by player",
            )
        baseline_by_source[launch.source_planet_id] = (
            baseline_by_source.get(launch.source_planet_id, 0) + launch.ships
        )

    remaining_by_source = {
        source_id: planets_by_id[source_id].ships - committed
        for source_id, committed in baseline_by_source.items()
    }
    if any(remaining < 0 for remaining in remaining_by_source.values()):
        return _rejected_capture_and_hold(
            candidate,
            "insufficient source ships for hold buffer",
        )

    buffer_remaining = effective_config.capture_hold_buffer_ships
    if buffer_remaining == 0:
        return CommitmentOption(
            option_type=CommitmentOptionType.CAPTURE_AND_HOLD,
            candidate=candidate,
            launches=candidate.launches,
            source_planet_ids=tuple(
                launch.source_planet_id for launch in candidate.launches
            ),
            ships_committed=sum(launch.ships for launch in candidate.launches),
            status=CommitmentOptionStatus.VALIDATED,
            note="capture and hold",
        )

    adjusted_launches = []
    for launch in candidate.launches:
        source_id = launch.source_planet_id
        extra = min(buffer_remaining, remaining_by_source[source_id])
        buffer_remaining -= extra
        remaining_by_source[source_id] -= extra
        adjusted_launches.append(
            LaunchCandidate(
                source_planet_id=launch.source_planet_id,
                angle=launch.angle,
                ships=launch.ships + extra,
                player_id=launch.player_id,
            )
        )
        if buffer_remaining == 0:
            adjusted_launches.extend(candidate.launches[len(adjusted_launches) :])
            break

    if buffer_remaining != 0:
        return _rejected_capture_and_hold(
            candidate,
            "insufficient source ships for hold buffer",
        )

    launches = tuple(adjusted_launches)
    return CommitmentOption(
        option_type=CommitmentOptionType.CAPTURE_AND_HOLD,
        candidate=candidate,
        launches=launches,
        source_planet_ids=tuple(launch.source_planet_id for launch in launches),
        ships_committed=sum(launch.ships for launch in launches),
        status=CommitmentOptionStatus.VALIDATED,
        note="capture and hold",
    )


def reserve_preserving_commitment_option(
    state: GameState,
    candidate: MissionCandidate,
    config: CommitmentPolicyConfig | None = None,
) -> CommitmentOption:
    """Return an option that preserves a per-source ship reserve."""

    effective_config = CommitmentPolicyConfig() if config is None else config
    if not candidate.launches:
        return _rejected_reserve_preserving(candidate, "candidate has no launches")

    planets_by_id = {planet.planet_id: planet for planet in state.planets}
    committed_by_source: dict[int, int] = {}
    for launch in candidate.launches:
        planet = planets_by_id.get(launch.source_planet_id)
        if planet is None:
            return _rejected_reserve_preserving(candidate, "missing source planet")
        player_id = launch.player_id if launch.player_id is not None else state.player_id
        if player_id is None:
            return _rejected_reserve_preserving(candidate, "missing player id")
        if planet.owner != player_id:
            return _rejected_reserve_preserving(
                candidate,
                "source planet not owned by player",
            )
        committed_by_source[launch.source_planet_id] = (
            committed_by_source.get(launch.source_planet_id, 0) + launch.ships
        )

    reserve = effective_config.reserve_ships_per_source
    for source_id, committed in committed_by_source.items():
        if planets_by_id[source_id].ships - committed < reserve:
            return _rejected_reserve_preserving(
                candidate,
                "insufficient source ships for reserve",
            )

    return CommitmentOption(
        option_type=CommitmentOptionType.RESERVE_PRESERVING,
        candidate=candidate,
        launches=candidate.launches,
        source_planet_ids=tuple(launch.source_planet_id for launch in candidate.launches),
        ships_committed=sum(launch.ships for launch in candidate.launches),
        status=CommitmentOptionStatus.VALIDATED,
        note="reserve preserving",
    )


def _options_for_candidate(
    state: GameState,
    candidate: MissionCandidate,
    config: CommitmentPolicyConfig,
) -> tuple[CommitmentOption, ...]:
    if config.max_options_per_candidate == 0:
        return ()

    options = [no_attack_commitment_option(candidate)]
    if config.max_options_per_candidate == 1:
        return tuple(options)

    options.append(minimum_capture_commitment_option(candidate))
    if config.max_options_per_candidate == 2:
        return tuple(options)

    options.append(capture_and_hold_commitment_option(state, candidate, config))
    if config.max_options_per_candidate == 3:
        return tuple(options)

    options.append(reserve_preserving_commitment_option(state, candidate, config))
    return tuple(options)


def _rejected_capture_and_hold(
    candidate: MissionCandidate,
    note: str,
) -> CommitmentOption:
    return CommitmentOption(
        option_type=CommitmentOptionType.CAPTURE_AND_HOLD,
        candidate=candidate,
        status=CommitmentOptionStatus.REJECTED,
        note=note,
    )


def _rejected_reserve_preserving(
    candidate: MissionCandidate,
    note: str,
) -> CommitmentOption:
    return CommitmentOption(
        option_type=CommitmentOptionType.RESERVE_PRESERVING,
        candidate=candidate,
        status=CommitmentOptionStatus.REJECTED,
        note=note,
    )


def _invalid_nonnegative_int(value: object) -> bool:
    return isinstance(value, bool) or not isinstance(value, int) or value < 0


__all__ = (
    "CandidateCommitmentOptions",
    "CommitmentOption",
    "CommitmentOptionStatus",
    "CommitmentOptionType",
    "CommitmentPolicyConfig",
    "capture_and_hold_commitment_option",
    "commitment_options_for_candidates",
    "minimum_capture_commitment_option",
    "no_attack_commitment_option",
    "reserve_preserving_commitment_option",
)
