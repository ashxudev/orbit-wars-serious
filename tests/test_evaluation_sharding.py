"""Tests for deterministic evaluation shard planning contracts."""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch

from ow_eval import (
    EvaluationShard,
    EvaluationShardPlan,
    ExperimentManifest,
    MatchConfig,
    ShardPlanConfig,
    build_evaluation_shard_plan,
    manifest_to_match_configs,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = REPO_ROOT / "experiments" / "manifests"
QUICK_2P = MANIFEST_DIR / "quick-2p-smoke.json"
QUICK_4P = MANIFEST_DIR / "quick-4p-smoke.json"
PROMOTION = MANIFEST_DIR / "promotion-smoke.json"


def load_manifest(path: Path) -> ExperimentManifest:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return ExperimentManifest.from_dict(payload)


class EvaluationShardingTests(unittest.TestCase):
    def test_module_imports_and_exports_are_available(self) -> None:
        import ow_eval.sharding as sharding

        self.assertIs(sharding.EvaluationShard, EvaluationShard)
        self.assertIs(sharding.EvaluationShardPlan, EvaluationShardPlan)
        self.assertIs(sharding.ShardPlanConfig, ShardPlanConfig)
        self.assertIs(sharding.build_evaluation_shard_plan, build_evaluation_shard_plan)

    def test_config_and_plan_objects_are_frozen_slotted_and_validate(self) -> None:
        config = ShardPlanConfig(shard_count=1)
        match = manifest_to_match_configs(load_manifest(QUICK_2P))[0]
        shard = EvaluationShard(
            shard_id="shard-0000",
            label="test-0000",
            source_manifest_refs=("manifest",),
            match_labels=("match",),
            seeds=(7,),
            matches=(match,),
            planned_manifest_path="/tmp/test-0000.manifest.json",
            planned_report_path="/tmp/test-0000.report.json",
            command="python script.py",
        )
        plan = EvaluationShardPlan(
            config=config,
            shards=(shard,),
            total_matches=1,
            summary_text="summary",
        )

        with self.assertRaises(FrozenInstanceError):
            config.shard_count = 2  # type: ignore[misc]
        with self.assertRaises((AttributeError, TypeError)):
            config.extra = "nope"  # type: ignore[attr-defined]
        with self.assertRaises(FrozenInstanceError):
            shard.label = "changed"  # type: ignore[misc]
        with self.assertRaises((AttributeError, TypeError)):
            plan.extra = "nope"  # type: ignore[attr-defined]
        with self.assertRaisesRegex(ValueError, "config"):
            EvaluationShardPlan(
                config="bad",  # type: ignore[arg-type]
                shards=(),
                total_matches=0,
                summary_text="summary",
            )
        with self.assertRaisesRegex(ValueError, "matches"):
            EvaluationShard(
                shard_id="shard-0000",
                label="test-0000",
                source_manifest_refs=("manifest",),
                match_labels=("match",),
                seeds=(7,),
                matches=("bad",),  # type: ignore[arg-type]
                planned_manifest_path="/tmp/test-0000.manifest.json",
                planned_report_path="/tmp/test-0000.report.json",
                command="python script.py",
            )

    def test_partition_by_shard_count_preserves_match_order_and_commands(self) -> None:
        config = ShardPlanConfig(
            shard_count=2,
            output_root="/tmp/ow-shards",
            label_prefix="local",
        )

        plan = build_evaluation_shard_plan((QUICK_2P, QUICK_4P), config)

        self.assertEqual(plan.total_matches, 4)
        self.assertEqual(tuple(shard.match_count for shard in plan.shards), (2, 2))
        self.assertEqual(tuple(shard.shard_id for shard in plan.shards), ("shard-0000", "shard-0001"))
        self.assertEqual(tuple(shard.label for shard in plan.shards), ("local-0000", "local-0001"))
        self.assertEqual(
            tuple(shard.match_labels for shard in plan.shards),
            (
                ("quick-2p-seed-7-seat-0", "quick-2p-seed-8-seat-0"),
                ("quick-4p-seed-7-seat-0", "quick-4p-seed-8-seat-2"),
            ),
        )
        self.assertEqual(
            tuple(shard.source_manifest_refs for shard in plan.shards),
            ((str(QUICK_2P),), (str(QUICK_4P),)),
        )
        self.assertEqual(tuple(shard.seeds for shard in plan.shards), ((7, 8), (7, 8)))
        self.assertEqual(
            plan.shards[0].command,
            (
                ".venv/bin/python scripts/run_evaluation_experiment.py "
                "/tmp/ow-shards/local-0000.manifest.json "
                "--report-output /tmp/ow-shards/local-0000.report.json"
            ),
        )
        self.assertEqual(
            plan.summary_text,
            "shard_plan=READY shards=2 matches=4 strategy=shard_count=2",
        )

    def test_partition_by_matches_per_shard_preserves_contiguous_chunks(self) -> None:
        config = ShardPlanConfig(
            matches_per_shard=3,
            output_root="/tmp/ow-shards",
            label_prefix="chunk",
        )

        plan = build_evaluation_shard_plan((QUICK_2P, PROMOTION), config)

        self.assertEqual(plan.total_matches, 5)
        self.assertEqual(tuple(shard.match_count for shard in plan.shards), (3, 2))
        self.assertEqual(tuple(shard.label for shard in plan.shards), ("chunk-0000", "chunk-0001"))
        self.assertEqual(
            plan.shards[0].match_labels,
            (
                "quick-2p-seed-7-seat-0",
                "quick-2p-seed-8-seat-0",
                "promotion-2p-seed-7-seat-0",
            ),
        )
        self.assertEqual(
            plan.shards[0].source_manifest_refs,
            (str(QUICK_2P), str(PROMOTION)),
        )
        self.assertEqual(
            plan.summary_text,
            "shard_plan=READY shards=2 matches=5 strategy=matches_per_shard=3",
        )

    def test_manifest_objects_and_direct_match_configs_are_supported(self) -> None:
        manifest = load_manifest(QUICK_2P)
        direct_match = manifest_to_match_configs(load_manifest(QUICK_4P))[0]

        plan = build_evaluation_shard_plan(
            (manifest, direct_match),
            ShardPlanConfig(matches_per_shard=2, output_root="/tmp/ow-shards"),
        )

        self.assertEqual(plan.total_matches, 3)
        self.assertEqual(len(plan.shards), 2)
        self.assertEqual(
            plan.shards[0].source_manifest_refs,
            (manifest.name,),
        )
        self.assertEqual(
            plan.shards[1].source_manifest_refs,
            ("match-config",),
        )
        self.assertTrue(all(isinstance(match, MatchConfig) for shard in plan.shards for match in shard.matches))

    def test_invalid_configs_and_empty_inputs_raise_clear_errors(self) -> None:
        with self.assertRaisesRegex(ValueError, "exactly one"):
            ShardPlanConfig()
        with self.assertRaisesRegex(ValueError, "exactly one"):
            ShardPlanConfig(shard_count=2, matches_per_shard=2)
        with self.assertRaisesRegex(ValueError, "shard_count"):
            ShardPlanConfig(shard_count=0)
        with self.assertRaisesRegex(ValueError, "matches_per_shard"):
            ShardPlanConfig(matches_per_shard=-1)
        with self.assertRaisesRegex(ValueError, "shard_count"):
            ShardPlanConfig(shard_count=True)  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "inputs"):
            build_evaluation_shard_plan((), ShardPlanConfig(shard_count=1))
        with self.assertRaisesRegex(ValueError, "inputs"):
            build_evaluation_shard_plan("not-a-sequence", ShardPlanConfig(shard_count=1))  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "unsupported type"):
            build_evaluation_shard_plan((object(),), ShardPlanConfig(shard_count=1))  # type: ignore[arg-type]

    def test_plan_to_dict_is_json_safe_and_stable(self) -> None:
        plan = build_evaluation_shard_plan(
            (QUICK_2P,),
            ShardPlanConfig(shard_count=1, output_root="/tmp/ow-shards"),
        )

        encoded = json.dumps(plan.to_dict(), sort_keys=True)
        decoded = json.loads(encoded)

        self.assertEqual(decoded["total_matches"], 2)
        self.assertEqual(decoded["config"]["shard_count"], 1)
        self.assertEqual(decoded["shards"][0]["match_count"], 2)
        self.assertEqual(
            decoded["shards"][0]["match_labels"],
            ["quick-2p-seed-7-seat-0", "quick-2p-seed-8-seat-0"],
        )
        self.assertEqual(decoded, plan.to_dict())

    def test_building_plan_does_not_write_outputs_run_matches_or_call_daytona(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "planned-output"

            with patch("ow_eval.official_runner.run_official_match") as official_runner:
                plan = build_evaluation_shard_plan(
                    (QUICK_2P,),
                    ShardPlanConfig(shard_count=1, output_root=output_root),
                )

            self.assertEqual(plan.total_matches, 2)
            official_runner.assert_not_called()
            self.assertFalse(output_root.exists())


if __name__ == "__main__":
    unittest.main()
