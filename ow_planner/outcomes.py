"""Planner candidate outcome validation.

Mission Generation Cycle 5 validates affordable estimated source-target pairs
by converting their launch candidates into simulator launch orders and rolling
out the existing simulator. It reports factual consequences only; it does not
score, rank, compare, select, or execute actions.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from ow_sim.state import GameState, Planet
from ow_sim.whatif import LaunchOrder, simulate_launch_orders

from .actions import launch_candidate_to_order
from .candidates import LaunchCandidate
from .estimation import EstimatedPair


class CandidateValidationStatus(str, Enum):
    """Status for simulator-backed candidate validation."""

    VALIDATED = "validated"
    NO_LAUNCH = "no_launch"
    SIMULATION_REJECTED = "simulation_rejected"
    TARGET_MISSING = "target_missing"
    SOURCE_MISSING = "source_missing"


@dataclass(frozen=True, slots=True)
class CandidateOutcomeReport:
    """Factual simulator outcome report for one estimated pair."""

    estimated_pair: EstimatedPair
    status: CandidateValidationStatus
    launch: LaunchCandidate | None
    launch_order: LaunchOrder | None
    rollout_ticks: int
    target_owner_after: int | None
    target_ships_after: int | None
    source_ships_after: int | None
    captured_target: bool
    source_planet_id: int
    target_planet_id: int
    error: str | None = None


def validate_estimated_pair_outcome(
    state: GameState,
    estimated_pair: EstimatedPair,
    player_id: int | None = None,
) -> CandidateOutcomeReport:
    """Validate one estimated pair through the simulator rollout boundary."""

    pair = estimated_pair.pair
    rollout_ticks = pair.rough_travel_ticks
    launch = estimated_pair.launch

    if launch is None:
        return _report(
            estimated_pair=estimated_pair,
            status=CandidateValidationStatus.NO_LAUNCH,
            launch=None,
            launch_order=None,
            rollout_ticks=rollout_ticks,
        )
    if rollout_ticks < 0:
        return _report(
            estimated_pair=estimated_pair,
            status=CandidateValidationStatus.SIMULATION_REJECTED,
            launch=launch,
            launch_order=None,
            rollout_ticks=rollout_ticks,
            error="rough_travel_ticks must be >= 0",
        )

    launch_order: LaunchOrder | None = None
    try:
        launch_order = launch_candidate_to_order(state, launch, player_id=player_id)
        rolled_state = simulate_launch_orders(
            state,
            [launch_order],
            ticks=rollout_ticks,
            player_id=player_id,
        )
    except ValueError as exc:
        return _report(
            estimated_pair=estimated_pair,
            status=CandidateValidationStatus.SIMULATION_REJECTED,
            launch=launch,
            launch_order=launch_order,
            rollout_ticks=rollout_ticks,
            error=str(exc),
        )

    effective_player_id = launch_order.player_id
    source = _planet_by_id(rolled_state, pair.source_planet_id)
    target = _planet_by_id(rolled_state, pair.target_planet_id)

    if source is None:
        return _report(
            estimated_pair=estimated_pair,
            status=CandidateValidationStatus.SOURCE_MISSING,
            launch=launch,
            launch_order=launch_order,
            rollout_ticks=rollout_ticks,
            target=target,
        )
    if target is None:
        return _report(
            estimated_pair=estimated_pair,
            status=CandidateValidationStatus.TARGET_MISSING,
            launch=launch,
            launch_order=launch_order,
            rollout_ticks=rollout_ticks,
            source=source,
        )

    return _report(
        estimated_pair=estimated_pair,
        status=CandidateValidationStatus.VALIDATED,
        launch=launch,
        launch_order=launch_order,
        rollout_ticks=rollout_ticks,
        source=source,
        target=target,
        captured_target=target.owner == effective_player_id,
    )


def validate_estimated_pair_outcomes(
    state: GameState,
    estimated_pairs: Sequence[EstimatedPair],
    player_id: int | None = None,
) -> tuple[CandidateOutcomeReport, ...]:
    """Validate estimated pairs in deterministic input order."""

    return tuple(
        validate_estimated_pair_outcome(state, estimated_pair, player_id=player_id)
        for estimated_pair in estimated_pairs
    )


def _report(
    *,
    estimated_pair: EstimatedPair,
    status: CandidateValidationStatus,
    launch: LaunchCandidate | None,
    launch_order: LaunchOrder | None,
    rollout_ticks: int,
    source: Planet | None = None,
    target: Planet | None = None,
    captured_target: bool = False,
    error: str | None = None,
) -> CandidateOutcomeReport:
    return CandidateOutcomeReport(
        estimated_pair=estimated_pair,
        status=status,
        launch=launch,
        launch_order=launch_order,
        rollout_ticks=rollout_ticks,
        target_owner_after=None if target is None else target.owner,
        target_ships_after=None if target is None else target.ships,
        source_ships_after=None if source is None else source.ships,
        captured_target=captured_target,
        source_planet_id=estimated_pair.pair.source_planet_id,
        target_planet_id=estimated_pair.pair.target_planet_id,
        error=error,
    )


def _planet_by_id(state: GameState, planet_id: int) -> Planet | None:
    for planet in state.planets:
        if planet.planet_id == planet_id:
            return planet
    return None


__all__ = (
    "CandidateOutcomeReport",
    "CandidateValidationStatus",
    "validate_estimated_pair_outcome",
    "validate_estimated_pair_outcomes",
)
