"""Tests for Evaluation Harness Cycle 15 experiment reports."""

from __future__ import annotations

import importlib
import json
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from ow_eval import (
    AgentSourceKind,
    AgentSpec,
    EvaluationBatchResult,
    EvaluationStatus,
    ExperimentManifest,
    ExperimentReport,
    ExperimentRunResult,
    FailureCategory,
    MatchMetrics,
    PlannerAnalysisItem,
    PlannerAnalysisPack,
    PromotionGateDecision,
    PromotionGateFailure,
    ScoreboardRecord,
    build_experiment_report,
    read_experiment_report,
    write_experiment_report,
)


def manifest() -> ExperimentManifest:
    return ExperimentManifest(
        name="report-smoke",
        candidate_agent=AgentSpec(
            name="candidate-agent",
            source_kind=AgentSourceKind.MODULAR_AGENT,
            module_path="agents.orbit_wars_agent",
        ),
        scenarios=(),
        version="v3",
        metadata=(("zeta", "last"), ("alpha", "first")),
    )


def scoreboard() -> ScoreboardRecord:
    return ScoreboardRecord(
        agent_name="candidate-agent",
        agent_version="v3",
        commit="abc123",
        scenario_set="report-smoke",
        match_count=2,
        completed_count=2,
        win_count=1,
        loss_count=1,
        error_count=0,
        win_rate=0.5,
        mean_rank=1.5,
        mean_score=7.25,
        error_rate=0.0,
        triage_category_counts=(("clean", 1), ("normal_loss", 1)),
        notes=("local review",),
        metadata=(("suite", "report"),),
    )


def analysis_pack() -> PlannerAnalysisPack:
    item = PlannerAnalysisItem(
        batch_index=1,
        label="loss",
        seed=8,
        player_count=2,
        controlled_seat=0,
        candidate_agent_name="candidate-agent",
        opponent_names=("opponent",),
        status=EvaluationStatus.COMPLETED,
        triage_category=FailureCategory.NORMAL_LOSS,
        triage_reason="completed with losing final rank",
        final_rank=2,
        final_score=4.5,
        final_planets=1,
        final_ships=20,
        final_production=2,
        turns_survived=100,
        no_action_count=3,
        invalid_action_count=0,
        timeout_count=0,
        error_count=0,
        replay_path="/tmp/replay.json",
        artifact_path="/tmp/result.json",
        selected_metadata=(("selected_target", "5"),),
    )
    return PlannerAnalysisPack(
        items=(item,),
        total_results=2,
        included_count=1,
        omitted_count=1,
        triage_category_counts=(("normal_loss", 1),),
    )


def promotion_decision() -> PromotionGateDecision:
    failure = PromotionGateFailure(
        code="max_mean_rank_exceeded",
        message="mean_rank 1.5 exceeds 1.25",
        observed=1.5,
        threshold=1.25,
    )
    return PromotionGateDecision(
        passed=False,
        failures=(failure,),
        summary_text=(
            "promotion=FAIL experiment=report-smoke matches=2 completed=2 "
            "win_rate=0.5 error_rate=0 mean_rank=1.5 failures=1"
        ),
    )


def run_result() -> ExperimentRunResult:
    return ExperimentRunResult(
        manifest=manifest(),
        matches=(),
        batch_result=EvaluationBatchResult(),
        scoreboard_record=scoreboard(),
        analysis_pack=analysis_pack(),
        summary_text=(
            "experiment=report-smoke matches=2 completed=2 errors=0 "
            "win_rate=0.5 mean_rank=1.5 analysis_items=1"
        ),
    )


def report() -> ExperimentReport:
    return build_experiment_report(run_result(), promotion_decision())


class EvaluationExperimentReportTests(unittest.TestCase):
    def test_report_module_imports_and_exports_are_available(self) -> None:
        module = importlib.import_module("ow_eval.experiment_report")

        self.assertIs(module.ExperimentReport, ExperimentReport)
        self.assertIs(module.build_experiment_report, build_experiment_report)
        self.assertIs(module.write_experiment_report, write_experiment_report)
        self.assertIs(module.read_experiment_report, read_experiment_report)

    def test_report_contract_is_frozen_slotted_and_validates(self) -> None:
        built_report = report()

        with self.assertRaises(FrozenInstanceError):
            built_report.manifest_name = "changed"  # type: ignore[misc]
        with self.assertRaises((AttributeError, TypeError)):
            built_report.extra = "nope"  # type: ignore[attr-defined]
        with self.assertRaisesRegex(ValueError, "manifest_name"):
            ExperimentReport(
                manifest_name="",
                manifest_version=None,
                candidate_agent_name="candidate",
                commit=None,
                run_summary_text="run",
                promotion_summary_text="promotion",
                scoreboard_record=scoreboard(),
                analysis_pack=analysis_pack(),
                promotion_decision=promotion_decision(),
            )
        with self.assertRaisesRegex(ValueError, "scoreboard_record"):
            ExperimentReport(
                manifest_name="experiment",
                manifest_version=None,
                candidate_agent_name="candidate",
                commit=None,
                run_summary_text="run",
                promotion_summary_text="promotion",
                scoreboard_record="bad",  # type: ignore[arg-type]
                analysis_pack=analysis_pack(),
                promotion_decision=promotion_decision(),
            )

    def test_build_report_from_run_result_and_promotion_decision(self) -> None:
        result = run_result()
        decision = promotion_decision()

        built_report = build_experiment_report(result, decision)

        self.assertEqual(built_report.manifest_name, "report-smoke")
        self.assertEqual(built_report.manifest_version, "v3")
        self.assertEqual(built_report.candidate_agent_name, "candidate-agent")
        self.assertEqual(built_report.commit, "abc123")
        self.assertEqual(built_report.run_summary_text, result.summary_text)
        self.assertEqual(built_report.promotion_summary_text, decision.summary_text)
        self.assertIs(built_report.scoreboard_record, result.scoreboard_record)
        self.assertIs(built_report.analysis_pack, result.analysis_pack)
        self.assertIs(built_report.promotion_decision, decision)
        self.assertEqual(
            built_report.metadata,
            (("alpha", "first"), ("zeta", "last")),
        )

    def test_to_dict_and_from_dict_round_trip_json_safe_data(self) -> None:
        built_report = report()

        encoded = json.dumps(built_report.to_dict(), sort_keys=True)
        decoded = json.loads(encoded)
        restored = ExperimentReport.from_dict(decoded)

        self.assertEqual(restored, built_report)
        self.assertEqual(restored.scoreboard_record.mean_score, 7.25)
        self.assertEqual(decoded["scoreboard_record"]["completed_matches"], 2)
        self.assertEqual(decoded["scoreboard_record"]["completed_count"], 2)
        self.assertEqual(restored.analysis_pack.items[0].final_score, 4.5)
        self.assertEqual(
            restored.promotion_decision.failures[0].code,
            "max_mean_rank_exceeded",
        )

    def test_write_and_read_report_use_deterministic_json_file(self) -> None:
        built_report = report()
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "nested" / "report.json"

            written_path = write_experiment_report(built_report, path)
            text = written_path.read_text(encoding="utf-8")
            restored = read_experiment_report(written_path)

        self.assertEqual(written_path, path)
        self.assertTrue(text.endswith("\n"))
        self.assertIn('\n  "analysis_pack":', text)
        self.assertEqual(restored, built_report)

    def test_metadata_ordering_is_stable_in_report_and_dict_output(self) -> None:
        built_report = report()
        data = built_report.to_dict()

        self.assertEqual(
            built_report.metadata,
            (("alpha", "first"), ("zeta", "last")),
        )
        self.assertEqual(
            data["metadata"],
            [
                {"key": "alpha", "value": "first"},
                {"key": "zeta", "value": "last"},
            ],
        )

    def test_build_report_rejects_wrong_input_types(self) -> None:
        with self.assertRaisesRegex(ValueError, "run_result"):
            build_experiment_report("bad", promotion_decision())  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "decision"):
            build_experiment_report(run_result(), "bad")  # type: ignore[arg-type]

    def test_from_dict_rejects_malformed_nested_data(self) -> None:
        data = report().to_dict()
        data["promotion_decision"] = "bad"

        with self.assertRaisesRegex(ValueError, "promotion_decision"):
            ExperimentReport.from_dict(data)  # type: ignore[arg-type]

    def test_read_report_rejects_non_object_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "report.json"
            path.write_text("[]\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "report JSON"):
                read_experiment_report(path)


if __name__ == "__main__":
    unittest.main()
