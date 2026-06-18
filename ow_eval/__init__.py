"""Local evaluation harness contracts and runners for Orbit Wars.

The harness supports typed match contracts, local official-environment smoke
runs, reusable agent loading, and deterministic built-in baselines. Replay
capture, artifact writing, scoreboards, and live submission automation remain
deferred.
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
from .baselines import (
    BaselineName,
    available_builtin_baselines,
    builtin_baseline_spec,
    load_builtin_baseline,
)
from .official_runner import run_official_match

__all__ = (
    "AgentSourceKind",
    "AgentSpec",
    "BaselineName",
    "EvaluationStatus",
    "KaggleAgent",
    "MatchConfig",
    "MatchMetrics",
    "MatchResult",
    "OpponentSpec",
    "PlayerCount",
    "available_builtin_baselines",
    "builtin_baseline_spec",
    "load_agent_callable",
    "load_builtin_baseline",
    "run_official_match",
)
