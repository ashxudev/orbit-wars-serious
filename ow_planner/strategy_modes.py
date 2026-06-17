"""Deterministic 2-player / 4-player strategy mode detection.

Strategy Modes Cycle 0 only identifies board mode facts from current state.
It does not select strategies, generate missions, evaluate candidates, score,
or run simulator rollouts.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ow_sim.state import GameState


class StrategyMode(str, Enum):
    """Supported high-level strategy modes."""

    TWO_PLAYER = "two_player"
    FOUR_PLAYER = "four_player"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class StrategyModeFacts:
    """Factual strategy-mode classification for one parsed state."""

    mode: StrategyMode
    player_id: int | None
    active_player_ids: tuple[int, ...]
    opponent_player_ids: tuple[int, ...]
    player_count: int
    note: str | None = None


def strategy_mode_facts(state: GameState) -> StrategyModeFacts:
    """Return deterministic strategy-mode facts for ``state``."""

    active_player_ids = {
        owner
        for owner in (
            *(planet.owner for planet in state.planets),
            *(fleet.owner for fleet in state.fleets),
        )
        if owner >= 0
    }
    if state.player_id is not None and state.player_id >= 0:
        active_player_ids.add(state.player_id)

    sorted_active_player_ids = tuple(sorted(active_player_ids))
    if state.player_id is None:
        opponent_player_ids = ()
    else:
        opponent_player_ids = tuple(
            player_id
            for player_id in sorted_active_player_ids
            if player_id != state.player_id
        )

    player_count = len(sorted_active_player_ids)
    if player_count == 2:
        mode = StrategyMode.TWO_PLAYER
        note = None
    elif player_count == 4:
        mode = StrategyMode.FOUR_PLAYER
        note = None
    else:
        mode = StrategyMode.UNKNOWN
        note = "unknown player count"

    return StrategyModeFacts(
        mode=mode,
        player_id=state.player_id,
        active_player_ids=sorted_active_player_ids,
        opponent_player_ids=opponent_player_ids,
        player_count=player_count,
        note=note,
    )


def detect_strategy_mode(state: GameState) -> StrategyMode:
    """Return only the detected strategy mode for ``state``."""

    return strategy_mode_facts(state).mode


__all__ = (
    "StrategyMode",
    "StrategyModeFacts",
    "detect_strategy_mode",
    "strategy_mode_facts",
)
