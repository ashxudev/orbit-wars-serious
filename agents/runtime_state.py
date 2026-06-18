"""Runtime observation-to-state adapter.

Runtime / Submission Cycle 1 delegates Kaggle observation parsing to the
existing simulator ``GameState`` parser. Planner composition, action
conversion, simulator futures, and submission behavior remain deferred.
"""

from __future__ import annotations

from typing import Mapping

from ow_sim.state import GameState


def observation_to_game_state(observation: Mapping[str, object]) -> GameState:
    """Parse a Kaggle observation into the simulator ``GameState`` shape."""

    return GameState.from_obs(observation)


__all__ = ("observation_to_game_state",)
