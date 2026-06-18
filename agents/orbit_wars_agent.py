"""Orbit Wars runtime entrypoint.

The Kaggle-callable ``agent`` delegates through the safe runtime turn boundary,
which owns parser/planner/action fallback behavior and optional stage-start
budget guards. Submission bundling remains deferred to later runtime cycles.
"""

from __future__ import annotations

from typing import Mapping

from ow_planner.actions import KaggleActionRow

from .runtime_config import runtime_turn_config_for_observation
from .runtime_turn import safe_actions_for_observation


def agent(
    observation: Mapping[str, object],
    configuration: object | None = None,
) -> list[KaggleActionRow]:
    """Return safe Kaggle action rows for one observation."""

    config = runtime_turn_config_for_observation(observation, configuration)
    return safe_actions_for_observation(observation, configuration, config)


__all__ = ("agent",)
