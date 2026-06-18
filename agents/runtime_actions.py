"""Runtime strategy-selection to Kaggle action conversion boundary.

Runtime / Submission Cycle 3 converts an already-selected validated commitment
option into Kaggle action rows through the existing planner action validation
helpers. It does not parse observations, run the planner pipeline, or wire
action emission into the runtime ``agent`` entrypoint.
"""

from __future__ import annotations

from dataclasses import replace

from ow_planner import (
    CommitmentOption,
    CommitmentOptionStatus,
    CommitmentOptionType,
    MissionCandidate,
    MissionType,
    StrategySelectionResult,
    StrategySelectionStatus,
)
from ow_planner.actions import KaggleActionRow, mission_candidate_to_actions
from ow_sim.state import GameState

from .runtime_planner import RuntimePlannerResult


def selected_commitment_to_actions(
    state: GameState,
    selection: StrategySelectionResult,
) -> list[KaggleActionRow]:
    """Convert a selected validated commitment option to Kaggle action rows."""

    if selection.status is not StrategySelectionStatus.SELECTED:
        return []

    commitment_option = selection.selected_commitment_option
    if commitment_option is None:
        return []
    if commitment_option.status is not CommitmentOptionStatus.VALIDATED:
        return []
    if commitment_option.option_type is CommitmentOptionType.NO_ATTACK:
        return []
    if not commitment_option.launches:
        return []

    mission = _mission_from_commitment_option(selection, commitment_option)
    return mission_candidate_to_actions(state, mission)


def planner_result_to_actions(result: RuntimePlannerResult) -> list[KaggleActionRow]:
    """Convert a runtime planner result's final selection to action rows."""

    return selected_commitment_to_actions(result.state, result.selection)


def _mission_from_commitment_option(
    selection: StrategySelectionResult,
    commitment_option: CommitmentOption,
) -> MissionCandidate:
    candidate = commitment_option.candidate
    if candidate is None and selection.selected_bundle is not None:
        candidate = selection.selected_bundle.candidate
    if candidate is None:
        return MissionCandidate(
            mission_type=MissionType.ATTACK_ENEMY,
            source_planet_ids=commitment_option.source_planet_ids,
            launches=commitment_option.launches,
        )
    return replace(
        candidate,
        source_planet_ids=commitment_option.source_planet_ids,
        launches=commitment_option.launches,
    )


__all__ = (
    "planner_result_to_actions",
    "selected_commitment_to_actions",
)
