"""Planner V2 runtime entrypoint with trajectory second-source disabled.

This module exists for A/B gauntlets. It keeps Planner V2 diagnostics and
scenario evaluation enabled while suppressing only the
``trajectory_second_source`` behavior surface.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Mapping

from ow_planner.actions import KaggleActionRow
from ow_planner_v2 import PlannerV2Config

from .runtime_config import runtime_turn_config_for_observation as _base_config
from .runtime_planner import PLANNER_VERSION_V2, RuntimePlannerConfig
from .runtime_turn import RuntimeTurnConfig, safe_actions_for_observation


def runtime_turn_config_for_observation(
    observation: Mapping[str, object],
    configuration: object | None = None,
) -> RuntimeTurnConfig:
    """Build a normal runtime config with Planner V2 trajectory behavior off."""

    config = _base_config(observation, configuration)
    planner_config = config.planner_config or RuntimePlannerConfig()
    v2_config = planner_config.planner_v2_config or PlannerV2Config(max_action_sets=4)
    return replace(
        config,
        planner_config=replace(
            planner_config,
            planner_version=PLANNER_VERSION_V2,
            planner_v2_config=replace(
                v2_config,
                enable_trajectory_second_source=False,
            ),
        ),
    )


def agent(
    observation: Mapping[str, object],
    configuration: object | None = None,
) -> list[KaggleActionRow]:
    """Return safe Kaggle action rows for one observation using V2 trajectory-off."""

    config = runtime_turn_config_for_observation(observation, configuration)
    return safe_actions_for_observation(observation, configuration, config)


__all__ = ("agent", "runtime_turn_config_for_observation")
