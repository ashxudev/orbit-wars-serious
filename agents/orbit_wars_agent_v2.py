"""Orbit Wars runtime entrypoint with Planner V2 explicitly enabled.

This module is for local experiments, gauntlets, and Daytona probes. The
default Kaggle/submission entrypoint remains ``agents.orbit_wars_agent`` and
continues to use Planner V1 unless a caller explicitly selects this module.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Mapping

from ow_planner.actions import KaggleActionRow

from .runtime_config import runtime_turn_config_for_observation as _base_config
from .runtime_planner import PLANNER_VERSION_V2, RuntimePlannerConfig
from .runtime_turn import RuntimeTurnConfig, safe_actions_for_observation


def runtime_turn_config_for_observation(
    observation: Mapping[str, object],
    configuration: object | None = None,
) -> RuntimeTurnConfig:
    """Build a normal runtime config with Planner V2 enabled."""

    config = _base_config(observation, configuration)
    planner_config = config.planner_config or RuntimePlannerConfig()
    return replace(
        config,
        planner_config=replace(
            planner_config,
            planner_version=PLANNER_VERSION_V2,
        ),
    )


def agent(
    observation: Mapping[str, object],
    configuration: object | None = None,
) -> list[KaggleActionRow]:
    """Return safe Kaggle action rows for one observation using Planner V2."""

    config = runtime_turn_config_for_observation(observation, configuration)
    return safe_actions_for_observation(observation, configuration, config)


__all__ = ("agent", "runtime_turn_config_for_observation")
