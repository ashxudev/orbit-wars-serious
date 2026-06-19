"""Tests for Evaluation Harness Cycle 11 planner analysis packs."""

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
    FailureCategory,
    MatchConfig,
    MatchMetrics,
    MatchResult,
    OpponentSpec,
    PlannerAnalysisItem,
    PlannerAnalysisPack,
    PlannerAnalysisPackConfig,
    PlayerCount,
    build_planner_analysis_pack,
)


def match_config(
    *,
    seed: int = 7,
    label: str | None = "analysis",
    metadata: tuple[tuple[str, str], ...] = (),
) -> MatchConfig:
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
        metadata=metadata,
    )


def result(
    *,
    seed: int = 7,
    label: str | None = "analysis",
    status: EvaluationStatus = EvaluationStatus.COMPLETED,
    final_rank: int | None = 1,
    final_score: float | None = 10.0,
    final_planets: int | None = 3,
    final_ships: int | None = 100,
    final_production: int | None = 5,
    turns_survived: int | None = 100,
    no_action_count: int | None = 0,
    invalid_action_count: int | None = 0,
    timeout_count: int | None = 0,
    error_count: int | None = 0,
    error_text: str | None = None,
    replay_path: str | None = None,
    artifact_path: str | None = None,
    config_metadata: tuple[tuple[str, str], ...] = (),
    result_metadata: tuple[tuple[str, str], ...] = (),
) -> MatchResult:
    return MatchResult(
        config=match_config(seed=seed, label=label, metadata=config_metadata),
        status=status,
        metrics=MatchMetrics(
            final_rank=final_rank,
            final_score=final_score,
            final_planets=final_planets,
            final_ships=final_ships,
            final_production=final_production,
            turns_survived=turns_survived,
            no_action_count=no_action_count,
            invalid_action_count=invalid_action_count,
            timeout_count=timeout_count,
            error_count=error_count,
        ),
        error_text=error_text,
        replay_path=replay_path,
        artifact_path=artifact_path,
        metadata=result_metadata,
    )


def batch_result(*results: MatchResult) -> EvaluationBatchResult:
    return EvaluationBatchResult(results=tuple(results))


class EvaluationAnalysisPackTests(unittest.TestCase):
    def test_analysis_pack_module_imports_and_exports_are_available(self) -> None:
        module = importlib.import_module("ow_eval.analysis_pack")

        self.assertIs(module.PlannerAnalysisPackConfig, PlannerAnalysisPackConfig)
        self.assertIs(module.PlannerAnalysisItem, PlannerAnalysisItem)
        self.assertIs(module.PlannerAnalysisPack, PlannerAnalysisPack)
        self.assertIs(module.build_planner_analysis_pack, build_planner_analysis_pack)

    def test_analysis_pack_contracts_are_frozen_slotted_and_validate(self) -> None:
        config = PlannerAnalysisPackConfig(max_items=1)
        item = PlannerAnalysisItem(
            batch_index=0,
            label="item",
            seed=7,
            player_count=2,
            controlled_seat=0,
            candidate_agent_name="candidate",
            opponent_names=("opponent",),
            status=EvaluationStatus.COMPLETED,
            triage_category=FailureCategory.NORMAL_LOSS,
            triage_reason="loss",
        )
        pack = PlannerAnalysisPack(items=(item,), total_results=1, included_count=1)

        with self.assertRaises(FrozenInstanceError):
            config.max_items = 2  # type: ignore[misc]
        with self.assertRaises((AttributeError, TypeError)):
            item.extra = "nope"  # type: ignore[attr-defined]
        with self.assertRaises(FrozenInstanceError):
            pack.total_results = 2  # type: ignore[misc]
        with self.assertRaisesRegex(ValueError, "max_items"):
            PlannerAnalysisPackConfig(max_items=-1)
        with self.assertRaisesRegex(ValueError, "batch_index"):
            PlannerAnalysisItem(
                batch_index=-1,
                label=None,
                seed=7,
                player_count=2,
                controlled_seat=0,
                candidate_agent_name="candidate",
                opponent_names=(),
                status=EvaluationStatus.COMPLETED,
                triage_category=FailureCategory.CLEAN,
                triage_reason="clean",
            )

    def test_clean_wins_are_omitted_by_default(self) -> None:
        pack = build_planner_analysis_pack(batch_result(result(final_rank=1)))

        self.assertEqual(pack.items, ())
        self.assertEqual(pack.total_results, 1)
        self.assertEqual(pack.included_count, 0)
        self.assertEqual(pack.omitted_count, 1)
        self.assertEqual(pack.triage_category_counts, ())

    def test_clean_wins_can_be_included_when_configured(self) -> None:
        pack = build_planner_analysis_pack(
            batch_result(result(final_rank=1)),
            PlannerAnalysisPackConfig(include_clean_wins=True),
        )

        self.assertEqual(len(pack.items), 1)
        self.assertEqual(pack.items[0].triage_category, FailureCategory.CLEAN)
        self.assertEqual(pack.triage_category_counts, (("clean", 1),))

    def test_completed_losses_are_included_with_match_context(self) -> None:
        pack = build_planner_analysis_pack(
            batch_result(
                result(
                    seed=11,
                    label="loss",
                    final_rank=2,
                    final_score=3.5,
                    final_planets=1,
                    final_ships=42,
                    final_production=2,
                )
            )
        )

        self.assertEqual(len(pack.items), 1)
        item = pack.items[0]
        self.assertEqual(item.batch_index, 0)
        self.assertEqual(item.label, "loss")
        self.assertEqual(item.seed, 11)
        self.assertEqual(item.player_count, 2)
        self.assertEqual(item.controlled_seat, 0)
        self.assertEqual(item.candidate_agent_name, "candidate")
        self.assertEqual(item.opponent_names, ("opponent",))
        self.assertEqual(item.status, EvaluationStatus.COMPLETED)
        self.assertEqual(item.triage_category, FailureCategory.NORMAL_LOSS)
        self.assertEqual(item.triage_reason, "completed with losing final rank")
        self.assertEqual(item.final_rank, 2)
        self.assertEqual(item.final_score, 3.5)
        self.assertEqual(item.final_planets, 1)
        self.assertEqual(item.final_ships, 42)
        self.assertEqual(item.final_production, 2)

    def test_severe_triage_categories_are_included(self) -> None:
        pack = build_planner_analysis_pack(
            batch_result(
                result(
                    status=EvaluationStatus.AGENT_ERROR,
                    final_rank=None,
                    final_score=None,
                    error_text="RuntimeError: evaluation failed",
                )
            )
        )

        self.assertEqual(len(pack.items), 1)
        self.assertEqual(pack.items[0].triage_category, FailureCategory.PLANNER_CRASH)
        self.assertEqual(pack.items[0].error_text, "RuntimeError: evaluation failed")

    def test_noop_heavy_completed_behavior_is_included(self) -> None:
        pack = build_planner_analysis_pack(
            batch_result(
                result(
                    final_rank=1,
                    no_action_count=90,
                    turns_survived=100,
                )
            )
        )

        self.assertEqual(len(pack.items), 1)
        self.assertEqual(
            pack.items[0].triage_category,
            FailureCategory.INVALID_OR_NOOP_HEAVY_BEHAVIOR,
        )
        self.assertEqual(pack.items[0].no_action_count, 90)
        self.assertEqual(pack.items[0].turns_survived, 100)

    def test_paths_and_selected_metadata_are_preserved(self) -> None:
        pack = build_planner_analysis_pack(
            batch_result(
                result(
                    final_rank=2,
                    replay_path="/tmp/replay.json",
                    artifact_path="/tmp/result.json",
                    config_metadata=(
                        ("selected_mission", "target=3"),
                        ("ignored", "config"),
                    ),
                    result_metadata=(
                        ("selected_missions", "target=3;target=4"),
                        ("other", "result"),
                    ),
                )
            )
        )

        item = pack.items[0]
        self.assertEqual(item.replay_path, "/tmp/replay.json")
        self.assertEqual(item.artifact_path, "/tmp/result.json")
        self.assertEqual(
            item.selected_metadata,
            (
                ("selected_mission", "target=3"),
                ("selected_missions", "target=3;target=4"),
            ),
        )

    def test_runtime_diagnostic_metadata_is_preserved(self) -> None:
        pack = build_planner_analysis_pack(
            batch_result(
                result(
                    final_rank=1,
                    no_action_count=90,
                    turns_survived=100,
                    result_metadata=(
                        (
                            "runtime_diagnostic_primary_no_action_reason",
                            "strategy_selection_no_action",
                        ),
                        ("runtime_diagnostic_candidate_count_last", "4"),
                        ("other", "ignored"),
                    ),
                )
            )
        )

        item = pack.items[0]
        self.assertEqual(
            item.diagnostic_metadata,
            (
                (
                    "runtime_diagnostic_primary_no_action_reason",
                    "strategy_selection_no_action",
                ),
                ("runtime_diagnostic_candidate_count_last", "4"),
            ),
        )

    def test_ordering_and_max_items_are_deterministic(self) -> None:
        pack = build_planner_analysis_pack(
            batch_result(
                result(seed=1, label="first", final_rank=2),
                result(
                    seed=2,
                    label="second",
                    status=EvaluationStatus.AGENT_ERROR,
                    final_rank=None,
                    error_text="RuntimeError: evaluation failed",
                ),
                result(
                    seed=3,
                    label="third",
                    final_rank=1,
                    no_action_count=90,
                    turns_survived=100,
                ),
            ),
            PlannerAnalysisPackConfig(max_items=2),
        )

        self.assertEqual(tuple(item.batch_index for item in pack.items), (0, 1))
        self.assertEqual(tuple(item.label for item in pack.items), ("first", "second"))
        self.assertEqual(pack.included_count, 2)
        self.assertEqual(pack.omitted_count, 1)
        self.assertEqual(
            pack.triage_category_counts,
            (
                ("planner_crash", 1),
                ("normal_loss", 1),
            ),
        )

    def test_to_dict_output_is_json_safe_and_deterministic(self) -> None:
        pack = build_planner_analysis_pack(
            batch_result(
                result(
                    seed=5,
                    label="json",
                    final_rank=2,
                    config_metadata=(("selected_target", "5"),),
                )
            )
        )

        data = pack.to_dict()
        encoded = json.dumps(data, sort_keys=True)
        decoded = json.loads(encoded)

        self.assertEqual(decoded["total_results"], 1)
        self.assertEqual(decoded["included_count"], 1)
        self.assertEqual(decoded["items"][0]["status"], "completed")
        self.assertEqual(decoded["items"][0]["triage_category"], "normal_loss")
        self.assertEqual(
            decoded["items"][0]["selected_metadata"],
            [{"key": "selected_target", "value": "5"}],
        )
        self.assertEqual(decoded["items"][0]["diagnostic_metadata"], [])
        self.assertEqual(
            pack.summary_text(),
            "analysis_items=1 total=1 omitted=0 categories=normal_loss:1",
        )


if __name__ == "__main__":
    unittest.main()
