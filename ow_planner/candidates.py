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
    max_validation_attempts: int | None = None

    def __post_init__(self) -> None:
        _validate_optional_nonnegative_int(self.max_candidates, "max_candidates")
        _validate_optional_nonnegative_int(
            self.max_validation_attempts,
            "max_validation_attempts",
        )


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
    outcome validation. Candidate limiting is applied to validated candidates,
    while validation-attempt limiting bounds expensive simulator work.
    Unaffordable estimates are skipped before validation so early poor pairs do
    not starve later affordable opportunities.
    """

    effective_config = config or CandidateGenerationConfig()
    from .enumeration import enumerate_source_target_pairs
    from .estimation import ShipEstimateStatus, estimate_source_target_pairs
    from .outcomes import CandidateValidationStatus, validate_estimated_pair_outcomes

    if (
        effective_config.max_candidates == 0
        or effective_config.max_validation_attempts == 0
    ):
        return ()

    pairs = enumerate_source_target_pairs(state, config=effective_config)
    estimated_pairs = estimate_source_target_pairs(pairs, config=effective_config)
    candidates: list[MissionCandidate] = []
    validation_attempts = 0

    for estimated_pair in estimated_pairs:
        if (
            estimated_pair.estimate.status is not ShipEstimateStatus.AFFORDABLE
            or estimated_pair.launch is None
        ):
            continue
        if (
            effective_config.max_validation_attempts is not None
            and validation_attempts >= effective_config.max_validation_attempts
        ):
            break

        validation_attempts += 1
        reports = validate_estimated_pair_outcomes(state, (estimated_pair,))
        for report in reports:
            if (
                report.status is CandidateValidationStatus.VALIDATED
                and report.captured_target
                and report.launch is not None
            ):
                candidates.append(_mission_candidate_from_report(report))
                if (
                    effective_config.max_candidates is not None
                    and len(candidates) >= effective_config.max_candidates
                ):
                    return tuple(candidates)
    if candidates:
        return tuple(candidates)

    recovery_candidates = _early_two_player_pressure_candidates(
        state,
        estimated_pairs,
        effective_config,
        validation_attempts,
    )
    if recovery_candidates:
        return recovery_candidates

    return _reduced_owner_pressure_candidates(
        state,
        estimated_pairs,
        effective_config,
        validation_attempts,
    )


def _early_two_player_pressure_candidates(
    state: GameState,
    estimated_pairs: tuple[Any, ...],
    config: CandidateGenerationConfig,
    validation_attempts: int,
) -> tuple[MissionCandidate, ...]:
    from .estimation import (
        ShipEstimate,
        ShipEstimateStatus,
        EstimatedPair,
        DEFAULT_CAPTURE_BUFFER_SHIPS,
    )
    from .outcomes import CandidateValidationStatus, validate_estimated_pair_outcomes
    from ow_sim.forecast import angle_to_point

    if not _is_low_owned_two_player_pressure_state(state):
        return ()

    candidates: list[MissionCandidate] = []
    for estimated_pair in estimated_pairs:
        if (
            config.max_validation_attempts is not None
            and validation_attempts >= config.max_validation_attempts
        ):
            break
        if config.max_candidates is not None and len(candidates) >= config.max_candidates:
            break
        if not _is_pressure_recovery_pair(estimated_pair):
            continue

        pair = estimated_pair.pair
        ships = pair.source_affordable_ships - 1
        launch = LaunchCandidate(
            source_planet_id=pair.source_planet_id,
            angle=angle_to_point(pair.source_position, pair.target_position),
            ships=ships,
        )
        recovery_pair = EstimatedPair(
            pair=pair,
            estimate=ShipEstimate(
                target_category=pair.target_category,
                required_ships=ships,
                source_available_ships=pair.source_affordable_ships,
                target_projected_ships=pair.target_ships,
                production_added=0,
                buffer_ships=DEFAULT_CAPTURE_BUFFER_SHIPS,
                status=ShipEstimateStatus.AFFORDABLE,
            ),
            launch=launch,
        )
        validation_attempts += 1
        reports = validate_estimated_pair_outcomes(state, (recovery_pair,))
        for report in reports:
            if report.status is CandidateValidationStatus.VALIDATED:
                candidates.append(
                    _mission_candidate_from_report(
                        report,
                        note="early two-player pressure recovery",
                    )
                )
                if (
                    config.max_candidates is not None
                    and len(candidates) >= config.max_candidates
                ):
                    return tuple(candidates)
    return tuple(candidates)


def _is_low_owned_two_player_pressure_state(state: GameState) -> bool:
    if state.step is None or state.step > 10:
        return False
    active_owners = {
        planet.owner
        for planet in state.planets
        if planet.owner is not None and planet.owner >= 0
    }
    owned_planets = tuple(
        planet for planet in state.planets if planet.owner == state.player_id
    )
    return len(active_owners) <= 2 and len(owned_planets) <= 1


def _reduced_owner_pressure_candidates(
    state: GameState,
    estimated_pairs: tuple[Any, ...],
    config: CandidateGenerationConfig,
    validation_attempts: int,
) -> tuple[MissionCandidate, ...]:
    from .estimation import (
        ShipEstimate,
        ShipEstimateStatus,
        EstimatedPair,
        DEFAULT_CAPTURE_BUFFER_SHIPS,
    )
    from .outcomes import CandidateValidationStatus, validate_estimated_pair_outcomes
    from ow_sim.forecast import angle_to_point

    if not _is_reduced_owner_pressure_state(state):
        return ()

    candidates: list[MissionCandidate] = []
    for estimated_pair in estimated_pairs:
        if (
            config.max_validation_attempts is not None
            and validation_attempts >= config.max_validation_attempts
        ):
            break
        if config.max_candidates is not None and len(candidates) >= config.max_candidates:
            break
        if not _is_pressure_recovery_pair(estimated_pair):
            continue

        pair = estimated_pair.pair
        ships = pair.source_affordable_ships - 1
        launch = LaunchCandidate(
            source_planet_id=pair.source_planet_id,
            angle=angle_to_point(pair.source_position, pair.target_position),
            ships=ships,
        )
        recovery_pair = EstimatedPair(
            pair=pair,
            estimate=ShipEstimate(
                target_category=pair.target_category,
                required_ships=ships,
                source_available_ships=pair.source_affordable_ships,
                target_projected_ships=pair.target_ships,
                production_added=0,
                buffer_ships=DEFAULT_CAPTURE_BUFFER_SHIPS,
                status=ShipEstimateStatus.AFFORDABLE,
            ),
            launch=launch,
        )
        validation_attempts += 1
        reports = validate_estimated_pair_outcomes(state, (recovery_pair,))
        for report in reports:
            if report.status is CandidateValidationStatus.VALIDATED:
                candidates.append(
                    _mission_candidate_from_report(
                        report,
                        note="reduced-owner pressure recovery",
                    )
                )
                if (
                    config.max_candidates is not None
                    and len(candidates) >= config.max_candidates
                ):
                    return tuple(candidates)
    return tuple(candidates)


def _is_reduced_owner_pressure_state(state: GameState) -> bool:
    if state.step is None or state.step < 50:
        return False
    active_owners = {
        planet.owner
        for planet in state.planets
        if planet.owner is not None and planet.owner >= 0
    }
    owned_planets = tuple(
        planet for planet in state.planets if planet.owner == state.player_id
    )
    return len(active_owners) <= 2 and len(owned_planets) == 1


def _is_pressure_recovery_pair(estimated_pair: Any) -> bool:
    from .enumeration import TargetCategory
    from .estimation import ShipEstimateStatus

    pair = estimated_pair.pair
    return (
        estimated_pair.estimate.status is ShipEstimateStatus.INSUFFICIENT_SOURCE_SHIPS
        and pair.target_category in (TargetCategory.NEUTRAL, TargetCategory.ENEMY)
        and pair.target_production > 0
        and pair.source_affordable_ships > 1
        and estimated_pair.estimate.required_ships > pair.source_affordable_ships
    )


def _mission_candidate_from_report(
    report: Any,
    note: str | None = None,
) -> MissionCandidate:
    from .enumeration import TargetCategory

    pair = report.estimated_pair.pair
    if pair.target_category is TargetCategory.NEUTRAL:
        mission_type = MissionType.CAPTURE_NEUTRAL
    elif pair.target_category is TargetCategory.ENEMY:
        mission_type = MissionType.ATTACK_ENEMY
    else:
        mission_type = MissionType.REINFORCE
    return MissionCandidate(
        mission_type=mission_type,
        target_planet_id=pair.target_planet_id,
        source_planet_ids=(pair.source_planet_id,),
        launches=(report.launch,),
        outcome=CandidateOutcome.VALIDATED,
        note=note,
    )


def _validate_optional_nonnegative_int(value: object, name: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be None or an integer >= 0")


__all__ = (
    "CandidateGenerationConfig",
    "CandidateOutcome",
    "LaunchCandidate",
    "MissionCandidate",
    "MissionType",
    "generate_candidates",
)
