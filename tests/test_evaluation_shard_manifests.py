"""Tests for deterministic shard manifest materialization."""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from unittest.mock import patch

from ow_eval import (
    AgentSourceKind,
    AgentSpec,
    EvaluationShardManifestWriteResult,
    ExperimentManifest,
    ShardPlanConfig,
    build_evaluation_shard_plan,
    manifest_to_match_configs,
    shard_to_experiment_manifest,
    write_evaluation_shard_manifest,
    write_evaluation_shard_manifests,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = REPO_ROOT / "experiments" / "manifests"
QUICK_2P = MANIFEST_DIR / "quick-2p-smoke.json"
QUICK_4P = MANIFEST_DIR / "quick-4p-smoke.json"


def shard_plan(output_root: str | Path):
    return build_evaluation_shard_plan(
        (QUICK_2P, QUICK_4P),
        ShardPlanConfig(
            shard_count=2,
            output_root=output_root,
            label_prefix="materialized",
        ),
    )


class EvaluationShardManifestTests(unittest.TestCase):
    def test_module_imports_and_exports_are_available(self) -> None:
        import ow_eval.shard_manifests as shard_manifests

        self.assertIs(
            shard_manifests.EvaluationShardManifestWriteResult,
            EvaluationShardManifestWriteResult,
        )
        self.assertIs(
            shard_manifests.shard_to_experiment_manifest,
            shard_to_experiment_manifest,
        )
        self.assertIs(
            shard_manifests.write_evaluation_shard_manifest,
            write_evaluation_shard_manifest,
        )
        self.assertIs(
            shard_manifests.write_evaluation_shard_manifests,
            write_evaluation_shard_manifests,
        )

    def test_one_shard_converts_to_manifest_that_round_trips_to_matches(self) -> None:
        shard = shard_plan("/tmp/ow-shard-manifests").shards[0]

        manifest = shard_to_experiment_manifest(shard)

        self.assertIsInstance(manifest, ExperimentManifest)
        self.assertEqual(manifest.name, shard.label)
        self.assertEqual(manifest.candidate_agent, shard.matches[0].candidate_agent)
        self.assertEqual(manifest_to_match_configs(manifest), shard.matches)
        self.assertEqual(tuple(scenario.label for scenario in manifest.scenarios), shard.match_labels)
        self.assertEqual(tuple(scenario.seed for scenario in manifest.scenarios), shard.seeds)
        metadata = dict(manifest.metadata)
        self.assertEqual(metadata["shard_id"], shard.shard_id)
        self.assertEqual(metadata["shard_label"], shard.label)
        self.assertEqual(metadata["source_manifest_refs"], ",".join(shard.source_manifest_refs))
        self.assertEqual(metadata["match_labels"], ",".join(shard.match_labels))

    def test_full_plan_writes_one_manifest_per_shard_at_planned_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plan = shard_plan(Path(temp_dir) / "planned")

            result = write_evaluation_shard_manifests(plan)

            self.assertIs(result.shard_plan, plan)
            self.assertEqual(
                result.manifest_paths,
                tuple(shard.planned_manifest_path for shard in plan.shards),
            )
            self.assertEqual(result.commands, tuple(shard.command for shard in plan.shards))
            self.assertEqual(
                result.summary_text,
                "shard_manifests=WRITTEN shards=2 manifests=2",
            )
            for shard in plan.shards:
                path = Path(shard.planned_manifest_path)
                self.assertTrue(path.is_file())
                self.assertEqual(
                    path.read_text(encoding="utf-8"),
                    json.dumps(
                        shard_to_experiment_manifest(shard).to_dict(),
                        sort_keys=True,
                        indent=2,
                    )
                    + "\n",
                )
                payload = json.loads(path.read_text(encoding="utf-8"))
                manifest = ExperimentManifest.from_dict(payload)
                self.assertEqual(manifest_to_match_configs(manifest), shard.matches)

    def test_parent_directories_are_created_only_for_planned_manifest_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            plan = shard_plan(root / "planned")

            write_evaluation_shard_manifests(plan)

            self.assertEqual(
                sorted(
                    path.relative_to(root).as_posix()
                    for path in root.rglob("*")
                    if path.is_file()
                ),
                [
                    "planned/materialized-0000.manifest.json",
                    "planned/materialized-0001.manifest.json",
                ],
            )
            self.assertFalse((root / "planned" / "materialized-0000.report.json").exists())

    def test_write_result_is_frozen_slotted_validates_and_is_json_safe(self) -> None:
        plan = shard_plan("/tmp/ow-shard-manifests")
        result = EvaluationShardManifestWriteResult(
            shard_plan=plan,
            manifest_paths=("/tmp/a.json",),
            commands=("python script.py",),
            summary_text="summary",
        )

        with self.assertRaises(FrozenInstanceError):
            result.summary_text = "changed"  # type: ignore[misc]
        with self.assertRaises((AttributeError, TypeError)):
            result.extra = "nope"  # type: ignore[attr-defined]
        with self.assertRaisesRegex(ValueError, "shard_plan"):
            EvaluationShardManifestWriteResult(
                shard_plan="bad",  # type: ignore[arg-type]
                manifest_paths=(),
                commands=(),
                summary_text="summary",
            )
        with self.assertRaisesRegex(ValueError, "manifest_paths"):
            EvaluationShardManifestWriteResult(
                shard_plan=plan,
                manifest_paths=["/tmp/a.json"],  # type: ignore[arg-type]
                commands=(),
                summary_text="summary",
            )
        with self.assertRaisesRegex(ValueError, "commands"):
            EvaluationShardManifestWriteResult(
                shard_plan=plan,
                manifest_paths=(),
                commands=["python"],  # type: ignore[arg-type]
                summary_text="summary",
            )

        decoded = json.loads(json.dumps(result.to_dict(), sort_keys=True))
        self.assertEqual(decoded["manifest_paths"], ["/tmp/a.json"])
        self.assertEqual(decoded["commands"], ["python script.py"])
        self.assertEqual(decoded["shard_plan"]["total_matches"], 4)

    def test_malformed_inputs_raise_clear_errors(self) -> None:
        with self.assertRaisesRegex(ValueError, "shard"):
            shard_to_experiment_manifest("bad")  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "shard"):
            write_evaluation_shard_manifest("bad")  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "plan"):
            write_evaluation_shard_manifests("bad")  # type: ignore[arg-type]

    def test_mixed_candidate_agents_in_one_shard_fail_clearly(self) -> None:
        shard = shard_plan("/tmp/ow-shard-manifests").shards[0]
        other_agent = AgentSpec(
            name="other-agent",
            source_kind=AgentSourceKind.MODULAR_AGENT,
            module_path="agents.other_agent",
        )
        changed_match = replace(shard.matches[1], candidate_agent=other_agent)
        mixed_shard = replace(
            shard,
            matches=(shard.matches[0], changed_match),
        )

        with self.assertRaisesRegex(ValueError, "same candidate_agent"):
            shard_to_experiment_manifest(mixed_shard)

    def test_materialization_does_not_run_matches_spawn_subprocesses_or_call_daytona(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plan = shard_plan(Path(temp_dir) / "planned")

            with patch("ow_eval.official_runner.run_official_match") as official_runner:
                with patch("ow_eval.shard_runner.run_evaluation_batch") as batch_runner:
                    with patch("subprocess.run") as subprocess_run:
                        result = write_evaluation_shard_manifests(plan)

            self.assertEqual(len(result.manifest_paths), 2)
            official_runner.assert_not_called()
            batch_runner.assert_not_called()
            subprocess_run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
