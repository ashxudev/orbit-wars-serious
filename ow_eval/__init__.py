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
from .daytona_jobs import (
    DaytonaShardJobPlan,
    DaytonaShardJobPlanConfig,
    DaytonaShardJobSpec,
    build_daytona_shard_job_plan,
)
from .daytona_plan_cli import (
    DaytonaShardJobPlanWriteResult,
    main as prepare_daytona_shard_jobs_main,
    prepare_daytona_shard_job_plan,
    write_daytona_shard_job_plan,
)
from .daytona_preflight import (
    DaytonaShardJobPlanValidationResult,
    main as validate_daytona_shard_jobs_main,
    read_daytona_shard_job_plan,
    validate_daytona_shard_job_plan,
)
from .daytona_executor import (
    DaytonaShardExecutionBatchResult,
    DaytonaShardExecutionRequest,
    DaytonaShardExecutionResult,
    DaytonaShardJobExecutor,
    run_daytona_shard_job_plan,
)
from .daytona_executor_cli import (
    DaytonaDryRunExecutor,
    DaytonaExecutorCliResult,
    main as run_daytona_shard_jobs_main,
    run_daytona_shard_jobs,
)
from .daytona_operations import (
    DaytonaBatchOperationPlan,
    DaytonaCommandOperation,
    DaytonaDownloadOperation,
    DaytonaSandboxOperationPlan,
    DaytonaUploadOperation,
    build_daytona_batch_operation_plan,
    build_daytona_sandbox_operation_plan,
)
from .daytona_client_executor import (
    DaytonaClientCommandResult,
    DaytonaClientExecutionEvent,
    DaytonaClientExecutor,
    DaytonaSandboxClient,
    DaytonaSandboxHandle,
    run_daytona_shard_job_plan_with_client,
)
from .daytona_client_report import (
    DaytonaClientExecutionReport,
    run_daytona_shard_job_plan_with_client_report,
)
from .daytona_client_report_cli import (
    DaytonaClientReportCliResult,
    DaytonaRecordingClient,
    main as run_daytona_client_report_main,
    run_daytona_client_report,
)
from .daytona_real_config import (
    DaytonaRealExecutionConfig,
    DaytonaRealExecutionReadiness,
    read_daytona_real_execution_config_from_env,
    validate_daytona_real_execution_readiness,
)
from .daytona_real_cli import (
    DaytonaRealCliResult,
    main as run_daytona_real_shard_jobs_main,
    run_daytona_real_shard_jobs,
)
from .daytona_real_smoke import (
    DaytonaRealSmokeEvent,
    DaytonaRealSmokeResult,
    main as run_daytona_real_smoke_main,
    run_daytona_real_smoke,
)
from .daytona_runtime_snapshot import (
    DaytonaRuntimeSnapshotConfig,
    DaytonaRuntimeSnapshotPlan,
    DaytonaRuntimeSnapshotResult,
    main as prepare_daytona_runtime_snapshot_main,
    prepare_daytona_runtime_snapshot,
    prepare_daytona_runtime_snapshot_context,
)
from .daytona_sdk_adapter import (
    DaytonaSdkAdapter,
    DaytonaSdkAdapterConfig,
    DaytonaSdkProtocolClient,
    DaytonaSdkUnavailableError,
    build_daytona_sdk_protocol_client,
)
from .distributed_preflight import (
    DistributedEvaluationPreflightConfig,
    DistributedEvaluationPreflightResult,
    DistributedEvaluationPreflightStageResult,
    main as run_distributed_evaluation_preflight_main,
    run_distributed_evaluation_preflight,
)
from .historical_gauntlet_shards import (
    HistoricalChampionShard,
    HistoricalChampionShardPlan,
    HistoricalChampionShardScenario,
    build_historical_champion_evaluation_shard_plan,
    build_historical_champion_full_evaluation_shard_plan,
    build_historical_champion_shard_plan,
    default_historical_champion_manifest_paths,
    main as prepare_historical_champion_gauntlet_package_main,
    select_historical_champion_shard,
    write_historical_champion_full_shard_package,
    write_historical_champion_probe_shard_package,
)
from .historical_leak_regression import (
    HistoricalLeakRegressionCaseResult,
    HistoricalLeakRegressionMetrics,
    HistoricalLeakRegressionReport,
    default_historical_leak_fixture_dir,
    run_historical_leak_regression,
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
from .local_tests import (
    LocalTestModule,
    LocalTestResult,
    LocalTestRunSummary,
    build_unittest_command,
    default_worker_count,
    discover_test_modules,
    run_test_module,
    run_test_modules,
)
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
from .sharding import (
    EvaluationShard,
    EvaluationShardPlan,
    ShardPlanConfig,
    build_evaluation_shard_plan,
)
from .shard_runner import (
    EvaluationShardRunConfig,
    EvaluationShardRunResult,
    run_evaluation_shard,
)
from .shard_persistence import (
    read_evaluation_shard_run_result,
    write_evaluation_shard_run_result,
)
from .shard_merge import (
    EvaluationShardMergeResult,
    merge_evaluation_shard_result_files,
    merge_evaluation_shard_results,
)
from .shard_manifests import (
    EvaluationShardManifestWriteResult,
    shard_to_experiment_manifest,
    write_evaluation_shard_manifest,
    write_evaluation_shard_manifests,
)
from .shard_jobs import (
    EvaluationShardJob,
    EvaluationShardJobPackageResult,
    build_evaluation_shard_jobs,
    write_evaluation_shard_job_package,
)
from .shard_package_cli import (
    EvaluationShardPackageCliResult,
    main as prepare_evaluation_shards_main,
    prepare_evaluation_shard_package,
)
from .shard_job_runner import (
    EvaluationShardJobRunResult,
    evaluation_shard_from_job,
    main as run_evaluation_shard_job_main,
    read_evaluation_shard_job,
    run_evaluation_shard_job,
)
from .shard_index_runner import (
    EvaluationShardIndexRunResult,
    EvaluationShardJobIndex,
    main as run_evaluation_shard_index_main,
    read_evaluation_shard_job_index,
    run_evaluation_shard_job_index,
)
from .shard_cli import (
    EvaluationShardCliResult,
    main as run_evaluation_shards_main,
    run_evaluation_shards,
)
from .submission_preflight import (
    SubmissionPreflightCheck,
    SubmissionPreflightResult,
    main as run_submission_preflight_main,
    run_submission_preflight,
)
from .triage import (
    FailureCategory,
    FailureTriageItem,
    FailureTriageReport,
    triage_evaluation_batch,
    triage_match_result,
    triage_match_results,
)
from .v0_replay_regression import (
    V0ReplayRegressionCaseResult,
    V0ReplayRegressionMetrics,
    V0ReplayRegressionReport,
    default_v0_replay_fixture_dir,
    run_v0_replay_regression,
)
from .v1_replay_regression import (
    V1ReplayRegressionCaseResult,
    V1ReplayRegressionMetrics,
    V1ReplayRegressionReport,
    default_v1_replay_fixture_dir,
    run_v1_replay_regression,
)

__all__ = (
    "AgentSourceKind",
    "AgentSpec",
    "BaselineName",
    "DaytonaShardJobPlan",
    "DaytonaShardJobPlanConfig",
    "DaytonaShardJobPlanValidationResult",
    "DaytonaShardJobPlanWriteResult",
    "DaytonaShardJobSpec",
    "DaytonaShardExecutionBatchResult",
    "DaytonaShardExecutionRequest",
    "DaytonaShardExecutionResult",
    "DaytonaShardJobExecutor",
    "DaytonaDryRunExecutor",
    "DaytonaExecutorCliResult",
    "DaytonaBatchOperationPlan",
    "DaytonaCommandOperation",
    "DaytonaDownloadOperation",
    "DaytonaSandboxOperationPlan",
    "DaytonaUploadOperation",
    "DaytonaClientCommandResult",
    "DaytonaClientExecutionEvent",
    "DaytonaClientExecutor",
    "DaytonaSandboxClient",
    "DaytonaSandboxHandle",
    "DaytonaClientExecutionReport",
    "DaytonaClientReportCliResult",
    "DaytonaRecordingClient",
    "DaytonaRealCliResult",
    "DaytonaRealExecutionConfig",
    "DaytonaRealExecutionReadiness",
    "DaytonaRealSmokeEvent",
    "DaytonaRealSmokeResult",
    "DaytonaRuntimeSnapshotConfig",
    "DaytonaRuntimeSnapshotPlan",
    "DaytonaRuntimeSnapshotResult",
    "DaytonaSdkAdapter",
    "DaytonaSdkAdapterConfig",
    "DaytonaSdkProtocolClient",
    "DaytonaSdkUnavailableError",
    "DistributedEvaluationPreflightConfig",
    "DistributedEvaluationPreflightResult",
    "DistributedEvaluationPreflightStageResult",
    "EvaluationStatus",
    "HistoricalChampionShard",
    "HistoricalChampionShardPlan",
    "HistoricalChampionShardScenario",
    "HistoricalLeakRegressionCaseResult",
    "HistoricalLeakRegressionMetrics",
    "HistoricalLeakRegressionReport",
    "EvaluationArtifactConfig",
    "EvaluationBatchConfig",
    "EvaluationBatchResult",
    "EvaluationBatchSummary",
    "EvaluationShard",
    "EvaluationShardCliResult",
    "EvaluationShardIndexRunResult",
    "EvaluationShardJob",
    "EvaluationShardJobIndex",
    "EvaluationShardJobPackageResult",
    "EvaluationShardJobRunResult",
    "EvaluationShardManifestWriteResult",
    "EvaluationShardMergeResult",
    "EvaluationShardPackageCliResult",
    "EvaluationShardPlan",
    "EvaluationShardRunConfig",
    "EvaluationShardRunResult",
    "ExperimentCliResult",
    "ExperimentManifest",
    "ExperimentReport",
    "ExperimentRunConfig",
    "ExperimentRunResult",
    "ExperimentScenario",
    "ExperimentSuiteResult",
    "KaggleAgent",
    "LocalTestModule",
    "LocalTestResult",
    "LocalTestRunSummary",
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
    "ShardPlanConfig",
    "SubmissionParityComparison",
    "SubmissionParityConfig",
    "SubmissionParityResult",
    "SubmissionPreflightCheck",
    "SubmissionPreflightResult",
    "V0ReplayRegressionCaseResult",
    "V0ReplayRegressionMetrics",
    "V0ReplayRegressionReport",
    "V1ReplayRegressionCaseResult",
    "V1ReplayRegressionMetrics",
    "V1ReplayRegressionReport",
    "available_builtin_baselines",
    "append_scoreboard_record",
    "build_scoreboard_record",
    "build_experiment_report",
    "build_evaluation_shard_plan",
    "build_evaluation_shard_jobs",
    "build_planner_analysis_pack",
    "builtin_baseline_spec",
    "build_daytona_shard_job_plan",
    "build_daytona_batch_operation_plan",
    "build_daytona_sandbox_operation_plan",
    "build_daytona_sdk_protocol_client",
    "build_historical_champion_evaluation_shard_plan",
    "build_historical_champion_full_evaluation_shard_plan",
    "build_historical_champion_shard_plan",
    "build_unittest_command",
    "default_historical_champion_manifest_paths",
    "default_historical_leak_fixture_dir",
    "default_manifest_paths",
    "default_worker_count",
    "default_v0_replay_fixture_dir",
    "default_v1_replay_fixture_dir",
    "discover_test_modules",
    "evaluate_promotion_gate",
    "evaluation_shard_from_job",
    "extract_match_metrics",
    "load_agent_callable",
    "load_builtin_baseline",
    "manifest_to_match_configs",
    "merge_evaluation_shard_result_files",
    "merge_evaluation_shard_results",
    "prepare_evaluation_shard_package",
    "prepare_daytona_shard_job_plan",
    "prepare_daytona_shard_jobs_main",
    "prepare_daytona_runtime_snapshot",
    "prepare_daytona_runtime_snapshot_context",
    "prepare_daytona_runtime_snapshot_main",
    "prepare_evaluation_shards_main",
    "prepare_historical_champion_gauntlet_package_main",
    "read_evaluation_shard_run_result",
    "read_evaluation_shard_job",
    "read_evaluation_shard_job_index",
    "read_daytona_shard_job_plan",
    "read_daytona_real_execution_config_from_env",
    "read_experiment_report",
    "read_scoreboard_records",
    "run_daytona_shard_job_plan",
    "run_daytona_shard_jobs",
    "run_daytona_shard_jobs_main",
    "run_daytona_shard_job_plan_with_client",
    "run_daytona_shard_job_plan_with_client_report",
    "run_daytona_client_report",
    "run_daytona_client_report_main",
    "run_daytona_real_shard_jobs",
    "run_daytona_real_shard_jobs_main",
    "run_daytona_real_smoke",
    "run_daytona_real_smoke_main",
    "run_distributed_evaluation_preflight",
    "run_distributed_evaluation_preflight_main",
    "run_evaluation_batch",
    "run_evaluation_experiment",
    "run_evaluation_experiment_main",
    "run_evaluation_shard",
    "run_evaluation_shard_index_main",
    "run_evaluation_shard_job",
    "run_evaluation_shard_job_index",
    "run_evaluation_shard_job_main",
    "run_evaluation_shards",
    "run_evaluation_shards_main",
    "run_evaluation_suite",
    "run_evaluation_suite_main",
    "run_experiment_manifest",
    "run_historical_leak_regression",
    "run_official_match",
    "run_regression_gate",
    "run_submission_parity_check",
    "run_submission_preflight",
    "run_submission_preflight_main",
    "run_test_module",
    "run_test_modules",
    "run_v0_replay_regression",
    "run_v1_replay_regression",
    "select_historical_champion_shard",
    "shard_to_experiment_manifest",
    "submission_agent_spec",
    "summarize_match_results",
    "triage_evaluation_batch",
    "triage_match_result",
    "triage_match_results",
    "validate_daytona_shard_job_plan",
    "validate_daytona_shard_jobs_main",
    "validate_daytona_real_execution_readiness",
    "write_scoreboard_record",
    "write_evaluation_shard_run_result",
    "write_evaluation_shard_manifest",
    "write_evaluation_shard_manifests",
    "write_evaluation_shard_job_package",
    "write_historical_champion_full_shard_package",
    "write_historical_champion_probe_shard_package",
    "write_daytona_shard_job_plan",
    "write_experiment_report",
    "write_match_result_artifact",
    "write_replay_artifact",
)
