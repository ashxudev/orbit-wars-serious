"""Two-player pressure-retention selection facts.

V0 Replay Leak Fix Cycle 4 adds a small pressure signal for two-player
selection. It consumes already-computed response labels and selected
commitment options only; it does not generate missions, run simulator
rollouts, or evaluate new defense policy.
"""

from __future__ import annotations

from dataclasses import dataclass

from .commitment import CommitmentOption, CommitmentOptionType
from .two_player_strategy import TwoPlayerAdvantageFacts


PRESSURE_RESPONSE_LABELS = (
    "target_reinforcement_feasible",
    "target_race_risk",
    "source_counterattack_risk",
)


@dataclass(frozen=True, slots=True)
class TwoPlayerPressureFacts:
    """Deterministic pressure-retention facts for one eligible 2P option."""

    response_pressure_active: bool = False
    reserve_preserving_commitment: bool = False
    pressure_labels: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


def two_player_pressure_facts(
    facts: TwoPlayerAdvantageFacts,
    commitment_option: CommitmentOption | None,
) -> TwoPlayerPressureFacts:
    """Return pressure-retention facts for one candidate/commitment pair."""

    pressure_labels = tuple(
        label for label in facts.response_labels if label in PRESSURE_RESPONSE_LABELS
    )
    response_pressure_active = bool(pressure_labels)
    reserve_preserving_commitment = (
        commitment_option is not None
        and commitment_option.option_type is CommitmentOptionType.RESERVE_PRESERVING
    )
    notes = ()
    if response_pressure_active and reserve_preserving_commitment:
        notes = ("pressure reserve-preserving option",)
    elif response_pressure_active:
        notes = ("pressure non-reserve option",)
    return TwoPlayerPressureFacts(
        response_pressure_active=response_pressure_active,
        reserve_preserving_commitment=reserve_preserving_commitment,
        pressure_labels=pressure_labels,
        notes=notes,
    )


__all__ = (
    "PRESSURE_RESPONSE_LABELS",
    "TwoPlayerPressureFacts",
    "two_player_pressure_facts",
)
