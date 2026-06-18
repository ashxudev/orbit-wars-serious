"""Tests for Evaluation Harness Cycle 19 submission preflight."""

from __future__ import annotations

import contextlib
import importlib
import io
import json
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch

from ow_eval import (
    EvaluationBatchResult,
    ExperimentSuiteResult,
    RegressionGateFailure,
    RegressionGateResult,
    SubmissionParityResult,
    SubmissionPreflightCheck,
    SubmissionPreflightResult,
    default_manifest_paths,
    run_submission_preflight,
    run_submission_preflight_main,
)


def fake_write_submission(path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("def agent(observation, configuration=None):\n    return []\n", encoding="utf-8")
    return output_path


def parity_result(*, passed: bool = True, mismatch_count: int = 0) -> SubmissionParityResult:
    return SubmissionParityResult(
        comparisons=(),
        modular_batch=EvaluationBatchResult(),
        submission_batch=EvaluationBatchResult(),
        passed=passed,
        mismatch_count=mismatch_count,
    )


def regression_result(*, passed: bool = True) -> RegressionGateResult:
    failures = ()
    if not passed:
        failures = (
            RegressionGateFailure(
                code="parity_mismatch",
                message="generated submission parity failed",
            ),
        )
    return RegressionGateResult(
        passed=passed,
        failures=failures,
        summary_text=f"gate={'PASS' if passed else 'FAIL'}",
    )


def suite_result(*, exit_code: int = 0) -> ExperimentSuiteResult:
    return ExperimentSuiteResult(
        manifest_paths=tuple(str(path) for path in default_manifest_paths()),
        results=(),
        exit_code=exit_code,
        summary_text=(
            f"experiment_suite={'PASS' if exit_code == 0 else 'FAIL'} "
            f"total=3 passed={3 if exit_code == 0 else 2} "
            f"failed={0 if exit_code == 0 else 1} "
            f"failed_manifests={'none' if exit_code == 0 else 'promotion-smoke'} "
            f"exit_code={exit_code}"
        ),
    )


class EvaluationSubmissionPreflightTests(unittest.TestCase):
    def test_preflight_module_imports_and_exports_are_available(self) -> None:
        module = importlib.import_module("ow_eval.submission_preflight")

        self.assertIs(module.SubmissionPreflightCheck, SubmissionPreflightCheck)
        self.assertIs(module.SubmissionPreflightResult, SubmissionPreflightResult)
        self.assertIs(module.run_submission_preflight, run_submission_preflight)
        self.assertIs(module.main, run_submission_preflight_main)

    def test_preflight_contracts_are_frozen_slotted_and_validate(self) -> None:
        check = SubmissionPreflightCheck(
            name="check",
            passed=True,
            exit_code=0,
            summary_text="summary",
        )
        result = SubmissionPreflightResult(
            checks=(check,),
            passed=True,
            exit_code=0,
            summary_text="summary",
        )

        with self.assertRaises(FrozenInstanceError):
            check.name = "changed"  # type: ignore[misc]
        with self.assertRaises((AttributeError, TypeError)):
            result.extra = "nope"  # type: ignore[attr-defined]
        with self.assertRaises(FrozenInstanceError):
            result.passed = False  # type: ignore[misc]
        with self.assertRaisesRegex(ValueError, "name"):
            SubmissionPreflightCheck(name="", passed=True, exit_code=0, summary_text="s")
        with self.assertRaisesRegex(ValueError, "checks"):
            SubmissionPreflightResult(
                checks=("bad",),  # type: ignore[arg-type]
                passed=True,
                exit_code=0,
                summary_text="summary",
            )

    def test_all_pass_preflight_runs_checks_in_stable_order(self) -> None:
        with patch(
            "ow_eval.submission_preflight.write_submission",
            side_effect=fake_write_submission,
        ) as build_mock, patch(
            "ow_eval.submission_preflight.run_submission_parity_check",
            return_value=parity_result(),
        ) as parity_mock, patch(
            "ow_eval.submission_preflight.run_regression_gate",
            return_value=regression_result(),
        ) as gate_mock, patch(
            "ow_eval.submission_preflight.run_evaluation_suite",
            return_value=suite_result(),
        ) as suite_mock:
            result = run_submission_preflight()

        self.assertTrue(result.passed)
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(
            tuple(check.name for check in result.checks),
            (
                "submission_build",
                "submission_parity",
                "regression_gate",
                "experiment_suite",
            ),
        )
        self.assertTrue(all(check.passed for check in result.checks))
        self.assertEqual(
            result.summary_text,
            (
                "submission_preflight=PASS total=4 passed=4 failed=0 "
                "failed_checks=none exit_code=0"
            ),
        )
        build_mock.assert_called_once()
        self.assertEqual(parity_mock.call_count, 1)
        parity_config = parity_mock.call_args.args[0]
        self.assertTrue(Path(parity_config.submission_path).name.endswith(".py"))
        gate_config = gate_mock.call_args.args[0]
        self.assertTrue(Path(gate_config.submission_path).name.endswith(".py"))
        suite_mock.assert_called_once_with(default_manifest_paths(), report_dir=None)

    def test_parity_failure_makes_preflight_fail(self) -> None:
        result = self.run_mocked_preflight(
            parity=parity_result(passed=False, mismatch_count=1),
        )

        self.assertFalse(result.passed)
        self.assertEqual(result.exit_code, 1)
        self.assertEqual(
            result.summary_text,
            (
                "submission_preflight=FAIL total=4 passed=3 failed=1 "
                "failed_checks=submission_parity exit_code=1"
            ),
        )
        parity_check = result.checks[1]
        self.assertEqual(parity_check.name, "submission_parity")
        self.assertEqual(parity_check.failure_reasons, ("generated submission parity failed",))

    def test_regression_gate_failure_is_reported(self) -> None:
        result = self.run_mocked_preflight(gate=regression_result(passed=False))

        self.assertFalse(result.passed)
        self.assertEqual(result.checks[2].name, "regression_gate")
        self.assertEqual(
            result.checks[2].failure_reasons,
            ("parity_mismatch: generated submission parity failed",),
        )

    def test_experiment_suite_failure_is_reported(self) -> None:
        result = self.run_mocked_preflight(suite=suite_result(exit_code=1))

        self.assertFalse(result.passed)
        self.assertEqual(result.checks[3].name, "experiment_suite")
        self.assertIn("failed_checks=experiment_suite", result.summary_text)

    def test_raised_exception_is_captured_as_failed_check(self) -> None:
        with patch(
            "ow_eval.submission_preflight.write_submission",
            side_effect=fake_write_submission,
        ), patch(
            "ow_eval.submission_preflight.run_submission_parity_check",
            side_effect=RuntimeError("boom"),
        ), patch(
            "ow_eval.submission_preflight.run_regression_gate",
            return_value=regression_result(),
        ), patch(
            "ow_eval.submission_preflight.run_evaluation_suite",
            return_value=suite_result(),
        ):
            result = run_submission_preflight()

        self.assertFalse(result.passed)
        self.assertEqual(result.checks[1].exit_code, 2)
        self.assertEqual(result.checks[1].failure_reasons, ("RuntimeError: boom",))
        self.assertIn("submission_parity", result.summary_text)

    def test_build_failure_marks_parity_as_unavailable(self) -> None:
        with patch(
            "ow_eval.submission_preflight.write_submission",
            side_effect=ValueError("build failed"),
        ), patch(
            "ow_eval.submission_preflight.run_submission_parity_check",
        ) as parity_mock, patch(
            "ow_eval.submission_preflight.run_regression_gate",
            return_value=regression_result(),
        ), patch(
            "ow_eval.submission_preflight.run_evaluation_suite",
            return_value=suite_result(),
        ):
            result = run_submission_preflight()

        self.assertFalse(result.passed)
        self.assertEqual(result.checks[0].failure_reasons, ("ValueError: build failed",))
        self.assertEqual(result.checks[1].failure_reasons, ("submission build unavailable",))
        parity_mock.assert_not_called()

    def test_skip_flags_mark_expensive_checks_as_skipped(self) -> None:
        with patch(
            "ow_eval.submission_preflight.write_submission",
            side_effect=fake_write_submission,
        ), patch(
            "ow_eval.submission_preflight.run_submission_parity_check",
        ) as parity_mock, patch(
            "ow_eval.submission_preflight.run_regression_gate",
        ) as gate_mock, patch(
            "ow_eval.submission_preflight.run_evaluation_suite",
        ) as suite_mock:
            result = run_submission_preflight(
                skip_parity=True,
                skip_regression_gate=True,
                skip_experiment_suite=True,
            )

        self.assertTrue(result.passed)
        self.assertEqual(
            tuple(check.summary_text for check in result.checks[1:]),
            (
                "preflight_check=submission_parity status=SKIPPED exit_code=0",
                "preflight_check=regression_gate status=SKIPPED exit_code=0",
                "preflight_check=experiment_suite status=SKIPPED exit_code=0",
            ),
        )
        parity_mock.assert_not_called()
        gate_mock.assert_not_called()
        suite_mock.assert_not_called()

    def test_manifest_paths_and_suite_report_dir_are_passed_to_suite(self) -> None:
        with patch(
            "ow_eval.submission_preflight.write_submission",
            side_effect=fake_write_submission,
        ), patch(
            "ow_eval.submission_preflight.run_submission_parity_check",
            return_value=parity_result(),
        ), patch(
            "ow_eval.submission_preflight.run_regression_gate",
            return_value=regression_result(),
        ), patch(
            "ow_eval.submission_preflight.run_evaluation_suite",
            return_value=suite_result(),
        ) as suite_mock:
            run_submission_preflight(
                manifest_paths=("/tmp/b.json", "/tmp/a.json"),
                suite_report_dir="/tmp/reports",
            )

        suite_mock.assert_called_once_with(
            ("/tmp/b.json", "/tmp/a.json"),
            report_dir="/tmp/reports",
        )

    def test_to_dict_output_is_json_safe(self) -> None:
        result = self.run_mocked_preflight()

        decoded = json.loads(json.dumps(result.to_dict(), sort_keys=True))

        self.assertEqual(decoded["passed"], True)
        self.assertEqual(decoded["checks"][0]["name"], "submission_build")
        self.assertEqual(decoded["checks"][0]["failure_reasons"], [])
        self.assertEqual(decoded["exit_code"], 0)

    def test_main_prints_summary_and_returns_exit_code(self) -> None:
        fake_result = SubmissionPreflightResult(
            checks=(
                SubmissionPreflightCheck(
                    name="submission_build",
                    passed=True,
                    exit_code=0,
                    summary_text="preflight_check=submission_build status=PASS exit_code=0",
                ),
                SubmissionPreflightCheck(
                    name="submission_parity",
                    passed=False,
                    exit_code=1,
                    summary_text="preflight_check=submission_parity status=FAIL exit_code=1",
                    failure_reasons=("generated submission parity failed",),
                ),
            ),
            passed=False,
            exit_code=1,
            summary_text=(
                "submission_preflight=FAIL total=2 passed=1 failed=1 "
                "failed_checks=submission_parity exit_code=1"
            ),
        )
        stdout = io.StringIO()
        stderr = io.StringIO()

        with patch(
            "ow_eval.submission_preflight.run_submission_preflight",
            return_value=fake_result,
        ) as runner, contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = run_submission_preflight_main(
                [
                    "--skip-parity",
                    "--skip-regression-gate",
                    "--skip-experiment-suite",
                    "--suite-report-dir",
                    "/tmp/reports",
                    "/tmp/a.json",
                    "/tmp/b.json",
                ]
            )

        self.assertEqual(exit_code, 1)
        runner.assert_called_once_with(
            manifest_paths=("/tmp/a.json", "/tmp/b.json"),
            suite_report_dir="/tmp/reports",
            skip_parity=True,
            skip_regression_gate=True,
            skip_experiment_suite=True,
        )
        self.assertEqual(
            stdout.getvalue(),
            (
                fake_result.summary_text
                + "\n"
                + fake_result.checks[0].summary_text
                + "\n"
                + fake_result.checks[1].summary_text
                + "\n"
            ),
        )
        self.assertEqual(
            stderr.getvalue(),
            "submission_parity: generated submission parity failed\n",
        )

    def test_script_help_parser_works(self) -> None:
        stdout = io.StringIO()
        with self.assertRaises(SystemExit) as raised, contextlib.redirect_stdout(stdout):
            run_submission_preflight_main(["--help"])

        self.assertEqual(raised.exception.code, 0)
        self.assertIn("Run local submission-readiness preflight checks.", stdout.getvalue())

    def run_mocked_preflight(
        self,
        *,
        parity: SubmissionParityResult | None = None,
        gate: RegressionGateResult | None = None,
        suite: ExperimentSuiteResult | None = None,
    ) -> SubmissionPreflightResult:
        with patch(
            "ow_eval.submission_preflight.write_submission",
            side_effect=fake_write_submission,
        ), patch(
            "ow_eval.submission_preflight.run_submission_parity_check",
            return_value=parity or parity_result(),
        ), patch(
            "ow_eval.submission_preflight.run_regression_gate",
            return_value=gate or regression_result(),
        ), patch(
            "ow_eval.submission_preflight.run_evaluation_suite",
            return_value=suite or suite_result(),
        ):
            return run_submission_preflight()


if __name__ == "__main__":
    unittest.main()
