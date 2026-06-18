"""Local evaluation harness contracts and runners for Orbit Wars.

The harness supports typed match contracts, local official-environment smoke
runs, reusable agent loading, deterministic built-in baselines, single-match
metrics extraction, optional artifact capture, and sequential batch execution.
Scoreboards, regression gates, and live submission automation remain deferred.
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
from .batch_runner import (
    EvaluationBatchConfig,
    EvaluationBatchResult,
    EvaluationBatchSummary,
    run_evaluation_batch,
    summarize_match_results,
)
from .metrics import extract_match_metrics
from .official_runner import run_official_match

__all__ = (
    "AgentSourceKind",
    "AgentSpec",
    "BaselineName",
    "EvaluationStatus",
    "EvaluationArtifactConfig",
    "EvaluationBatchConfig",
    "EvaluationBatchResult",
    "EvaluationBatchSummary",
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
    "run_evaluation_batch",
    "run_official_match",
    "summarize_match_results",
    "write_match_result_artifact",
    "write_replay_artifact",
)
