"""Tests for Evaluation Harness Cycle 14 promotion gate decisions."""

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
    ExperimentManifest,
    ExperimentRunResult,
    MatchMetrics,
    MatchResult,
    PlannerAnalysisPack,
    PromotionGateDecision,
    PromotionGateFailure,
    PromotionThresholds,
    ScoreboardRecord,
    evaluate_promotion_gate,
)


def manifest_with_thresholds(thresholds: PromotionThresholds) -> ExperimentManifest:
    return ExperimentManifest(
        name="promotion-smoke",
        candidate_agent=AgentSpec(
            name="candidate",
            source_kind=AgentSourceKind.MODULAR_AGENT,
            module_path="agents.orbit_wars_agent",
        ),
        scenarios=(),
        version="v1",
        promotion_thresholds=thresholds,
    )


def scoreboard(
    *,
    match_count: int = 4,
    completed_count: int = 4,
    win_count: int = 2,
    loss_count: int = 2,
    error_count: int = 0,
    win_rate: float | None = 0.5,
    error_rate: float | None = 0.0,
    mean_rank: float | None = 1.5,
) -> ScoreboardRecord:
    return ScoreboardRecord(
        agent_name="candidate",
        agent_version="v1",
        commit=None,
        scenario_set="promotion-smoke",
        match_count=match_count,
        completed_count=completed_count,
        win_count=win_count,
        loss_count=loss_count,
        error_count=error_count,
        win_rate=win_rate,
        mean_rank=mean_rank,
        mean_score=1.0,
        error_rate=error_rate,
    )


def run_result(
    *,
    thresholds: PromotionThresholds,
    record: ScoreboardRecord,
) -> ExperimentRunResult:
    return ExperimentRunResult(
        manifest=manifest_with_thresholds(thresholds),
        matches=(),
        batch_result=EvaluationBatchResult(
            results=(
                MatchResult(
                    config=None,  # type: ignore[arg-type]
                    status=EvaluationStatus.COMPLETED,
                    metrics=MatchMetrics(final_rank=1),
                ),
            )
        ),
        scoreboard_record=record,
        analysis_pack=PlannerAnalysisPack(total_results=record.match_count),
        summary_text="experiment summary",
    )


def decision_for(
    thresholds: PromotionThresholds,
    record: ScoreboardRecord,
) -> PromotionGateDecision:
    return evaluate_promotion_gate(run_result(thresholds=thresholds, record=record))


class EvaluationPromotionGateTests(unittest.TestCase):
    def test_promotion_gate_module_imports_and_exports_are_available(self) -> None:
        module = importlib.import_module("ow_eval.promotion_gate")

        self.assertIs(module.PromotionGateFailure, PromotionGateFailure)
        self.assertIs(module.PromotionGateDecision, PromotionGateDecision)
        self.assertIs(module.evaluate_promotion_gate, evaluate_promotion_gate)

    def test_promotion_gate_contracts_are_frozen_slotted_and_validate(self) -> None:
        failure = PromotionGateFailure(
            code="failure",
            message="failed",
            observed=0.0,
            threshold=1.0,
        )
        decision = PromotionGateDecision(
            passed=False,
            failures=(failure,),
            summary_text="summary",
        )

        with self.assertRaises(FrozenInstanceError):
            failure.code = "changed"  # type: ignore[misc]
        with self.assertRaises((AttributeError, TypeError)):
            decision.extra = "nope"  # type: ignore[attr-defined]
        with self.assertRaises(FrozenInstanceError):
            decision.passed = True  # type: ignore[misc]
        with self.assertRaisesRegex(ValueError, "code"):
            PromotionGateFailure(code="", message="failed", observed=0, threshold=1)
        with self.assertRaisesRegex(ValueError, "threshold"):
            PromotionGateFailure(
                code="failure",
                message="failed",
                observed=0,
                threshold=True,  # type: ignore[arg-type]
            )
        with self.assertRaisesRegex(ValueError, "summary_text"):
            PromotionGateDecision(passed=True, summary_text="")

    def test_passes_when_all_configured_thresholds_are_met(self) -> None:
        decision = decision_for(
            PromotionThresholds(
                min_win_rate=0.5,
                max_error_rate=0.0,
                max_mean_rank=1.5,
                min_completed_count=4,
            ),
            scoreboard(),
        )

        self.assertTrue(decision.passed)
        self.assertEqual(decision.failures, ())
        self.assertEqual(
            decision.summary_text,
            (
                "promotion=PASS experiment=promotion-smoke matches=4 "
                "completed=4 win_rate=0.5 error_rate=0 mean_rank=1.5 failures=0"
            ),
        )

    def test_min_win_rate_violation_fails(self) -> None:
        decision = decision_for(
            PromotionThresholds(min_win_rate=0.75),
            scoreboard(win_rate=0.5),
        )

        self.assertFalse(decision.passed)
        self.assertEqual(self.failure_codes(decision), ("min_win_rate_not_met",))
        self.assertEqual(decision.failures[0].observed, 0.5)
        self.assertEqual(decision.failures[0].threshold, 0.75)
        self.assertEqual(decision.failures[0].message, "win_rate 0.5 below 0.75")

    def test_max_error_rate_violation_fails(self) -> None:
        decision = decision_for(
            PromotionThresholds(max_error_rate=0.0),
            scoreboard(error_rate=0.25, error_count=1, completed_count=3),
        )

        self.assertFalse(decision.passed)
        self.assertEqual(self.failure_codes(decision), ("max_error_rate_exceeded",))
        self.assertEqual(decision.failures[0].message, "error_rate 0.25 exceeds 0")

    def test_max_mean_rank_violation_fails(self) -> None:
        decision = decision_for(
            PromotionThresholds(max_mean_rank=1.25),
            scoreboard(mean_rank=1.5),
        )

        self.assertFalse(decision.passed)
        self.assertEqual(self.failure_codes(decision), ("max_mean_rank_exceeded",))
        self.assertEqual(decision.failures[0].message, "mean_rank 1.5 exceeds 1.25")

    def test_min_completed_count_violation_fails(self) -> None:
        decision = decision_for(
            PromotionThresholds(min_completed_count=4),
            scoreboard(completed_count=3),
        )

        self.assertFalse(decision.passed)
        self.assertEqual(
            self.failure_codes(decision),
            ("min_completed_count_not_met",),
        )
        self.assertEqual(decision.failures[0].message, "completed_count 3 below 4")

    def test_unset_thresholds_are_ignored(self) -> None:
        decision = decision_for(
            PromotionThresholds(),
            scoreboard(
                completed_count=0,
                win_rate=None,
                error_rate=None,
                mean_rank=None,
            ),
        )

        self.assertTrue(decision.passed)
        self.assertEqual(decision.failures, ())

    def test_none_rates_fail_when_corresponding_threshold_is_configured(self) -> None:
        decision = decision_for(
            PromotionThresholds(
                min_win_rate=0.1,
                max_error_rate=0.0,
                max_mean_rank=2.0,
            ),
            scoreboard(
                match_count=0,
                completed_count=0,
                win_count=0,
                loss_count=0,
                error_count=0,
                win_rate=None,
                error_rate=None,
                mean_rank=None,
            ),
        )

        self.assertFalse(decision.passed)
        self.assertEqual(
            self.failure_codes(decision),
            (
                "min_win_rate_not_met",
                "max_error_rate_exceeded",
                "max_mean_rank_exceeded",
            ),
        )
        self.assertEqual(decision.failures[0].message, "win_rate none below 0.1")

    def test_multiple_threshold_failures_keep_stable_order(self) -> None:
        decision = decision_for(
            PromotionThresholds(
                min_win_rate=0.8,
                max_error_rate=0.0,
                max_mean_rank=1.0,
                min_completed_count=5,
            ),
            scoreboard(win_rate=0.25, error_rate=0.5, mean_rank=2.0, completed_count=3),
        )

        self.assertEqual(
            self.failure_codes(decision),
            (
                "min_win_rate_not_met",
                "max_error_rate_exceeded",
                "max_mean_rank_exceeded",
                "min_completed_count_not_met",
            ),
        )

    def test_to_dict_output_is_json_safe(self) -> None:
        decision = decision_for(
            PromotionThresholds(min_win_rate=1.0),
            scoreboard(win_rate=0.5),
        )

        encoded = json.dumps(decision.to_dict(), sort_keys=True)
        decoded = json.loads(encoded)

        self.assertEqual(decoded["passed"], False)
        self.assertEqual(decoded["failures"][0]["code"], "min_win_rate_not_met")
        self.assertEqual(decoded["failures"][0]["observed"], 0.5)
        self.assertEqual(decoded["failures"][0]["threshold"], 1.0)
        self.assertIn("summary_text", decoded)

    def test_non_run_result_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "run_result"):
            evaluate_promotion_gate("bad")  # type: ignore[arg-type]

    def failure_codes(self, decision: PromotionGateDecision) -> tuple[str, ...]:
        return tuple(failure.code for failure in decision.failures)


if __name__ == "__main__":
    unittest.main()
