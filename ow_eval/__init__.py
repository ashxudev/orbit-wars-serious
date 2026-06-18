"""Local evaluation harness contracts for Orbit Wars.

Evaluation Harness Cycle 0 exposes typed result/config data shapes only. Match
execution, Kaggle environment integration, replay capture, and artifact writing
remain deferred to later cycles.
"""

from .contracts import (
    AgentSourceKind,
    AgentSpec,
    EvaluationStatus,
    MatchConfig,
    MatchMetrics,
    MatchResult,
    OpponentSpec,
    PlayerCount,
)
from .agent_loading import KaggleAgent, load_agent_callable
from .official_runner import run_official_match

__all__ = (
    "AgentSourceKind",
    "AgentSpec",
    "EvaluationStatus",
    "KaggleAgent",
    "MatchConfig",
    "MatchMetrics",
    "MatchResult",
    "OpponentSpec",
    "PlayerCount",
    "load_agent_callable",
    "run_official_match",
)
