"""Local evaluation harness contracts and runners for Orbit Wars.

The harness supports typed match contracts, local official-environment smoke
runs, reusable agent loading, deterministic built-in baselines, single-match
metrics extraction, optional artifact capture, and sequential batch execution.
Scoreboard records and a quick regression gate are available for local checks;
analysis packs can summarize completed results for planner improvement. Live
submission automation remains deferred.
"""

from .analysis_pack import (
    PlannerAnalysisItem,
    PlannerAnalysisPack,
    PlannerAnalysisPackConfig,
    build_planner_analysis_pack,
)
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
from .experiment_manifest import (
    ExperimentManifest,
    ExperimentScenario,
    PromotionThresholds,
    manifest_to_match_configs,
)
from .experiment_cli import (
    ExperimentCliResult,
    main as run_evaluation_experiment_main,
    run_evaluation_experiment,
)
from .experiment_report import (
    ExperimentReport,
    build_experiment_report,
    read_experiment_report,
    write_experiment_report,
)
from .experiment_runner import (
    ExperimentRunConfig,
    ExperimentRunResult,
    run_experiment_manifest,
)
from .experiment_suite import (
    ExperimentSuiteResult,
    default_manifest_paths,
    main as run_evaluation_suite_main,
    run_evaluation_suite,
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
from .promotion_gate import (
    PromotionGateDecision,
    PromotionGateFailure,
    evaluate_promotion_gate,
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
    "ExperimentCliResult",
    "ExperimentManifest",
    "ExperimentReport",
    "ExperimentRunConfig",
    "ExperimentRunResult",
    "ExperimentScenario",
    "ExperimentSuiteResult",
    "KaggleAgent",
    "FailureCategory",
    "FailureTriageItem",
    "FailureTriageReport",
    "MatchConfig",
    "MatchMetrics",
    "MatchResult",
    "OpponentSpec",
    "PlayerCount",
    "PlannerAnalysisItem",
    "PlannerAnalysisPack",
    "PlannerAnalysisPackConfig",
    "PromotionGateDecision",
    "PromotionGateFailure",
    "PromotionThresholds",
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
    "build_experiment_report",
    "build_planner_analysis_pack",
    "builtin_baseline_spec",
    "default_manifest_paths",
    "evaluate_promotion_gate",
    "extract_match_metrics",
    "load_agent_callable",
    "load_builtin_baseline",
    "manifest_to_match_configs",
    "read_experiment_report",
    "read_scoreboard_records",
    "run_evaluation_batch",
    "run_evaluation_experiment",
    "run_evaluation_experiment_main",
    "run_evaluation_suite",
    "run_evaluation_suite_main",
    "run_experiment_manifest",
    "run_official_match",
    "run_regression_gate",
    "run_submission_parity_check",
    "submission_agent_spec",
    "summarize_match_results",
    "triage_evaluation_batch",
    "triage_match_result",
    "triage_match_results",
    "write_scoreboard_record",
    "write_experiment_report",
    "write_match_result_artifact",
    "write_replay_artifact",
)
