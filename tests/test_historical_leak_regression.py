"""Regression harness tests for compact historical gauntlet leak fixtures."""

from __future__ import annotations

import json
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

import ow_eval
from ow_eval.historical_leak_regression import (
    HistoricalLeakRegressionCaseResult,
    HistoricalLeakRegressionMetrics,
    HistoricalLeakRegressionReport,
    default_historical_leak_fixture_dir,
    run_historical_leak_regression,
)


EXPECTED_FIXTURE_NAMES = (
    "four_p_mixed_style_budget_pressure_t220_p2.json",
    "four_p_ow2_reference_strategy_pressure_t189_p0.json",
    "four_p_top_score_plateau_t080_p3.json",
    "two_p_collapse_claude_v31_t002_p1.json",
    "two_p_collapse_claude_v9_t001_p1.json",
    "two_p_control_pressure_ow2_main_t002_p0.json",
)


class HistoricalLeakRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = run_historical_leak_regression()

    def test_report_covers_all_committed_historical_leak_fixtures(self) -> None:
        report = self.report

        self.assertIsInstance(report, HistoricalLeakRegressionReport)
        self.assertEqual(
            tuple(case.fixture_name for case in report.case_results),
            EXPECTED_FIXTURE_NAMES,
        )
        self.assertEqual(report.metrics.total_cases, len(EXPECTED_FIXTURE_NAMES))
        self.assertEqual(
            Path(report.fixture_dir),
            default_historical_leak_fixture_dir(),
        )

    def test_metrics_classify_post_cycle_four_status(self) -> None:
        metrics = self.report.metrics

        self.assertIsInstance(metrics, HistoricalLeakRegressionMetrics)
        self.assertEqual(metrics.total_cases, 6)
        self.assertEqual(metrics.action_emitting_count, 5)
        self.assertEqual(metrics.action_emitting_rate, 0.833333)
        self.assertEqual(metrics.source_less_no_owned_planets_count, 1)
        self.assertEqual(metrics.budget_guarded_no_action_count, 0)
        self.assertEqual(metrics.unresolved_no_candidates_generated_count, 0)
        self.assertEqual(metrics.unresolved_strategy_selection_no_action_count, 0)
        self.assertEqual(metrics.other_no_action_count, 0)
        self.assertEqual(metrics.unresolved_deterministic_leak_count, 0)
        self.assertEqual(
            self.report.summary_text,
            (
                "historical_leak_regression cases=6 action_emitting=5 "
                "action_rate=0.833333 source_less_no_owned=1 "
                "budget_guarded=0 unresolved_no_candidates=0 "
                "unresolved_strategy_no_action=0 other_no_action=0 "
                "unresolved_deterministic_leaks=0"
            ),
        )

    def test_case_classifications_are_precise(self) -> None:
        action_cases = tuple(
            case
            for case in self.report.case_results
            if case.classification == "action_emitted"
        )
        source_less_cases = tuple(
            case
            for case in self.report.case_results
            if case.classification == "source_less_no_owned_planets"
        )

        self.assertEqual(len(action_cases), 5)
        for case in action_cases:
            with self.subTest(case=case.fixture_name):
                self.assertGreater(case.action_count, 0)
                self.assertEqual(case.no_action_reason, "actions_emitted")
                self.assertFalse(case.unresolved_deterministic_leak)

        self.assertEqual(len(source_less_cases), 1)
        source_less = source_less_cases[0]
        self.assertEqual(
            source_less.fixture_name,
            "four_p_mixed_style_budget_pressure_t220_p2.json",
        )
        self.assertEqual(source_less.action_count, 0)
        self.assertEqual(source_less.no_action_reason, "no_owned_planets")
        self.assertEqual(source_less.candidate_count, 0)
        self.assertFalse(source_less.unresolved_deterministic_leak)

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

    def test_result_objects_are_frozen_and_slotted(self) -> None:
        case = self.report.case_results[0]

        self.assertIsInstance(case, HistoricalLeakRegressionCaseResult)
        self.assertTrue(hasattr(HistoricalLeakRegressionCaseResult, "__slots__"))
        self.assertTrue(hasattr(HistoricalLeakRegressionMetrics, "__slots__"))
        self.assertTrue(hasattr(HistoricalLeakRegressionReport, "__slots__"))
        with self.assertRaises(FrozenInstanceError):
            case.action_count = 0  # type: ignore[misc]

    def test_empty_fixture_directory_is_rejected(self) -> None:
        empty_dir = Path(self.id())

        with self.assertRaisesRegex(
            ValueError,
            "no historical gauntlet leak fixtures found",
        ):
            run_historical_leak_regression(empty_dir)

    def test_public_exports_are_available_from_ow_eval(self) -> None:
        self.assertIs(
            ow_eval.HistoricalLeakRegressionCaseResult,
            HistoricalLeakRegressionCaseResult,
        )
        self.assertIs(
            ow_eval.HistoricalLeakRegressionMetrics,
            HistoricalLeakRegressionMetrics,
        )
        self.assertIs(
            ow_eval.HistoricalLeakRegressionReport,
            HistoricalLeakRegressionReport,
        )
        self.assertIs(
            ow_eval.default_historical_leak_fixture_dir,
            default_historical_leak_fixture_dir,
        )
        self.assertIs(
            ow_eval.run_historical_leak_regression,
            run_historical_leak_regression,
        )


if __name__ == "__main__":
    unittest.main()
