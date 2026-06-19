"""Tests for Evaluation Harness Cycle 8 failure triage."""

from __future__ import annotations

import importlib
import json
import unittest
from dataclasses import FrozenInstanceError

from ow_eval import (
    AgentSourceKind,
    AgentSpec,
    EvaluationBatchResult,
    EvaluationStatus,
    FailureCategory,
    FailureTriageItem,
    FailureTriageReport,
    MatchConfig,
    MatchMetrics,
    MatchResult,
    OpponentSpec,
    PlayerCount,
    triage_evaluation_batch,
    triage_match_result,
    triage_match_results,
)


def match_config(seed: int = 7, label: str | None = "triage") -> MatchConfig:
    return MatchConfig(
        seed=seed,
        player_count=PlayerCount.TWO_PLAYER,
        controlled_seat=0,
        candidate_agent=AgentSpec(
            name="candidate",
            source_kind=AgentSourceKind.MODULAR_AGENT,
            module_path="agents.orbit_wars_agent",
        ),
        opponent_agents=(
            OpponentSpec(
                AgentSpec(
                    name="opponent",
                    source_kind=AgentSourceKind.BUILTIN_BASELINE,
                )
            ),
        ),
        label=label,
    )


def match_result(
    *,
    status: EvaluationStatus = EvaluationStatus.COMPLETED,
    metrics: MatchMetrics | None = None,
    error_text: str | None = None,
    seed: int = 7,
    label: str | None = "triage",
    artifact_path: str | None = None,
    replay_path: str | None = None,
    metadata: tuple[tuple[str, str], ...] = (),
) -> MatchResult:
    return MatchResult(
        config=match_config(seed=seed, label=label),
        status=status,
        metrics=MatchMetrics(final_rank=1) if metrics is None else metrics,
        error_text=error_text,
        artifact_path=artifact_path,
        replay_path=replay_path,
        metadata=metadata,
    )


class EvaluationTriageTests(unittest.TestCase):
    def test_triage_module_imports_and_exports_are_available(self) -> None:
        module = importlib.import_module("ow_eval.triage")

        self.assertIs(module.FailureCategory, FailureCategory)
        self.assertIs(module.FailureTriageItem, FailureTriageItem)
        self.assertIs(module.FailureTriageReport, FailureTriageReport)
        self.assertIs(module.triage_match_result, triage_match_result)
        self.assertIs(module.triage_match_results, triage_match_results)
        self.assertIs(module.triage_evaluation_batch, triage_evaluation_batch)

    def test_triage_contracts_are_frozen_and_slotted(self) -> None:
        item = triage_match_result(match_result(), index=3)
        report = triage_match_results((match_result(),))

        with self.assertRaises(FrozenInstanceError):
            item.reason = "changed"  # type: ignore[misc]
        with self.assertRaises((AttributeError, TypeError)):
            item.extra = "nope"  # type: ignore[attr-defined]
        with self.assertRaises(FrozenInstanceError):
            report.total_results = 2  # type: ignore[misc]

    def test_parse_crash_category_from_observation_error_text(self) -> None:
        item = triage_match_result(
            match_result(
                status=EvaluationStatus.AGENT_ERROR,
                error_text="ValueError: observation_to_game_state failed",
            )
        )
        state_adapter_item = triage_match_result(
            match_result(
                status=EvaluationStatus.AGENT_ERROR,
                error_text="ValueError: state adapter failed",
            )
        )

        self.assertEqual(item.category, FailureCategory.PARSE_CRASH)
        self.assertEqual(state_adapter_item.category, FailureCategory.PARSE_CRASH)
        self.assertEqual(item.reason, "parse or observation adapter error text")

    def test_planner_crash_category_from_planner_error_text(self) -> None:
        item = triage_match_result(
            match_result(
                status=EvaluationStatus.AGENT_ERROR,
                error_text="RuntimeError: run_planner_pipeline commitment failed",
            )
        )
        evaluation_item = triage_match_result(
            match_result(
                status=EvaluationStatus.AGENT_ERROR,
                error_text="RuntimeError: evaluation failed",
            )
        )
        candidate_item = triage_match_result(
            match_result(
                status=EvaluationStatus.AGENT_ERROR,
                error_text="RuntimeError: candidate selection failed",
            )
        )

        self.assertEqual(item.category, FailureCategory.PLANNER_CRASH)
        self.assertEqual(evaluation_item.category, FailureCategory.PLANNER_CRASH)
        self.assertEqual(candidate_item.category, FailureCategory.PLANNER_CRASH)

    def test_action_conversion_category_from_output_error_text(self) -> None:
        item = triage_match_result(
            match_result(
                status=EvaluationStatus.AGENT_ERROR,
                error_text="ValueError: action conversion rejected action row",
            )
        )
        launch_order_item = triage_match_result(
            match_result(
                status=EvaluationStatus.AGENT_ERROR,
                error_text="ValueError: launch order output invalid",
            )
        )

        self.assertEqual(item.category, FailureCategory.ACTION_CONVERSION_CRASH)
        self.assertEqual(
            launch_order_item.category,
            FailureCategory.ACTION_CONVERSION_CRASH,
        )

    def test_timeout_or_budget_category_from_status_metric_and_text(self) -> None:
        status_item = triage_match_result(
            match_result(status=EvaluationStatus.TIMEOUT)
        )
        metric_item = triage_match_result(
            match_result(metrics=MatchMetrics(final_rank=1, timeout_count=1))
        )
        text_item = triage_match_result(
            match_result(
                status=EvaluationStatus.AGENT_ERROR,
                error_text="RuntimeTurnStatus.BUDGET_EXHAUSTED fallback",
            )
        )

        self.assertEqual(
            status_item.category,
            FailureCategory.TIMEOUT_OR_BUDGET_FALLBACK,
        )
        self.assertEqual(
            metric_item.category,
            FailureCategory.TIMEOUT_OR_BUDGET_FALLBACK,
        )
        self.assertEqual(
            text_item.category,
            FailureCategory.TIMEOUT_OR_BUDGET_FALLBACK,
        )

    def test_invalid_or_noop_heavy_category_from_status_metrics_and_noop_count(
        self,
    ) -> None:
        status_item = triage_match_result(
            match_result(status=EvaluationStatus.INVALID_ACTION)
        )
        metric_item = triage_match_result(
            match_result(metrics=MatchMetrics(final_rank=1, invalid_action_count=1))
        )
        noop_item = triage_match_result(
            match_result(
                metrics=MatchMetrics(
                    final_rank=1,
                    turns_survived=100,
                    no_action_count=90,
                )
            )
        )

        self.assertEqual(
            status_item.category,
            FailureCategory.INVALID_OR_NOOP_HEAVY_BEHAVIOR,
        )
        self.assertEqual(
            metric_item.category,
            FailureCategory.INVALID_OR_NOOP_HEAVY_BEHAVIOR,
        )
        self.assertEqual(
            noop_item.category,
            FailureCategory.INVALID_OR_NOOP_HEAVY_BEHAVIOR,
        )

    def test_noop_heavy_reason_uses_runtime_diagnostic_metadata(self) -> None:
        item = triage_match_result(
            match_result(
                metrics=MatchMetrics(
                    final_rank=1,
                    turns_survived=100,
                    no_action_count=90,
                ),
                metadata=(
                    (
                        "runtime_diagnostic_primary_no_action_reason",
                        "strategy_selection_no_action",
                    ),
                    (
                        "runtime_diagnostic_no_action_reasons",
                        "strategy_selection_no_action:90",
                    ),
                ),
            )
        )

        self.assertEqual(
            item.category,
            FailureCategory.INVALID_OR_NOOP_HEAVY_BEHAVIOR,
        )
        self.assertEqual(
            item.reason,
            (
                "invalid action or no-op heavy behavior: "
                "strategy_selection_no_action; "
                "reasons=strategy_selection_no_action:90"
            ),
        )

    def test_normal_loss_and_clean_completed_categories(self) -> None:
        loss_item = triage_match_result(
            match_result(metrics=MatchMetrics(final_rank=2, final_score=0.0))
        )
        clean_item = triage_match_result(
            match_result(metrics=MatchMetrics(final_rank=1, final_score=10.0))
        )

        self.assertEqual(loss_item.category, FailureCategory.NORMAL_LOSS)
        self.assertEqual(loss_item.reason, "completed with losing final rank")
        self.assertEqual(clean_item.category, FailureCategory.CLEAN)
        self.assertEqual(clean_item.reason, "completed without triage issue")

    def test_other_failure_category_for_unclassified_non_completed_result(self) -> None:
        item = triage_match_result(
            match_result(status=EvaluationStatus.IMPORT_ERROR, error_text="bad import")
        )

        self.assertEqual(item.category, FailureCategory.OTHER_FAILURE)
        self.assertEqual(item.reason, "unclassified non-completed result")

    def test_item_fields_capture_match_context_and_paths(self) -> None:
        item = triage_match_result(
            match_result(
                seed=11,
                label="context",
                status=EvaluationStatus.UNKNOWN_ERROR,
                metrics=MatchMetrics(final_rank=3),
                error_text="unknown",
                artifact_path="/tmp/result.json",
                replay_path="/tmp/replay.json",
            ),
            index=5,
        )

        self.assertEqual(item.index, 5)
        self.assertEqual(item.label, "context")
        self.assertEqual(item.seed, 11)
        self.assertEqual(item.player_count, 2)
        self.assertEqual(item.controlled_seat, 0)
        self.assertEqual(item.status, EvaluationStatus.UNKNOWN_ERROR)
        self.assertEqual(item.final_rank, 3)
        self.assertEqual(item.error_text, "unknown")
        self.assertEqual(item.artifact_path, "/tmp/result.json")
        self.assertEqual(item.replay_path, "/tmp/replay.json")

    def test_report_ordering_and_category_summary_are_deterministic(self) -> None:
        results = (
            match_result(seed=1, metrics=MatchMetrics(final_rank=1)),
            match_result(
                seed=2,
                status=EvaluationStatus.AGENT_ERROR,
                error_text="RuntimeError: run_planner_pipeline failed",
            ),
            match_result(seed=3, metrics=MatchMetrics(final_rank=2)),
            match_result(
                seed=4,
                status=EvaluationStatus.AGENT_ERROR,
                error_text="ValueError: action row invalid",
            ),
        )

        report = triage_match_results(results)

        self.assertEqual(
            tuple(item.seed for item in report.items),
            (1, 2, 3, 4),
        )
        self.assertEqual(
            report.category_counts,
            (
                ("planner_crash", 1),
                ("action_conversion_crash", 1),
                ("normal_loss", 1),
                ("clean", 1),
            ),
        )
        self.assertEqual(report.total_results, 4)
        self.assertEqual(report.clean_count, 1)
        self.assertEqual(report.failure_count, 3)

    def test_triage_evaluation_batch_uses_batch_results(self) -> None:
        batch = EvaluationBatchResult(
            results=(
                match_result(seed=1, metrics=MatchMetrics(final_rank=1)),
                match_result(seed=2, metrics=MatchMetrics(final_rank=2)),
            )
        )

        report = triage_evaluation_batch(batch)

        self.assertEqual(report.total_results, 2)
        self.assertEqual(
            tuple(item.category for item in report.items),
            (FailureCategory.CLEAN, FailureCategory.NORMAL_LOSS),
        )

    def test_to_dict_outputs_json_safe_plain_data(self) -> None:
        report = triage_match_results(
            (
                match_result(
                    seed=7,
                    label="json",
                    metrics=MatchMetrics(final_rank=2),
                    artifact_path="/tmp/result.json",
                    replay_path="/tmp/replay.json",
                ),
            )
        )

        data = report.to_dict()
        encoded = json.dumps(data, sort_keys=True)

        self.assertIn('"category": "normal_loss"', encoded)
        self.assertEqual(
            data,
            {
                "items": [
                    {
                        "index": 0,
                        "label": "json",
                        "seed": 7,
                        "player_count": 2,
                        "controlled_seat": 0,
                        "status": "completed",
                        "category": "normal_loss",
                        "reason": "completed with losing final rank",
                        "final_rank": 2,
                        "error_text": None,
                        "artifact_path": "/tmp/result.json",
                        "replay_path": "/tmp/replay.json",
                    }
                ],
                "category_counts": [
                    {"category": "normal_loss", "count": 1},
                ],
                "total_results": 1,
                "clean_count": 0,
                "failure_count": 1,
            },
        )


if __name__ == "__main__":
    unittest.main()
