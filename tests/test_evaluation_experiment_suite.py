"""Tests for Evaluation Harness Cycle 18 experiment suite workflow."""

from __future__ import annotations

import contextlib
import importlib
import io
import json
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch

from ow_eval import (
    ExperimentCliResult,
    ExperimentSuiteResult,
    default_manifest_paths,
    run_evaluation_suite,
    run_evaluation_suite_main,
)


def child_result(
    manifest_path: str | Path,
    *,
    exit_code: int = 0,
    report_path: str | Path | None = None,
    error_text: str | None = None,
) -> ExperimentCliResult:
    status = "PASS" if exit_code == 0 else "FAIL"
    return ExperimentCliResult(
        manifest_path=str(manifest_path),
        report_path=str(report_path) if report_path is not None else None,
        exit_code=exit_code,
        summary_text=(
            f"experiment_workflow={status} manifest={Path(manifest_path).stem} "
            f"promotion_passed={str(exit_code == 0).lower()} "
            f"exit_code={exit_code} report_path={report_path or 'none'}"
        ),
        error_text=error_text,
    )


class EvaluationExperimentSuiteTests(unittest.TestCase):
    def test_suite_module_imports_and_exports_are_available(self) -> None:
        module = importlib.import_module("ow_eval.experiment_suite")

        self.assertIs(module.ExperimentSuiteResult, ExperimentSuiteResult)
        self.assertIs(module.run_evaluation_suite, run_evaluation_suite)
        self.assertIs(module.main, run_evaluation_suite_main)
        self.assertIs(module.default_manifest_paths, default_manifest_paths)

    def test_suite_result_is_frozen_slotted_and_validates(self) -> None:
        result = ExperimentSuiteResult(
            manifest_paths=("/tmp/a.json",),
            results=(child_result("/tmp/a.json"),),
            exit_code=0,
            summary_text="summary",
        )

        with self.assertRaises(FrozenInstanceError):
            result.exit_code = 1  # type: ignore[misc]
        with self.assertRaises((AttributeError, TypeError)):
            result.extra = "nope"  # type: ignore[attr-defined]
        with self.assertRaisesRegex(ValueError, "manifest_paths"):
            ExperimentSuiteResult(
                manifest_paths=["/tmp/a.json"],  # type: ignore[arg-type]
                results=(),
                summary_text="summary",
            )
        with self.assertRaisesRegex(ValueError, "results"):
            ExperimentSuiteResult(
                manifest_paths=(),
                results=("bad",),  # type: ignore[arg-type]
                summary_text="summary",
            )
        with self.assertRaisesRegex(ValueError, "summary_text"):
            ExperimentSuiteResult(manifest_paths=(), results=(), summary_text="")

    def test_default_manifest_paths_are_committed_fixtures_in_stable_order(self) -> None:
        self.assertEqual(
            tuple(path.name for path in default_manifest_paths()),
            (
                "quick-2p-smoke.json",
                "quick-4p-smoke.json",
                "promotion-smoke.json",
            ),
        )
        self.assertTrue(all(path.is_file() for path in default_manifest_paths()))

    def test_explicit_manifest_paths_preserve_order(self) -> None:
        paths = (Path("/tmp/b.json"), Path("/tmp/a.json"))
        seen_paths: list[str] = []

        def fake_workflow(path: str | Path, *, report_path: object = None) -> ExperimentCliResult:
            _ = report_path
            seen_paths.append(str(path))
            return child_result(path)

        with patch(
            "ow_eval.experiment_suite.run_evaluation_experiment",
            side_effect=fake_workflow,
        ):
            result = run_evaluation_suite(paths)

        self.assertEqual(seen_paths, ["/tmp/b.json", "/tmp/a.json"])
        self.assertEqual(result.manifest_paths, ("/tmp/b.json", "/tmp/a.json"))
        self.assertEqual(tuple(child.manifest_path for child in result.results), result.manifest_paths)
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.passed)
        self.assertEqual(
            result.summary_text,
            (
                "experiment_suite=PASS total=2 passed=2 failed=0 "
                "failed_manifests=none exit_code=0"
            ),
        )

    def test_any_failed_child_result_makes_suite_exit_nonzero(self) -> None:
        paths = (Path("/tmp/pass.json"), Path("/tmp/fail.json"))

        def fake_workflow(path: str | Path, *, report_path: object = None) -> ExperimentCliResult:
            _ = report_path
            return child_result(path, exit_code=0 if Path(path).stem == "pass" else 1)

        with patch(
            "ow_eval.experiment_suite.run_evaluation_experiment",
            side_effect=fake_workflow,
        ):
            result = run_evaluation_suite(paths)

        self.assertEqual(result.exit_code, 1)
        self.assertFalse(result.passed)
        self.assertEqual(
            result.summary_text,
            (
                "experiment_suite=FAIL total=2 passed=1 failed=1 "
                "failed_manifests=fail exit_code=1"
            ),
        )

    def test_report_dir_maps_each_manifest_to_stable_report_path(self) -> None:
        paths = (Path("/tmp/quick-2p-smoke.json"), Path("/tmp/promotion-smoke.json"))
        report_dir = Path("/tmp/reports")
        seen_report_paths: list[str | None] = []

        def fake_workflow(
            path: str | Path,
            *,
            report_path: str | Path | None = None,
        ) -> ExperimentCliResult:
            seen_report_paths.append(str(report_path) if report_path else None)
            return child_result(path, report_path=report_path)

        with patch(
            "ow_eval.experiment_suite.run_evaluation_experiment",
            side_effect=fake_workflow,
        ):
            result = run_evaluation_suite(paths, report_dir=report_dir)

        self.assertEqual(
            seen_report_paths,
            [
                "/tmp/reports/quick-2p-smoke.report.json",
                "/tmp/reports/promotion-smoke.report.json",
            ],
        )
        self.assertEqual(result.report_dir, "/tmp/reports")
        self.assertEqual(
            tuple(child.report_path for child in result.results),
            tuple(seen_report_paths),
        )

    def test_no_reports_are_written_by_default(self) -> None:
        seen_report_paths = []

        def fake_workflow(
            path: str | Path,
            *,
            report_path: str | Path | None = None,
        ) -> ExperimentCliResult:
            seen_report_paths.append(report_path)
            return child_result(path)

        with patch(
            "ow_eval.experiment_suite.run_evaluation_experiment",
            side_effect=fake_workflow,
        ):
            result = run_evaluation_suite((Path("/tmp/a.json"),))

        self.assertEqual(seen_report_paths, [None])
        self.assertIsNone(result.report_dir)

    def test_unexpected_child_exception_is_captured_as_failed_result(self) -> None:
        with patch(
            "ow_eval.experiment_suite.run_evaluation_experiment",
            side_effect=RuntimeError("boom"),
        ):
            result = run_evaluation_suite((Path("/tmp/a.json"),))

        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.results[0].exit_code, 2)
        self.assertEqual(result.results[0].error_text, "RuntimeError: boom")
        self.assertEqual(
            result.summary_text,
            (
                "experiment_suite=FAIL total=1 passed=0 failed=1 "
                "failed_manifests=a exit_code=1"
            ),
        )

    def test_to_dict_output_is_json_safe(self) -> None:
        result = ExperimentSuiteResult(
            manifest_paths=("/tmp/a.json",),
            results=(child_result("/tmp/a.json"),),
            report_dir="/tmp/reports",
            exit_code=0,
            summary_text="summary",
        )

        decoded = json.loads(json.dumps(result.to_dict(), sort_keys=True))

        self.assertEqual(decoded["manifest_paths"], ["/tmp/a.json"])
        self.assertEqual(decoded["results"][0]["exit_code"], 0)
        self.assertEqual(decoded["passed"], True)
        self.assertEqual(decoded["report_dir"], "/tmp/reports")

    def test_main_uses_default_manifests_when_none_are_supplied(self) -> None:
        fake_result = ExperimentSuiteResult(
            manifest_paths=tuple(str(path) for path in default_manifest_paths()),
            results=(),
            exit_code=0,
            summary_text="experiment_suite=PASS total=3 passed=3 failed=0 failed_manifests=none exit_code=0",
        )
        stdout = io.StringIO()
        stderr = io.StringIO()

        with patch(
            "ow_eval.experiment_suite.run_evaluation_suite",
            return_value=fake_result,
        ) as runner, contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = run_evaluation_suite_main([])

        self.assertEqual(exit_code, 0)
        runner.assert_called_once_with(default_manifest_paths(), report_dir=None)
        self.assertEqual(stdout.getvalue(), fake_result.summary_text + "\n")
        self.assertEqual(stderr.getvalue(), "")

    def test_main_preserves_explicit_paths_and_report_dir(self) -> None:
        fake_result = ExperimentSuiteResult(
            manifest_paths=("/tmp/b.json", "/tmp/a.json"),
            results=(
                child_result("/tmp/b.json"),
                child_result("/tmp/a.json", exit_code=1),
            ),
            report_dir="/tmp/reports",
            exit_code=1,
            summary_text="experiment_suite=FAIL total=2 passed=1 failed=1 failed_manifests=a exit_code=1",
        )
        stdout = io.StringIO()

        with patch(
            "ow_eval.experiment_suite.run_evaluation_suite",
            return_value=fake_result,
        ) as runner, contextlib.redirect_stdout(stdout):
            exit_code = run_evaluation_suite_main(
                [
                    "--report-dir",
                    "/tmp/reports",
                    "/tmp/b.json",
                    "/tmp/a.json",
                ]
            )

        self.assertEqual(exit_code, 1)
        runner.assert_called_once_with(
            ("/tmp/b.json", "/tmp/a.json"),
            report_dir="/tmp/reports",
        )
        self.assertEqual(
            stdout.getvalue(),
            (
                fake_result.summary_text
                + "\n"
                + fake_result.results[0].summary_text
                + "\n"
                + fake_result.results[1].summary_text
                + "\n"
            ),
        )

    def test_main_prints_child_errors_to_stderr(self) -> None:
        fake_result = ExperimentSuiteResult(
            manifest_paths=("/tmp/a.json",),
            results=(
                child_result(
                    "/tmp/a.json",
                    exit_code=2,
                    error_text="ValueError: bad manifest",
                ),
            ),
            exit_code=1,
            summary_text="experiment_suite=FAIL total=1 passed=0 failed=1 failed_manifests=a exit_code=1",
        )
        stderr = io.StringIO()

        with patch(
            "ow_eval.experiment_suite.run_evaluation_suite",
            return_value=fake_result,
        ), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
            exit_code = run_evaluation_suite_main(["/tmp/a.json"])

        self.assertEqual(exit_code, 1)
        self.assertEqual(stderr.getvalue(), "ValueError: bad manifest\n")

    def test_script_help_works_from_repo_root(self) -> None:
        # The validator also exercises the real script. This test keeps coverage
        # focused on the exported main parser without running workflows.
        stdout = io.StringIO()
        with self.assertRaises(SystemExit) as raised, contextlib.redirect_stdout(stdout):
            run_evaluation_suite_main(["--help"])

        self.assertEqual(raised.exception.code, 0)
        self.assertIn("Run a local evaluation experiment manifest suite.", stdout.getvalue())

    def test_suite_tests_do_not_create_report_files_without_report_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            before = tuple(Path(temp_dir).iterdir())

            with patch(
                "ow_eval.experiment_suite.run_evaluation_experiment",
                side_effect=lambda path, *, report_path=None: child_result(
                    path,
                    report_path=report_path,
                ),
            ):
                run_evaluation_suite((Path(temp_dir) / "a.json",))

            after = tuple(Path(temp_dir).iterdir())

        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
