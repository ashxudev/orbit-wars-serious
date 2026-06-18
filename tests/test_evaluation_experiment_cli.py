"""Tests for Evaluation Harness Cycle 16 experiment CLI workflow."""

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
    AgentSourceKind,
    AgentSpec,
    EvaluationBatchResult,
    ExperimentCliResult,
    ExperimentManifest,
    ExperimentRunResult,
    PlannerAnalysisPack,
    PromotionGateDecision,
    PromotionThresholds,
    ScoreboardRecord,
    read_experiment_report,
    run_evaluation_experiment,
    run_evaluation_experiment_main,
)


def manifest(thresholds: PromotionThresholds | None = None) -> ExperimentManifest:
    return ExperimentManifest(
        name="cli-smoke",
        candidate_agent=AgentSpec(
            name="candidate",
            source_kind=AgentSourceKind.MODULAR_AGENT,
            module_path="agents.orbit_wars_agent",
        ),
        scenarios=(),
        version="v1",
        metadata=(("suite", "cli"),),
        promotion_thresholds=thresholds or PromotionThresholds(min_win_rate=0.5),
    )


def scoreboard(
    *,
    win_rate: float | None = 0.5,
    error_rate: float | None = 0.0,
    mean_rank: float | None = 1.5,
) -> ScoreboardRecord:
    return ScoreboardRecord(
        agent_name="candidate",
        agent_version="v1",
        commit="abc123",
        scenario_set="cli-smoke",
        match_count=2,
        completed_count=2,
        win_count=1,
        loss_count=1,
        error_count=0,
        win_rate=win_rate,
        error_rate=error_rate,
        mean_rank=mean_rank,
        mean_score=6.0,
    )


def run_result_for(
    experiment: ExperimentManifest,
    *,
    record: ScoreboardRecord | None = None,
) -> ExperimentRunResult:
    return ExperimentRunResult(
        manifest=experiment,
        matches=(),
        batch_result=EvaluationBatchResult(),
        scoreboard_record=record or scoreboard(),
        analysis_pack=PlannerAnalysisPack(total_results=2),
        summary_text=(
            "experiment=cli-smoke matches=2 completed=2 errors=0 "
            "win_rate=0.5 mean_rank=1.5 analysis_items=0"
        ),
    )


def write_manifest(path: Path, experiment: ExperimentManifest) -> None:
    path.write_text(
        json.dumps(experiment.to_dict(), sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


class EvaluationExperimentCliTests(unittest.TestCase):
    def test_cli_module_imports_and_exports_are_available(self) -> None:
        module = importlib.import_module("ow_eval.experiment_cli")

        self.assertIs(module.ExperimentCliResult, ExperimentCliResult)
        self.assertIs(module.run_evaluation_experiment, run_evaluation_experiment)
        self.assertIs(module.main, run_evaluation_experiment_main)

    def test_cli_result_is_frozen_slotted_and_validates(self) -> None:
        result = ExperimentCliResult(
            manifest_path="/tmp/manifest.json",
            exit_code=0,
            summary_text="summary",
        )

        with self.assertRaises(FrozenInstanceError):
            result.exit_code = 1  # type: ignore[misc]
        with self.assertRaises((AttributeError, TypeError)):
            result.extra = "nope"  # type: ignore[attr-defined]
        with self.assertRaisesRegex(ValueError, "manifest_path"):
            ExperimentCliResult(manifest_path="", summary_text="summary")
        with self.assertRaisesRegex(ValueError, "exit_code"):
            ExperimentCliResult(
                manifest_path="/tmp/manifest.json",
                exit_code=True,  # type: ignore[arg-type]
                summary_text="summary",
            )
        with self.assertRaisesRegex(ValueError, "summary_text"):
            ExperimentCliResult(manifest_path="/tmp/manifest.json", summary_text="")

    def test_passing_manifest_workflow_returns_zero_exit_code(self) -> None:
        experiment = manifest(PromotionThresholds(min_win_rate=0.5))
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "manifest.json"
            write_manifest(manifest_path, experiment)

            with patch(
                "ow_eval.experiment_cli.run_experiment_manifest",
                side_effect=lambda loaded, config=None: run_result_for(loaded),
            ) as run_manifest:
                result = run_evaluation_experiment(manifest_path)

        self.assertEqual(result.exit_code, 0)
        self.assertIsNotNone(result.run_result)
        self.assertIsNotNone(result.promotion_decision)
        self.assertTrue(result.promotion_decision.passed)
        self.assertIsNotNone(result.experiment_report)
        self.assertIsNone(result.report_path)
        self.assertIsNone(result.error_text)
        self.assertEqual(run_manifest.call_count, 1)
        self.assertEqual(
            result.summary_text,
            (
                "experiment_workflow=PASS manifest=cli-smoke "
                "promotion_passed=true exit_code=0 report_path=none"
            ),
        )

    def test_failing_promotion_decision_returns_nonzero_exit_code(self) -> None:
        experiment = manifest(PromotionThresholds(min_win_rate=0.75))
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "manifest.json"
            write_manifest(manifest_path, experiment)

            with patch(
                "ow_eval.experiment_cli.run_experiment_manifest",
                side_effect=lambda loaded, config=None: run_result_for(loaded),
            ):
                result = run_evaluation_experiment(manifest_path)

        self.assertEqual(result.exit_code, 1)
        self.assertFalse(result.promotion_decision.passed)
        self.assertEqual(
            tuple(failure.code for failure in result.promotion_decision.failures),
            ("min_win_rate_not_met",),
        )
        self.assertIn("experiment_workflow=FAIL", result.summary_text)

    def test_output_path_writes_deterministic_report_json(self) -> None:
        experiment = manifest(PromotionThresholds(min_win_rate=0.5))
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "manifest.json"
            report_path = Path(temp_dir) / "reports" / "report.json"
            write_manifest(manifest_path, experiment)

            with patch(
                "ow_eval.experiment_cli.run_experiment_manifest",
                side_effect=lambda loaded, config=None: run_result_for(loaded),
            ):
                result = run_evaluation_experiment(
                    manifest_path,
                    report_path=report_path,
                )

            text = report_path.read_text(encoding="utf-8")
            restored = read_experiment_report(report_path)

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.report_path, str(report_path))
        self.assertTrue(text.endswith("\n"))
        self.assertIn('\n  "promotion_decision":', text)
        self.assertEqual(restored, result.experiment_report)
        self.assertIn(f"report_path={report_path}", result.summary_text)

    def test_no_report_is_written_by_default(self) -> None:
        experiment = manifest(PromotionThresholds(min_win_rate=0.5))
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "manifest.json"
            write_manifest(manifest_path, experiment)

            with patch(
                "ow_eval.experiment_cli.run_experiment_manifest",
                side_effect=lambda loaded, config=None: run_result_for(loaded),
            ), patch(
                "ow_eval.experiment_cli.write_experiment_report",
            ) as writer:
                result = run_evaluation_experiment(manifest_path)

        self.assertEqual(result.exit_code, 0)
        self.assertIsNone(result.report_path)
        writer.assert_not_called()

    def test_malformed_manifest_input_returns_structured_workflow_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "manifest.json"
            manifest_path.write_text("[]\n", encoding="utf-8")

            with patch(
                "ow_eval.experiment_cli.run_experiment_manifest",
            ) as run_manifest:
                result = run_evaluation_experiment(manifest_path)

        self.assertEqual(result.exit_code, 2)
        self.assertIsNone(result.run_result)
        self.assertIsNone(result.promotion_decision)
        self.assertIsNone(result.experiment_report)
        self.assertEqual(result.error_text, "ValueError: manifest JSON must be an object")
        self.assertIn("experiment_workflow=ERROR", result.summary_text)
        run_manifest.assert_not_called()

    def test_to_dict_output_is_json_safe(self) -> None:
        experiment = manifest(PromotionThresholds(min_win_rate=0.5))
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "manifest.json"
            write_manifest(manifest_path, experiment)

            with patch(
                "ow_eval.experiment_cli.run_experiment_manifest",
                side_effect=lambda loaded, config=None: run_result_for(loaded),
            ):
                result = run_evaluation_experiment(manifest_path)

        decoded = json.loads(json.dumps(result.to_dict(), sort_keys=True))

        self.assertEqual(decoded["exit_code"], 0)
        self.assertEqual(decoded["promotion_decision"]["passed"], True)
        self.assertEqual(decoded["experiment_report"]["manifest_name"], "cli-smoke")

    def test_main_prints_summary_and_returns_exit_code(self) -> None:
        fake_decision = PromotionGateDecision(
            passed=False,
            summary_text="promotion=FAIL",
        )
        fake_result = ExperimentCliResult(
            manifest_path="/tmp/manifest.json",
            promotion_decision=fake_decision,
            exit_code=1,
            summary_text="experiment_workflow=FAIL manifest=cli-smoke",
        )
        stdout = io.StringIO()
        stderr = io.StringIO()

        with patch(
            "ow_eval.experiment_cli.run_evaluation_experiment",
            return_value=fake_result,
        ) as runner, contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = run_evaluation_experiment_main(
                ["/tmp/manifest.json", "--report-output", "/tmp/report.json"]
            )

        self.assertEqual(exit_code, 1)
        runner.assert_called_once_with(
            "/tmp/manifest.json",
            report_path="/tmp/report.json",
        )
        self.assertEqual(stdout.getvalue(), "experiment_workflow=FAIL manifest=cli-smoke\n")
        self.assertEqual(stderr.getvalue(), "")

    def test_main_prints_workflow_errors_to_stderr(self) -> None:
        fake_result = ExperimentCliResult(
            manifest_path="/tmp/manifest.json",
            exit_code=2,
            summary_text="experiment_workflow=ERROR manifest=/tmp/manifest.json",
            error_text="ValueError: manifest JSON must be an object",
        )
        stdout = io.StringIO()
        stderr = io.StringIO()

        with patch(
            "ow_eval.experiment_cli.run_evaluation_experiment",
            return_value=fake_result,
        ), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = run_evaluation_experiment_main(["/tmp/manifest.json"])

        self.assertEqual(exit_code, 2)
        self.assertEqual(
            stdout.getvalue(),
            "experiment_workflow=ERROR manifest=/tmp/manifest.json\n",
        )
        self.assertEqual(
            stderr.getvalue(),
            "ValueError: manifest JSON must be an object\n",
        )


if __name__ == "__main__":
    unittest.main()
