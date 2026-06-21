"""Regression harness tests for compact V1 replay leak fixtures."""

from __future__ import annotations

import json
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

import ow_eval
from ow_eval.v1_replay_regression import (
    V1ReplayRegressionCaseResult,
    V1ReplayRegressionMetrics,
    V1ReplayRegressionReport,
    default_v1_replay_fixture_dir,
    run_v1_replay_regression,
)


EXPECTED_FIXTURE_NAMES = (
    "four_p_plateau_80981260_t060_p2.json",
    "four_p_plateau_80982912_t250_p0.json",
    "four_p_plateau_80984201_t240_p0.json",
    "four_p_thin_capture_recaptured_80979440_t054_p0.json",
    "two_p_enemy_denial_absent_80989880_t200_p0.json",
    "two_p_own_transfer_spam_80986331_t161_p1.json",
    "two_p_own_transfer_spam_80991772_t160_p0.json",
    "two_p_production_retention_80979989_t084_p1.json",
    "two_p_production_retention_80987824_t156_p1.json",
    "two_p_production_retention_80999800_t150_p0.json",
)


class V1ReplayRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = run_v1_replay_regression()

    def test_report_covers_all_committed_v1_leak_fixtures(self) -> None:
        report = self.report

        self.assertIsInstance(report, V1ReplayRegressionReport)
        self.assertEqual(
            tuple(case.fixture_name for case in report.case_results),
            EXPECTED_FIXTURE_NAMES,
        )
        self.assertEqual(report.metrics.total_cases, len(EXPECTED_FIXTURE_NAMES))
        self.assertEqual(Path(report.fixture_dir), default_v1_replay_fixture_dir())

    def test_metrics_classify_v1_leaks_and_caveats(self) -> None:
        metrics = self.report.metrics

        self.assertIsInstance(metrics, V1ReplayRegressionMetrics)
        self.assertEqual(metrics.total_cases, 10)
        self.assertEqual(metrics.live_action_count, 9)
        self.assertEqual(metrics.live_no_action_count, 1)
        self.assertEqual(metrics.live_action_rate, 0.9)
        self.assertEqual(metrics.unresolved_planner_no_action_count, 0)
        self.assertEqual(metrics.reduced_active_owner_caveat_count, 1)
        self.assertEqual(metrics.owned_production_pressure_coverage_count, 8)
        self.assertEqual(metrics.own_transfer_spam_coverage_count, 3)
        self.assertEqual(metrics.enemy_denial_safety_blocked_count, 1)
        self.assertEqual(metrics.four_player_plateau_action_count, 3)
        self.assertEqual(metrics.four_player_plateau_no_action_count, 1)
        self.assertEqual(metrics.rank_aware_continuation_count, 2)
        self.assertEqual(metrics.thin_capture_risk_count, 2)
        self.assertEqual(metrics.budget_guarded_no_action_count, 0)
        self.assertEqual(
            self.report.summary_text,
            (
                "v1_replay_regression cases=10 live_actions=9 live_no_actions=1 "
                "unresolved_planner_no_actions=0 reduced_active_owner_caveats=1 "
                "owned_pressure=8 own_transfer_spam=3 "
                "enemy_denial_safety_blocked=1 four_player_plateau_actions=3 "
                "four_player_plateau_no_actions=1 rank_aware_continuations=2 "
                "thin_capture_risks=2"
            ),
        )

    def test_reduced_active_owner_case_is_not_unresolved_planner_leak(self) -> None:
        case = self._case("four_p_plateau_80984201_t240_p0.json")

        self.assertEqual(case.action_count, 0)
        self.assertEqual(case.no_action_reason, "strategy_selection_no_action")
        self.assertTrue(case.reduced_active_owner_caveat)
        self.assertFalse(case.unresolved_planner_no_action)
        self.assertIn(
            "reduced_active_owner_live_2p_dispatch_caveat",
            case.leak_labels,
        )

    def test_fixed_four_player_plateau_cases_are_action_emitting(self) -> None:
        case_81260 = self._case("four_p_plateau_80981260_t060_p2.json")
        case_82912 = self._case("four_p_plateau_80982912_t250_p0.json")

        self.assertGreater(case_81260.action_count, 0)
        self.assertTrue(case_81260.four_player_action_emitting_plateau)
        self.assertGreater(case_82912.action_count, 0)
        self.assertTrue(case_82912.rank_aware_continuation)
        self.assertIn("rank_aware_continuation", case_82912.leak_labels)

    def test_enemy_denial_and_thin_capture_metrics_are_case_level_flags(self) -> None:
        denial = self._case("two_p_enemy_denial_absent_80989880_t200_p0.json")
        thin_capture = self._case("four_p_thin_capture_recaptured_80979440_t054_p0.json")

        self.assertTrue(denial.high_value_enemy_denial)
        self.assertTrue(denial.enemy_denial_safety_blocked)
        self.assertIn("enemy_denial_safety_blocked", denial.leak_labels)
        self.assertTrue(thin_capture.thin_capture_risk)
        self.assertTrue(thin_capture.rank_aware_continuation)
        self.assertEqual(thin_capture.selected_commitment_type, "reserve_preserving")

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

        self.assertIsInstance(case, V1ReplayRegressionCaseResult)
        self.assertTrue(hasattr(V1ReplayRegressionCaseResult, "__slots__"))
        self.assertTrue(hasattr(V1ReplayRegressionMetrics, "__slots__"))
        self.assertTrue(hasattr(V1ReplayRegressionReport, "__slots__"))
        with self.assertRaises(FrozenInstanceError):
            case.action_count = 0  # type: ignore[misc]

    def test_empty_fixture_directory_is_rejected(self) -> None:
        empty_dir = Path(self.id())

        with self.assertRaisesRegex(ValueError, "no V1 replay leak fixtures found"):
            run_v1_replay_regression(empty_dir)

    def test_public_exports_are_available_from_ow_eval(self) -> None:
        self.assertIs(ow_eval.V1ReplayRegressionCaseResult, V1ReplayRegressionCaseResult)
        self.assertIs(ow_eval.V1ReplayRegressionMetrics, V1ReplayRegressionMetrics)
        self.assertIs(ow_eval.V1ReplayRegressionReport, V1ReplayRegressionReport)
        self.assertIs(ow_eval.default_v1_replay_fixture_dir, default_v1_replay_fixture_dir)
        self.assertIs(ow_eval.run_v1_replay_regression, run_v1_replay_regression)

    def _case(self, fixture_name: str) -> V1ReplayRegressionCaseResult:
        for case in self.report.case_results:
            if case.fixture_name == fixture_name:
                return case
        raise AssertionError(f"missing case {fixture_name}")


if __name__ == "__main__":
    unittest.main()
