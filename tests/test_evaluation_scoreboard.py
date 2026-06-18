"""Tests for Evaluation Harness Cycle 9 scoreboard records."""

from __future__ import annotations

import importlib
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
    EvaluationStatus,
    MatchConfig,
    MatchMetrics,
    MatchResult,
    OpponentSpec,
    PlayerCount,
    ScoreboardRecord,
    append_scoreboard_record,
    build_scoreboard_record,
    read_scoreboard_records,
    write_scoreboard_record,
)


def match_config(seed: int = 7, label: str = "scoreboard") -> MatchConfig:
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


def result(
    *,
    seed: int = 7,
    status: EvaluationStatus = EvaluationStatus.COMPLETED,
    final_rank: int | None = 1,
    final_score: float | None = 10.0,
    error_text: str | None = None,
    no_action_count: int | None = None,
) -> MatchResult:
    return MatchResult(
        config=match_config(seed=seed),
        status=status,
        metrics=MatchMetrics(
            final_rank=final_rank,
            final_score=final_score,
            no_action_count=no_action_count,
            turns_survived=100 if no_action_count is not None else None,
        ),
        error_text=error_text,
    )


def batch_result(*results: MatchResult) -> EvaluationBatchResult:
    return EvaluationBatchResult(results=tuple(results))


class EvaluationScoreboardTests(unittest.TestCase):
    def test_scoreboard_module_imports_and_exports_are_available(self) -> None:
        module = importlib.import_module("ow_eval.scoreboard")

        self.assertIs(module.ScoreboardRecord, ScoreboardRecord)
        self.assertIs(module.build_scoreboard_record, build_scoreboard_record)
        self.assertIs(module.write_scoreboard_record, write_scoreboard_record)
        self.assertIs(module.append_scoreboard_record, append_scoreboard_record)
        self.assertIs(module.read_scoreboard_records, read_scoreboard_records)

    def test_scoreboard_record_is_frozen_slotted_and_validates(self) -> None:
        record = ScoreboardRecord(
            agent_name="agent",
            agent_version="v1",
            commit="abc123",
            scenario_set="smoke",
        )

        with self.assertRaises(FrozenInstanceError):
            record.agent_name = "changed"  # type: ignore[misc]
        with self.assertRaises((AttributeError, TypeError)):
            record.extra = "nope"  # type: ignore[attr-defined]
        with self.assertRaisesRegex(ValueError, "agent_name"):
            ScoreboardRecord(agent_name="", agent_version=None, commit=None, scenario_set="s")
        with self.assertRaisesRegex(ValueError, "match_count"):
            ScoreboardRecord(
                agent_name="agent",
                agent_version=None,
                commit=None,
                scenario_set="s",
                match_count=-1,
            )

    def test_build_record_counts_wins_losses_errors_and_rates(self) -> None:
        batch = batch_result(
            result(seed=1, final_rank=1, final_score=10.0),
            result(seed=2, final_rank=2, final_score=4.0),
            result(
                seed=3,
                status=EvaluationStatus.AGENT_ERROR,
                final_rank=None,
                final_score=None,
                error_text="RuntimeError: planner failed",
            ),
        )

        record = build_scoreboard_record(
            batch,
            agent_name="candidate",
            agent_version="v1",
            commit="abc123",
            scenario_set="seeds-1-3",
            notes=("baseline",),
            metadata={"suite": "unit"},
        )

        self.assertEqual(record.agent_name, "candidate")
        self.assertEqual(record.agent_version, "v1")
        self.assertEqual(record.commit, "abc123")
        self.assertEqual(record.scenario_set, "seeds-1-3")
        self.assertEqual(record.match_count, 3)
        self.assertEqual(record.completed_count, 2)
        self.assertEqual(record.win_count, 1)
        self.assertEqual(record.loss_count, 1)
        self.assertEqual(record.error_count, 1)
        self.assertEqual(record.win_rate, 1 / 3)
        self.assertEqual(record.error_rate, 1 / 3)
        self.assertEqual(record.mean_rank, 1.5)
        self.assertEqual(record.mean_score, 7.0)
        self.assertEqual(record.notes, ("baseline",))
        self.assertEqual(record.metadata, (("suite", "unit"),))

    def test_empty_batch_has_none_rates_and_means(self) -> None:
        record = build_scoreboard_record(
            batch_result(),
            agent_name="candidate",
            scenario_set="empty",
        )

        self.assertEqual(record.match_count, 0)
        self.assertEqual(record.completed_count, 0)
        self.assertEqual(record.win_count, 0)
        self.assertEqual(record.loss_count, 0)
        self.assertEqual(record.error_count, 0)
        self.assertIsNone(record.win_rate)
        self.assertIsNone(record.error_rate)
        self.assertIsNone(record.mean_rank)
        self.assertIsNone(record.mean_score)
        self.assertEqual(record.triage_category_counts, ())

    def test_missing_ranks_and_scores_are_ignored_for_means_and_outcomes(self) -> None:
        batch = batch_result(
            result(seed=1, final_rank=None, final_score=None),
            result(seed=2, final_rank=1, final_score=6.0),
        )

        record = build_scoreboard_record(
            batch,
            agent_name="candidate",
            scenario_set="missing-metrics",
        )

        self.assertEqual(record.match_count, 2)
        self.assertEqual(record.completed_count, 2)
        self.assertEqual(record.win_count, 1)
        self.assertEqual(record.loss_count, 0)
        self.assertEqual(record.error_count, 0)
        self.assertEqual(record.mean_rank, 1.0)
        self.assertEqual(record.mean_score, 6.0)

    def test_triage_category_counts_are_included_in_stable_order(self) -> None:
        batch = batch_result(
            result(seed=1, final_rank=1),
            result(seed=2, final_rank=2),
            result(
                seed=3,
                status=EvaluationStatus.AGENT_ERROR,
                final_rank=None,
                final_score=None,
                error_text="ValueError: action row invalid",
            ),
            result(
                seed=4,
                status=EvaluationStatus.AGENT_ERROR,
                final_rank=None,
                final_score=None,
                error_text="RuntimeError: run_planner_pipeline failed",
            ),
        )

        record = build_scoreboard_record(
            batch,
            agent_name="candidate",
            scenario_set="triage",
        )

        self.assertEqual(
            record.triage_category_counts,
            (
                ("planner_crash", 1),
                ("action_conversion_crash", 1),
                ("normal_loss", 1),
                ("clean", 1),
            ),
        )

    def test_to_dict_and_from_dict_round_trip_json_safe_data(self) -> None:
        record = build_scoreboard_record(
            batch_result(result(final_rank=1, final_score=3.0)),
            agent_name="candidate",
            agent_version="v1",
            commit="abc123",
            scenario_set="json",
            notes=("note",),
            metadata={"b": "2", "a": "1"},
        )

        data = record.to_dict()
        encoded = json.dumps(data, sort_keys=True)
        decoded = json.loads(encoded)
        restored = ScoreboardRecord.from_dict(decoded)

        self.assertEqual(restored, record)
        self.assertEqual(
            data["triage_category_counts"],
            [{"category": "clean", "count": 1}],
        )
        self.assertEqual(data["metadata"], {"a": "1", "b": "2"})

    def test_write_append_and_read_jsonl_records_preserve_order(self) -> None:
        first = build_scoreboard_record(
            batch_result(result(seed=1, final_rank=1, final_score=10.0)),
            agent_name="candidate",
            scenario_set="first",
        )
        second = build_scoreboard_record(
            batch_result(result(seed=2, final_rank=2, final_score=1.0)),
            agent_name="candidate",
            scenario_set="second",
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scoreboard" / "records.jsonl"
            returned_write_path = write_scoreboard_record(first, path)
            returned_append_path = append_scoreboard_record(second, path)
            raw_lines = path.read_text(encoding="utf-8").splitlines()
            records = read_scoreboard_records(path)

        self.assertEqual(returned_write_path, path)
        self.assertEqual(returned_append_path, path)
        self.assertEqual(len(raw_lines), 2)
        self.assertTrue(all(line.startswith("{") and line.endswith("}") for line in raw_lines))
        self.assertEqual(records, (first, second))

    def test_write_scoreboard_record_replaces_existing_file(self) -> None:
        first = ScoreboardRecord(
            agent_name="candidate",
            agent_version=None,
            commit=None,
            scenario_set="first",
        )
        second = ScoreboardRecord(
            agent_name="candidate",
            agent_version=None,
            commit=None,
            scenario_set="second",
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "records.jsonl"
            write_scoreboard_record(first, path)
            write_scoreboard_record(second, path)
            records = read_scoreboard_records(path)

        self.assertEqual(records, (second,))

    def test_read_scoreboard_records_rejects_non_object_json_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "records.jsonl"
            path.write_text("[]\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "line 1 must contain"):
                read_scoreboard_records(path)

    def test_scoreboard_build_does_not_run_matches(self) -> None:
        with patch("ow_eval.official_runner.run_official_match") as run_match:
            build_scoreboard_record(
                batch_result(result(final_rank=1)),
                agent_name="candidate",
                scenario_set="no-run",
            )

        run_match.assert_not_called()


if __name__ == "__main__":
    unittest.main()
