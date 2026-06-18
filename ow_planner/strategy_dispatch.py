"""Unified strategy-mode dispatch boundary.

Strategy Modes Cycle 8 routes already-built planner decision bundles to the
existing 2-player or 4-player selector based on supplied or inferred strategy
mode facts. It does not generate, evaluate, score, model responses, build
commitments, convert actions, run simulator rollouts, or reinterpret selector
results.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .four_player_selection import FourPlayerSelectionConfig, select_four_player_strategy
from .four_player_strategy import FourPlayerBoardFacts
from .strategy_decisions import (
    PlannerDecisionBundle,
    StrategySelectionResult,
    rejected_strategy_result,
)
from .strategy_modes import StrategyMode, StrategyModeFacts
from .two_player_selection import (
    TwoPlayerSelectionConfig,
    select_two_player_direct_advantage,
)


@dataclass(frozen=True, slots=True)
class StrategyDispatchConfig:
    """Configuration boundary for strategy-mode dispatch."""

    two_player_config: TwoPlayerSelectionConfig | None = None
    four_player_config: FourPlayerSelectionConfig | None = None

    def __post_init__(self) -> None:
        if self.two_player_config is not None and not isinstance(
            self.two_player_config,
            TwoPlayerSelectionConfig,
        ):
            raise ValueError(
                "two_player_config must be None or TwoPlayerSelectionConfig"
            )
        if self.four_player_config is not None and not isinstance(
            self.four_player_config,
            FourPlayerSelectionConfig,
        ):
            raise ValueError(
                "four_player_config must be None or FourPlayerSelectionConfig"
            )


def select_strategy_for_mode(
    bundles: Sequence[PlannerDecisionBundle],
    *,
    strategy_mode_facts: StrategyModeFacts | None = None,
    four_player_board_facts: FourPlayerBoardFacts | None = None,
    config: StrategyDispatchConfig | None = None,
) -> StrategySelectionResult:
    """Dispatch to the selector for the supplied or inferred strategy mode."""

    effective_config = StrategyDispatchConfig() if config is None else config
    effective_strategy_mode_facts = strategy_mode_facts or _infer_strategy_mode_facts(
        bundles
    )
    if effective_strategy_mode_facts is None:
        return rejected_strategy_result(notes=("missing strategy mode facts",))
    if effective_strategy_mode_facts.mode is StrategyMode.TWO_PLAYER:
        return select_two_player_direct_advantage(
            bundles,
            config=effective_config.two_player_config,
        )
    if effective_strategy_mode_facts.mode is StrategyMode.FOUR_PLAYER:
        return select_four_player_strategy(
            bundles,
            four_player_board_facts,
            config=effective_config.four_player_config,
        )
    return rejected_strategy_result(
        strategy_mode_facts=effective_strategy_mode_facts,
        notes=("unknown strategy mode",),
    )


def _infer_strategy_mode_facts(
    bundles: Sequence[PlannerDecisionBundle],
) -> StrategyModeFacts | None:
    for bundle in bundles:
        if bundle.strategy_mode_facts is not None:
            return bundle.strategy_mode_facts
    return None


__all__ = (
    "StrategyDispatchConfig",
    "select_strategy_for_mode",
)
