"""Tests for fallback source-guard A/B Daytona packaging."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

from ow_eval.shard_index_runner import read_evaluation_shard_job_index


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PREPARE_SCRIPT = _load_script(
    "prepare_fallback_source_guard_ab_daytona_package",
    REPO_ROOT / "scripts" / "prepare_fallback_source_guard_ab_daytona_package.py",
)


class FallbackSourceGuardABDaytonaTests(unittest.TestCase):
    def test_package_contains_two_cells_and_twelve_full_horizon_matches(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "ab"

            summary = PREPARE_SCRIPT.prepare_fallback_source_guard_ab_package(
                output_root,
            )
            index = read_evaluation_shard_job_index(summary["index_path"])

            self.assertEqual(summary["jobs"], 4)
            self.assertEqual(summary["matches"], 12)
            self.assertEqual(summary["episode_steps"], ["500"])
            self.assertEqual(len(index.jobs), 4)
            self.assertEqual([len(job.match_labels) for job in index.jobs], [3, 3, 3, 3])

            manifest_text = "\n".join(
                Path(job.manifest_path).read_text(encoding="utf-8")
                for job in index.jobs
            )

            self.assertIn("historical_opponents/agents/claude_v3_wide_search_forecast.py", manifest_text)
            self.assertIn("agents.fallback_source_guard", manifest_text)
            self.assertIn("fallback_source_guard_ab_cell", manifest_text)
            self.assertIn("base-historical-gauntlet-2p-500", manifest_text)
            self.assertIn("source-guard-historical-gauntlet-4p-500", manifest_text)


if __name__ == "__main__":
    unittest.main()
