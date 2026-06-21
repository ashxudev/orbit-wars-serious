"""Regression harness tests for compact V0 replay leak fixtures."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from ow_eval.v0_replay_regression import (
    V0ReplayRegressionCaseResult,
    V0ReplayRegressionMetrics,
    V0ReplayRegressionReport,
    default_v0_replay_fixture_dir,
    run_v0_replay_regression,
)


EXPECTED_FIXTURE_NAMES = (
    "four_p_no_action_80761836_t100_p2.json",
    "four_p_no_action_80766287_t000_p2.json",
    "two_p_capture_hold_80763852_t125_p1.json",
    "two_p_capture_hold_80763852_t131_p1.json",
    "two_p_idle_80768833_t000_p1.json",
    "two_p_pressure_80756891_t060_p0.json",
    "two_p_pressure_80760443_t100_p0.json",
)


class V0ReplayRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = run_v0_replay_regression()

    def test_report_covers_all_committed_v0_leak_fixtures(self) -> None:
        report = self.report

        self.assertIsInstance(report, V0ReplayRegressionReport)
        self.assertEqual(
            tuple(case.fixture_name for case in report.case_results),
            EXPECTED_FIXTURE_NAMES,
        )
        self.assertEqual(report.metrics.total_cases, len(EXPECTED_FIXTURE_NAMES))
        self.assertEqual(Path(report.fixture_dir), default_v0_replay_fixture_dir())

    def test_metrics_classify_plugged_leaks_and_budget_guard_separately(self) -> None:
        report = self.report
        metrics = report.metrics

        self.assertIsInstance(metrics, V0ReplayRegressionMetrics)
        self.assertEqual(metrics.total_cases, 7)
        self.assertEqual(metrics.budgetless_action_count, 7)
        self.assertEqual(metrics.budgetless_action_rate, 1.0)
        self.assertEqual(metrics.budget_guarded_no_action_count, 1)
        self.assertEqual(metrics.unresolved_planner_no_action_count, 0)
        self.assertEqual(metrics.risky_thin_capture_proxy_count, 0)
        self.assertEqual(metrics.pressure_retention_case_count, 4)
        self.assertEqual(metrics.pressure_retention_budgetless_action_count, 4)
        self.assertEqual(metrics.pressure_retention_budgetless_action_rate, 1.0)
        self.assertEqual(metrics.conservative_pressure_retention_action_count, 4)
        self.assertEqual(metrics.live_max_no_action_streak, 1)
        self.assertEqual(
            report.summary_text,
            (
                "v0_replay_regression cases=7 live_actions=6 "
                "live_no_actions=1 budget_guarded=1 budgetless_actions=7 "
                "pressure_actions=4 risky_thin_captures=0 "
                "unresolved_planner_no_actions=0"
            ),
        )

    def test_four_player_no_action_fixtures_emit_actions(self) -> None:
        report = self.report
        four_player_cases = tuple(
            case
            for case in report.case_results
            if case.leak_class == "four_player_no_action_candidate_starvation"
        )

        self.assertEqual(len(four_player_cases), 2)
        for case in four_player_cases:
            with self.subTest(case=case.case_id):
                self.assertIsInstance(case, V0ReplayRegressionCaseResult)
                self.assertGreater(case.budgetless_action_count, 0)
                self.assertGreater(case.live_action_count, 0)
                self.assertFalse(case.risky_thin_capture_proxy)

    def test_pressure_and_capture_hold_cases_are_conservative_when_budget_allows(
        self,
    ) -> None:
        report = self.report
        pressure_cases = tuple(
            case for case in report.case_results if case.pressure_or_retention_case
        )

        self.assertEqual(len(pressure_cases), 4)
        for case in pressure_cases:
            with self.subTest(case=case.case_id):
                self.assertGreater(case.budgetless_action_count, 0)
                self.assertEqual(case.selected_commitment_type, "reserve_preserving")
                self.assertTrue(case.conservative_budgetless_action)
                self.assertFalse(case.risky_thin_capture_proxy)

    def test_negative_overage_fixture_is_budget_blocked_not_planner_unresolved(
        self,
    ) -> None:
        report = self.report
        budget_blocked = tuple(
            case for case in report.case_results if case.budget_guarded_no_action
        )

        self.assertEqual(len(budget_blocked), 1)
        case = budget_blocked[0]
        self.assertEqual(case.fixture_name, "two_p_pressure_80760443_t100_p0.json")
        self.assertEqual(case.live_no_action_reason, "budget_guard_budget_exhausted")
        self.assertEqual(case.runtime_mode, "bounded")
        self.assertGreater(case.budgetless_action_count, 0)
        self.assertEqual(case.selected_commitment_type, "reserve_preserving")

    def test_to_dict_is_json_safe_and_stable(self) -> None:
        report = self.report

        data = report.to_dict()
        encoded = json.dumps(data, sort_keys=True)
        self.assertEqual(json.loads(encoded), data)
        self.assertEqual(data["summary_text"], report.summary_text)
        self.assertEqual(data["metrics"], report.metrics.to_dict())
        self.assertEqual(
            [case["fixture_name"] for case in data["case_results"]],
            list(EXPECTED_FIXTURE_NAMES),
        )

    def test_empty_fixture_directory_is_rejected(self) -> None:
        empty_dir = Path(self.id())

        with self.assertRaisesRegex(ValueError, "no V0 replay leak fixtures found"):
            run_v0_replay_regression(empty_dir)


if __name__ == "__main__":
    unittest.main()
