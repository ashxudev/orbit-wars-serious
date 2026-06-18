"""Orbit Wars runtime entrypoint.

Runtime / Submission Cycle 4 delegates the Kaggle-callable ``agent`` function
through the safe runtime turn boundary. Timing budgets and submission bundling
remain deferred to later runtime cycles.
"""

from __future__ import annotations

from typing import Mapping

from ow_planner.actions import KaggleActionRow

from .runtime_turn import safe_actions_for_observation


def agent(
    observation: Mapping[str, object],
    configuration: object | None = None,
) -> list[KaggleActionRow]:
    """Return safe Kaggle action rows for one observation."""

    return safe_actions_for_observation(observation, configuration)


__all__ = ("agent",)
