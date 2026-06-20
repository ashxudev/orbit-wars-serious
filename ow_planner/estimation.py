"""Planner ship requirement estimation.

Mission Generation Cycle 4 converts factual source-target pairs into
deterministic first-pass ship estimates and typed launch candidates. It does
not run simulator rollouts, validate arrivals, score missions, model opponent
response, or choose actions.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from ow_sim.forecast import angle_to_point

from .candidates import CandidateGenerationConfig, LaunchCandidate
from .enumeration import SourceTargetPair, TargetCategory


DEFAULT_CAPTURE_BUFFER_SHIPS = 1
"""Default deterministic buffer so exact-zero combat is not treated as capture."""


class ShipEstimateStatus(str, Enum):
    """Status for a first-pass ship requirement estimate."""

    AFFORDABLE = "affordable"
    INSUFFICIENT_SOURCE_SHIPS = "insufficient_source_ships"
    INVALID_TARGET = "invalid_target"


@dataclass(frozen=True, slots=True)
class ShipEstimate:
    """First-pass ships required for a factual source-target pair."""

    target_category: TargetCategory
    required_ships: int
    source_available_ships: int
    target_projected_ships: int
    production_added: int
    buffer_ships: int
    status: ShipEstimateStatus


@dataclass(frozen=True, slots=True)
class EstimatedPair:
    """Source-target pair with its ship estimate and optional launch."""

    pair: SourceTargetPair
    estimate: ShipEstimate
    launch: LaunchCandidate | None


def estimate_required_ships_for_pair(
    pair: SourceTargetPair,
    config: CandidateGenerationConfig | None = None,
) -> ShipEstimate:
    """Estimate ships needed to capture ``pair.target_planet_id``.

    Neutral and owned reinforcement targets do not add production pressure for
    this first-pass estimate. Enemy targets add
    ``target_production * rough_travel_ticks``. The default one-ship buffer
    makes capture requirements strictly greater than projected defenders.
    Owned targets use a one-ship reinforcement estimate so capture-hold windows
    can produce normal validated candidates instead of starving generation.
    ``config`` is accepted for API consistency but does not tune this first-pass
    estimator yet.
    """

    _ = config
    if not _is_valid_pair_for_estimation(pair):
        return ShipEstimate(
            target_category=pair.target_category,
            required_ships=0,
            source_available_ships=max(0, pair.source_affordable_ships),
            target_projected_ships=max(0, pair.target_ships),
            production_added=0,
            buffer_ships=DEFAULT_CAPTURE_BUFFER_SHIPS,
            status=ShipEstimateStatus.INVALID_TARGET,
        )

    production_added = _production_added(pair)
    target_projected_ships = pair.target_ships + production_added
    required_ships = _required_ships(pair, target_projected_ships)
    status = (
        ShipEstimateStatus.AFFORDABLE
        if required_ships <= pair.source_affordable_ships
        else ShipEstimateStatus.INSUFFICIENT_SOURCE_SHIPS
    )
    return ShipEstimate(
        target_category=pair.target_category,
        required_ships=required_ships,
        source_available_ships=pair.source_affordable_ships,
        target_projected_ships=target_projected_ships,
        production_added=production_added,
        buffer_ships=DEFAULT_CAPTURE_BUFFER_SHIPS,
        status=status,
    )


def launch_candidate_from_pair(
    pair: SourceTargetPair,
    config: CandidateGenerationConfig | None = None,
) -> LaunchCandidate | None:
    """Return a launch candidate when the first-pass estimate is affordable."""

    estimate = estimate_required_ships_for_pair(pair, config=config)
    if estimate.status is not ShipEstimateStatus.AFFORDABLE:
        return None
    return LaunchCandidate(
        source_planet_id=pair.source_planet_id,
        angle=angle_to_point(pair.source_position, pair.target_position),
        ships=estimate.required_ships,
    )


def estimate_source_target_pairs(
    pairs: Sequence[SourceTargetPair],
    config: CandidateGenerationConfig | None = None,
) -> tuple[EstimatedPair, ...]:
    """Estimate pairs in input order and include affordable launches."""

    return tuple(
        EstimatedPair(
            pair=pair,
            estimate=estimate_required_ships_for_pair(pair, config=config),
            launch=launch_candidate_from_pair(pair, config=config),
        )
        for pair in pairs
    )


def _is_valid_pair_for_estimation(pair: SourceTargetPair) -> bool:
    return (
        isinstance(pair.target_category, TargetCategory)
        and pair.target_ships >= 0
        and pair.target_production >= 0
        and pair.rough_travel_ticks >= 0
        and pair.source_affordable_ships >= 0
    )


def _production_added(pair: SourceTargetPair) -> int:
    if pair.target_category is TargetCategory.NEUTRAL:
        return 0
    if pair.target_category is TargetCategory.OWN:
        return 0
    if pair.target_category is TargetCategory.ENEMY:
        return pair.target_production * pair.rough_travel_ticks
    return 0


def _required_ships(pair: SourceTargetPair, target_projected_ships: int) -> int:
    if pair.target_category is TargetCategory.OWN:
        return 1
    return target_projected_ships + DEFAULT_CAPTURE_BUFFER_SHIPS


__all__ = (
    "DEFAULT_CAPTURE_BUFFER_SHIPS",
    "EstimatedPair",
    "ShipEstimate",
    "ShipEstimateStatus",
    "estimate_required_ships_for_pair",
    "estimate_source_target_pairs",
    "launch_candidate_from_pair",
)
