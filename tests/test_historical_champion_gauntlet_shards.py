"""Tests for historical champion gauntlet shard planning."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from ow_eval import ExperimentManifest
from ow_eval.historical_gauntlet_shards import (
    HistoricalChampionShardPlan,
    build_historical_champion_shard_plan,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "experiments" / "historical_champions" / "registry.json"
MANIFEST_PATHS = (
    REPO_ROOT / "experiments" / "manifests" / "historical-champion-gauntlet-2p-500.json",
    REPO_ROOT / "experiments" / "manifests" / "historical-champion-gauntlet-4p-500.json",
)


def load_manifest(path: Path) -> ExperimentManifest:
    return ExperimentManifest.from_dict(json.loads(path.read_text(encoding="utf-8")))


def committed_scenario_labels() -> tuple[str, ...]:
    labels: list[str] = []
    for path in MANIFEST_PATHS:
        manifest = load_manifest(path)
        labels.extend(scenario.label or "" for scenario in manifest.scenarios)
    return tuple(labels)


def registry_names_by_status(status: str) -> set[str]:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    return {
        entry["name"]
        for entry in registry["entries"]
        if entry["loadability_status"] == status
    }


class HistoricalChampionGauntletShardPlanTests(unittest.TestCase):
    def test_plan_is_deterministic_and_json_safe(self) -> None:
        first = build_historical_champion_shard_plan()
        second = build_historical_champion_shard_plan()

        self.assertEqual(first, second)
        self.assertEqual(json.loads(json.dumps(first.to_dict())), first.to_dict())
        self.assertEqual(
            first.summary_text,
            (
                "historical_champion_shard_plan shards=6 total_scenarios=30 "
                "scenarios_per_shard=5,5,5,5,5,5 "
                "recommended_probe_shard=historical-gauntlet-shard-000"
            ),
        )

    def test_all_committed_scenarios_are_assigned_exactly_once(self) -> None:
        plan = build_historical_champion_shard_plan()
        planned_labels = tuple(
            scenario.scenario_label
            for shard in plan.shards
            for scenario in shard.scenarios
        )

        self.assertEqual(plan.total_scenarios, 30)
        self.assertEqual(len(planned_labels), 30)
        self.assertEqual(len(set(planned_labels)), 30)
        self.assertEqual(set(planned_labels), set(committed_scenario_labels()))

    def test_shards_are_balanced_and_stably_identified(self) -> None:
        plan = build_historical_champion_shard_plan()

        self.assertEqual(plan.shard_count, 6)
        self.assertEqual(
            tuple(shard.shard_id for shard in plan.shards),
            tuple(f"historical-gauntlet-shard-{index:03d}" for index in range(6)),
        )
        self.assertEqual(tuple(shard.scenario_count for shard in plan.shards), (5, 5, 5, 5, 5, 5))
        self.assertEqual(plan.recommended_probe_shard_id, "historical-gauntlet-shard-000")
        self.assertTrue(plan.shards[0].recommended_for_probe)
        self.assertFalse(any(shard.recommended_for_probe for shard in plan.shards[1:]))

    def test_every_planned_scenario_keeps_full_horizon_metadata(self) -> None:
        plan = build_historical_champion_shard_plan()

        for shard in plan.shards:
            with self.subTest(shard=shard.shard_id):
                self.assertTrue(shard.intended_manifest_path.endswith("/manifest.json"))
                self.assertTrue(shard.intended_result_path.endswith("/shard-result.json"))
                self.assertTrue(shard.intended_report_path.endswith("/report.json"))
                for scenario in shard.scenarios:
                    self.assertEqual(scenario.episode_steps, "500")
                    self.assertIn(scenario.player_count, (2, 4))
                    self.assertGreaterEqual(scenario.seed, 0)
                    self.assertGreaterEqual(scenario.controlled_seat, 0)
                    self.assertTrue(scenario.opponent_names)
                    self.assertTrue(Path(scenario.source_manifest_path).is_file())

    def test_plan_does_not_schedule_skipped_registry_entries(self) -> None:
        plan = build_historical_champion_shard_plan()
        skipped_names = registry_names_by_status("skipped")
        loadable_names = registry_names_by_status("loadable")
        scheduled_names = {
            opponent_name
            for shard in plan.shards
            for scenario in shard.scenarios
            for opponent_name in scenario.opponent_names
        }

        self.assertTrue(scheduled_names <= loadable_names)
        self.assertFalse(scheduled_names & skipped_names)

    def test_custom_shard_count_remains_deterministic(self) -> None:
        plan = build_historical_champion_shard_plan(shard_count=4)

        self.assertEqual(plan.shard_count, 4)
        self.assertEqual(tuple(shard.scenario_count for shard in plan.shards), (8, 8, 7, 7))
        self.assertEqual(plan.total_scenarios, 30)

    def test_invalid_shard_count_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "shard_count must be positive"):
            build_historical_champion_shard_plan(shard_count=0)

    def test_missing_manifest_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "manifest not found"):
            build_historical_champion_shard_plan(
                manifest_paths=(REPO_ROOT / "missing-gauntlet.json",),
            )


if __name__ == "__main__":
    unittest.main()
