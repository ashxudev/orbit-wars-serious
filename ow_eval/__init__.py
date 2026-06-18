"""Local evaluation harness contracts and runners for Orbit Wars.

The harness supports typed match contracts, local official-environment smoke
runs, reusable agent loading, deterministic built-in baselines, single-match
metrics extraction, and optional artifact capture. Scoreboards, batch runs, and
live submission automation remain deferred.
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
from .artifacts import (
    EvaluationArtifactConfig,
    write_match_result_artifact,
    write_replay_artifact,
)
from .baselines import (
    BaselineName,
    available_builtin_baselines,
    builtin_baseline_spec,
    load_builtin_baseline,
)
from .metrics import extract_match_metrics
from .official_runner import run_official_match

__all__ = (
    "AgentSourceKind",
    "AgentSpec",
    "BaselineName",
    "EvaluationStatus",
    "EvaluationArtifactConfig",
    "KaggleAgent",
    "MatchConfig",
    "MatchMetrics",
    "MatchResult",
    "OpponentSpec",
    "PlayerCount",
    "available_builtin_baselines",
    "builtin_baseline_spec",
    "extract_match_metrics",
    "load_agent_callable",
    "load_builtin_baseline",
    "run_official_match",
    "write_match_result_artifact",
    "write_replay_artifact",
)
