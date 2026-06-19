"""Tests for Evaluation Harness Cycle 10 quick regression gate."""

from __future__ import annotations

import importlib
import io
import json
import unittest
from contextlib import redirect_stdout
from dataclasses import FrozenInstanceError
from unittest.mock import patch

from ow_eval import (
    AgentSourceKind,
    AgentSpec,
    EvaluationBatchResult,
    EvaluationStatus,
    MatchConfig,
    MatchMetrics,
    MatchResult,
    OpponentSpec,
    PlayerCount,
    RegressionGateConfig,
    RegressionGateFailure,
    RegressionGateResult,
    SubmissionParityComparison,
    SubmissionParityResult,
    builtin_baseline_spec,
    BaselineName,
    run_regression_gate,
)


def gate_match_config(seed: int = 7, label: str = "gate") -> MatchConfig:
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
                builtin_baseline_spec(BaselineName.NOOP, name="opponent-noop")
            ),
        ),
        label=label,
    )


def match_result(
    match: MatchConfig | None = None,
    *,
    status: EvaluationStatus = EvaluationStatus.COMPLETED,
    final_rank: int | None = 1,
    final_score: float | None = 10.0,
    no_action_count: int | None = None,
    turns_survived: int | None = None,
    error_text: str | None = None,
    metadata: tuple[tuple[str, str], ...] = (),
) -> MatchResult:
    return MatchResult(
        config=gate_match_config() if match is None else match,
        status=status,
        metrics=MatchMetrics(
            final_rank=final_rank,
            final_score=final_score,
            no_action_count=no_action_count,
            turns_survived=turns_survived,
        ),
        error_text=error_text,
        metadata=metadata,
    )


def batch_result(*results: MatchResult) -> EvaluationBatchResult:
    return EvaluationBatchResult(results=tuple(results))


def parity_result(
    matches: tuple[MatchConfig, ...],
    *,
    passed: bool = True,
    modular_status: EvaluationStatus = EvaluationStatus.COMPLETED,
    submission_status: EvaluationStatus = EvaluationStatus.COMPLETED,
    modular_no_action_count: int | None = None,
    submission_no_action_count: int | None = None,
    turns_survived: int | None = None,
    runtime_metadata: tuple[tuple[str, str], ...] = (),
) -> SubmissionParityResult:
    modular_results = tuple(
        match_result(
            match,
            status=modular_status,
            no_action_count=modular_no_action_count,
            turns_survived=turns_survived,
            metadata=runtime_metadata,
        )
        for match in matches
    )
    submission_results = tuple(
        match_result(
            match,
            status=submission_status,
            no_action_count=submission_no_action_count,
            turns_survived=turns_survived,
            metadata=runtime_metadata,
        )
        for match in matches
    )
    comparisons = tuple(
        SubmissionParityComparison(
            index=index,
            modular_result=modular_result,
            submission_result=submission_result,
            status_matches=modular_status is submission_status,
            metrics_match=passed,
            matched=passed,
            mismatch_reasons=() if passed else ("final_rank differs",),
        )
        for index, (modular_result, submission_result) in enumerate(
            zip(modular_results, submission_results)
        )
    )
    mismatch_count = sum(1 for comparison in comparisons if not comparison.matched)
    return SubmissionParityResult(
        comparisons=comparisons,
        modular_batch=batch_result(*modular_results),
        submission_batch=batch_result(*submission_results),
        passed=passed,
        mismatch_count=mismatch_count,
    )


class RegressionGateTests(unittest.TestCase):
    def test_regression_gate_module_imports_and_exports_are_available(self) -> None:
        module = importlib.import_module("ow_eval.regression_gate")

        self.assertIs(module.RegressionGateConfig, RegressionGateConfig)
        self.assertIs(module.RegressionGateFailure, RegressionGateFailure)
        self.assertIs(module.RegressionGateResult, RegressionGateResult)
        self.assertIs(module.run_regression_gate, run_regression_gate)

    def test_gate_contracts_are_frozen_slotted_and_validate(self) -> None:
        config = RegressionGateConfig(matches=(gate_match_config(),))
        failure = RegressionGateFailure(code="failure", message="failed")
        result = RegressionGateResult(passed=False, failures=(failure,))

        with self.assertRaises(FrozenInstanceError):
            config.max_error_rate = 0.5  # type: ignore[misc]
        with self.assertRaises((AttributeError, TypeError)):
            failure.extra = "nope"  # type: ignore[attr-defined]
        with self.assertRaises(FrozenInstanceError):
            result.passed = True  # type: ignore[misc]
        with self.assertRaisesRegex(ValueError, "matches must be a tuple"):
            RegressionGateConfig(matches=[gate_match_config()])  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "max_error_rate"):
            RegressionGateConfig(max_error_rate=1.5)
        with self.assertRaisesRegex(ValueError, "code"):
            RegressionGateFailure(code="", message="failed")

    def test_default_config_uses_small_deterministic_scenario_set(self) -> None:
        config = RegressionGateConfig()

        self.assertEqual(tuple(match.seed for match in config.matches), (7, 8))
        self.assertEqual(
            tuple(match.label for match in config.matches),
            ("quick-gate-7", "quick-gate-8"),
        )
        self.assertEqual(config.max_error_rate, 0.0)
        self.assertEqual(config.max_mean_rank, 2.0)
        self.assertEqual(config.min_win_rate, 0.0)

    def test_passing_gate_returns_scoreboard_triage_and_parity(self) -> None:
        matches = (gate_match_config(7), gate_match_config(8))
        candidate_batch = batch_result(
            match_result(matches[0], final_rank=1, final_score=10.0),
            match_result(matches[1], final_rank=2, final_score=2.0),
        )
        parity = parity_result(matches)
        config = RegressionGateConfig(
            matches=matches,
            agent_name="agent",
            scenario_set="unit",
            metadata=(("suite", "gate"),),
        )

        with patch(
            "ow_eval.regression_gate.run_evaluation_batch",
            return_value=candidate_batch,
        ) as batch_mock:
            with patch(
                "ow_eval.regression_gate.run_submission_parity_check",
                return_value=parity,
            ) as parity_mock:
                result = run_regression_gate(config)

        self.assertTrue(result.passed)
        self.assertEqual(result.failures, ())
        self.assertIs(result.parity_result, parity)
        self.assertIsNotNone(result.triage_report)
        self.assertIsNotNone(result.scoreboard_record)
        assert result.scoreboard_record is not None
        self.assertEqual(result.scoreboard_record.agent_name, "agent")
        self.assertEqual(result.scoreboard_record.metadata, (("suite", "gate"),))
        self.assertIn("gate=PASS", result.summary_text)
        batch_mock.assert_called_once()
        parity_config = parity_mock.call_args.args[0]
        self.assertIs(parity_config.submission_path, config.submission_path)
        self.assertEqual(parity_config.matches, matches)

    def test_parity_mismatch_fails_gate(self) -> None:
        matches = (gate_match_config(),)
        result = self.run_mocked_gate(
            matches,
            candidate_batch=batch_result(match_result(matches[0])),
            parity=parity_result(matches, passed=False),
        )

        self.assertFalse(result.passed)
        self.assertIn("parity_mismatch", self.failure_codes(result))

    def test_candidate_error_statuses_fail_gate(self) -> None:
        failing_statuses = (
            EvaluationStatus.IMPORT_ERROR,
            EvaluationStatus.AGENT_ERROR,
            EvaluationStatus.ENV_ERROR,
            EvaluationStatus.TIMEOUT,
            EvaluationStatus.INVALID_ACTION,
            EvaluationStatus.UNKNOWN_ERROR,
        )
        for status in failing_statuses:
            with self.subTest(status=status):
                matches = (gate_match_config(),)
                result = self.run_mocked_gate(
                    matches,
                    candidate_batch=batch_result(
                        match_result(
                            matches[0],
                            status=status,
                            final_rank=None,
                            final_score=None,
                            error_text=f"{status.value} failure",
                        )
                    ),
                    parity=parity_result(matches),
                )

                self.assertFalse(result.passed)
                self.assertIn(
                    "candidate_match_status_failure",
                    self.failure_codes(result),
                )

    def test_parity_batch_error_statuses_fail_gate(self) -> None:
        matches = (gate_match_config(),)
        result = self.run_mocked_gate(
            matches,
            candidate_batch=batch_result(match_result(matches[0])),
            parity=parity_result(
                matches,
                passed=False,
                submission_status=EvaluationStatus.IMPORT_ERROR,
            ),
        )

        self.assertFalse(result.passed)
        self.assertIn("submission_match_status_failure", self.failure_codes(result))

    def test_triage_failure_category_fails_gate(self) -> None:
        matches = (gate_match_config(),)
        result = self.run_mocked_gate(
            matches,
            candidate_batch=batch_result(
                match_result(
                    matches[0],
                    no_action_count=90,
                    turns_survived=100,
                )
            ),
            parity=parity_result(matches),
        )

        self.assertFalse(result.passed)
        self.assertIn("triage_failure_category", self.failure_codes(result))
        self.assertEqual(
            result.failures[-1].category,
            "invalid_or_noop_heavy_behavior",
        )

    def test_actual_agent_parity_triage_failures_fail_gate(self) -> None:
        matches = (gate_match_config(),)
        result = self.run_mocked_gate(
            matches,
            candidate_batch=batch_result(match_result(matches[0])),
            parity=parity_result(
                matches,
                modular_no_action_count=90,
                submission_no_action_count=90,
                turns_survived=100,
                runtime_metadata=(
                    (
                        "runtime_diagnostic_primary_no_action_reason",
                        "strategy_selection_no_action",
                    ),
                    (
                        "runtime_diagnostic_no_action_reasons",
                        "strategy_selection_no_action:90",
                    ),
                ),
            ),
        )

        self.assertFalse(result.passed)
        self.assertIn("modular_triage_failure_category", self.failure_codes(result))
        self.assertIn("submission_triage_failure_category", self.failure_codes(result))
        self.assertEqual(
            tuple(
                failure.category
                for failure in result.failures
                if failure.code.endswith("_triage_failure_category")
            ),
            (
                "invalid_or_noop_heavy_behavior",
                "invalid_or_noop_heavy_behavior",
            ),
        )
        self.assertEqual(
            tuple(
                failure.message
                for failure in result.failures
                if failure.code.endswith("_triage_failure_category")
            ),
            (
                "modular triage category invalid_or_noop_heavy_behavior count 1; "
                "details=0:invalid action or no-op heavy behavior: "
                "strategy_selection_no_action; "
                "reasons=strategy_selection_no_action:90",
                "submission triage category invalid_or_noop_heavy_behavior count 1; "
                "details=0:invalid action or no-op heavy behavior: "
                "strategy_selection_no_action; "
                "reasons=strategy_selection_no_action:90",
            ),
        )
        self.assertNotIn(
            "budget_guard_budget_exhausted",
            "\n".join(failure.message for failure in result.failures),
        )

    def test_threshold_violations_fail_gate(self) -> None:
        matches = (gate_match_config(7), gate_match_config(8))
        candidate_batch = batch_result(
            match_result(matches[0], final_rank=2, final_score=2.0),
            match_result(matches[1], final_rank=2, final_score=4.0),
        )
        result = self.run_mocked_gate(
            matches,
            candidate_batch=candidate_batch,
            parity=parity_result(matches),
            config=RegressionGateConfig(
                matches=matches,
                max_mean_rank=1.0,
                min_win_rate=1.0,
            ),
        )

        self.assertFalse(result.passed)
        self.assertIn("max_mean_rank_exceeded", self.failure_codes(result))
        self.assertIn("min_win_rate_not_met", self.failure_codes(result))

    def test_error_rate_threshold_violation_is_reported(self) -> None:
        matches = (gate_match_config(),)
        result = self.run_mocked_gate(
            matches,
            candidate_batch=batch_result(
                match_result(
                    matches[0],
                    status=EvaluationStatus.IMPORT_ERROR,
                    final_rank=None,
                    final_score=None,
                    error_text="ImportError: missing",
                )
            ),
            parity=parity_result(matches),
        )

        self.assertIn("max_error_rate_exceeded", self.failure_codes(result))

    def test_empty_scenario_set_is_deterministic_failure(self) -> None:
        result = run_regression_gate(RegressionGateConfig(matches=()))

        self.assertFalse(result.passed)
        self.assertEqual(result.scoreboard_record, None)
        self.assertEqual(result.triage_report, None)
        self.assertEqual(self.failure_codes(result), ("empty_scenario_set",))
        self.assertIn("gate=FAIL", result.summary_text)

    def test_unexpected_execution_exception_is_structured_failure(self) -> None:
        with patch(
            "ow_eval.regression_gate.run_evaluation_batch",
            side_effect=RuntimeError("boom"),
        ):
            result = run_regression_gate(
                RegressionGateConfig(matches=(gate_match_config(),))
            )

        self.assertFalse(result.passed)
        self.assertEqual(self.failure_codes(result), ("gate_execution_error",))
        self.assertEqual(result.failures[0].message, "RuntimeError: boom")

    def test_result_to_dict_is_json_safe(self) -> None:
        result = RegressionGateResult(
            passed=False,
            failures=(
                RegressionGateFailure(
                    code="failure",
                    message="failed",
                    match_index=2,
                    status="agent_error",
                    category="planner_crash",
                ),
            ),
            summary_text="gate=FAIL",
        )

        encoded = json.dumps(result.to_dict(), sort_keys=True)
        decoded = json.loads(encoded)

        self.assertEqual(decoded["passed"], False)
        self.assertEqual(decoded["failures"][0]["code"], "failure")
        self.assertEqual(decoded["summary_text"], "gate=FAIL")

    def test_script_main_returns_zero_for_passing_gate(self) -> None:
        script = importlib.import_module("scripts.evaluation_gate")
        gate_result = RegressionGateResult(passed=True, summary_text="gate=PASS")
        output = io.StringIO()

        with patch("scripts.evaluation_gate.run_regression_gate", return_value=gate_result):
            with redirect_stdout(output):
                code = script.main(())

        self.assertEqual(code, 0)
        self.assertEqual(output.getvalue(), "gate=PASS\n")

    def test_script_main_returns_nonzero_for_failed_gate(self) -> None:
        script = importlib.import_module("scripts.evaluation_gate")
        gate_result = RegressionGateResult(
            passed=False,
            failures=(
                RegressionGateFailure(code="failure", message="failed"),
            ),
            summary_text="gate=FAIL",
        )
        output = io.StringIO()

        with patch("scripts.evaluation_gate.run_regression_gate", return_value=gate_result):
            with redirect_stdout(output):
                code = script.main(())

        self.assertEqual(code, 1)
        self.assertEqual(
            output.getvalue(),
            "gate=FAIL\nfailure: failed\n",
        )

    def run_mocked_gate(
        self,
        matches: tuple[MatchConfig, ...],
        *,
        candidate_batch: EvaluationBatchResult,
        parity: SubmissionParityResult,
        config: RegressionGateConfig | None = None,
    ) -> RegressionGateResult:
        gate_config = config or RegressionGateConfig(matches=matches)
        with patch(
            "ow_eval.regression_gate.run_evaluation_batch",
            return_value=candidate_batch,
        ):
            with patch(
                "ow_eval.regression_gate.run_submission_parity_check",
                return_value=parity,
            ):
                return run_regression_gate(gate_config)

    def failure_codes(self, result: RegressionGateResult) -> tuple[str, ...]:
        return tuple(failure.code for failure in result.failures)


if __name__ == "__main__":
    unittest.main()
