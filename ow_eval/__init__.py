"""Local evaluation harness contracts and runners for Orbit Wars.

The harness supports typed match contracts, local official-environment smoke
runs, reusable agent loading, deterministic built-in baselines, single-match
metrics extraction, optional artifact capture, and sequential batch execution.
Scoreboard records and a quick regression gate are available for local checks;
live submission automation remains deferred.
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
from .parity import (
    SubmissionParityComparison,
    SubmissionParityConfig,
    SubmissionParityResult,
    run_submission_parity_check,
    submission_agent_spec,
)
from .regression_gate import (
    RegressionGateConfig,
    RegressionGateFailure,
    RegressionGateResult,
    run_regression_gate,
)
from .scoreboard import (
    ScoreboardRecord,
    append_scoreboard_record,
    build_scoreboard_record,
    read_scoreboard_records,
    write_scoreboard_record,
)
from .triage import (
    FailureCategory,
    FailureTriageItem,
    FailureTriageReport,
    triage_evaluation_batch,
    triage_match_result,
    triage_match_results,
)

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
    "FailureCategory",
    "FailureTriageItem",
    "FailureTriageReport",
    "MatchConfig",
    "MatchMetrics",
    "MatchResult",
    "OpponentSpec",
    "PlayerCount",
    "RegressionGateConfig",
    "RegressionGateFailure",
    "RegressionGateResult",
    "ScoreboardRecord",
    "SubmissionParityComparison",
    "SubmissionParityConfig",
    "SubmissionParityResult",
    "available_builtin_baselines",
    "append_scoreboard_record",
    "build_scoreboard_record",
    "builtin_baseline_spec",
    "extract_match_metrics",
    "load_agent_callable",
    "load_builtin_baseline",
    "read_scoreboard_records",
    "run_evaluation_batch",
    "run_official_match",
    "run_regression_gate",
    "run_submission_parity_check",
    "submission_agent_spec",
    "summarize_match_results",
    "triage_evaluation_batch",
    "triage_match_result",
    "triage_match_results",
    "write_scoreboard_record",
    "write_match_result_artifact",
    "write_replay_artifact",
)
