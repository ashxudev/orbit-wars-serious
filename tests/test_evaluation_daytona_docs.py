"""Guardrail tests for the distributed evaluation / Daytona runbook."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNBOOK = REPO_ROOT / "docs" / "distributed-evaluation-daytona.md"
DOCUMENTED_SCRIPTS = (
    "scripts/run_evaluation_shards.py",
    "scripts/prepare_evaluation_shards.py",
    "scripts/run_evaluation_shard_job.py",
    "scripts/run_evaluation_shard_index.py",
    "scripts/prepare_daytona_shard_jobs.py",
    "scripts/validate_daytona_shard_jobs.py",
    "scripts/run_daytona_shard_jobs.py",
    "scripts/run_daytona_client_report.py",
    "scripts/run_daytona_real_shard_jobs.py",
)
HELP_SCRIPTS = (
    "scripts/prepare_evaluation_shards.py",
    "scripts/prepare_daytona_shard_jobs.py",
    "scripts/validate_daytona_shard_jobs.py",
    "scripts/run_daytona_shard_jobs.py",
    "scripts/run_daytona_client_report.py",
    "scripts/run_daytona_real_shard_jobs.py",
)
MANIFEST_FIXTURES = (
    "experiments/manifests/quick-2p-smoke.json",
    "experiments/manifests/quick-4p-smoke.json",
    "experiments/manifests/promotion-smoke.json",
)
KEY_COMMANDS = (
    ".venv/bin/python scripts/run_evaluation_shards.py experiments/manifests/quick-2p-smoke.json --shard-count 2",
    ".venv/bin/python scripts/prepare_evaluation_shards.py experiments/manifests/quick-2p-smoke.json --shard-count 2 --output-dir /tmp/ow-eval-shards",
    ".venv/bin/python scripts/run_evaluation_shard_index.py /tmp/ow-eval-shards/shard-jobs.index.json",
    ".venv/bin/python scripts/prepare_daytona_shard_jobs.py /tmp/ow-eval-shards/shard-jobs.index.json --output-path /tmp/ow-eval-shards/daytona-shard-jobs.json",
    ".venv/bin/python scripts/validate_daytona_shard_jobs.py /tmp/ow-eval-shards/daytona-shard-jobs.json",
    ".venv/bin/python scripts/run_daytona_shard_jobs.py /tmp/ow-eval-shards/daytona-shard-jobs.json --dry-run --no-upload-path-existence-check",
    ".venv/bin/python scripts/run_daytona_client_report.py /tmp/ow-eval-shards/daytona-shard-jobs.json --dry-run --no-upload-path-existence-check",
    ".venv/bin/python scripts/run_daytona_real_shard_jobs.py /tmp/ow-eval-shards/daytona-shard-jobs.json --allow-real-daytona",
)


class EvaluationDaytonaDocsTests(unittest.TestCase):
    def test_runbook_exists(self) -> None:
        self.assertTrue(RUNBOOK.is_file())

    def test_documented_script_paths_exist_and_are_mentioned(self) -> None:
        text = RUNBOOK.read_text(encoding="utf-8")

        for script in DOCUMENTED_SCRIPTS:
            with self.subTest(script=script):
                self.assertTrue((REPO_ROOT / script).is_file())
                self.assertIn(script, text)

    def test_manifest_fixture_paths_exist_and_are_mentioned(self) -> None:
        text = RUNBOOK.read_text(encoding="utf-8")

        for fixture in MANIFEST_FIXTURES:
            with self.subTest(fixture=fixture):
                self.assertTrue((REPO_ROOT / fixture).is_file())
                self.assertIn(fixture, text)

    def test_key_commands_appear_exactly_in_runbook(self) -> None:
        text = RUNBOOK.read_text(encoding="utf-8")

        for command in KEY_COMMANDS:
            with self.subTest(command=command):
                self.assertIn(command, text)

    def test_help_supported_cli_scripts_expose_help_successfully(self) -> None:
        for script in HELP_SCRIPTS:
            with self.subTest(script=script):
                completed = subprocess.run(
                    [sys.executable, script, "--help"],
                    cwd=REPO_ROOT,
                    check=False,
                    capture_output=True,
                    text=True,
                )

                self.assertEqual(completed.returncode, 0)
                self.assertIn("usage:", completed.stdout)
                self.assertEqual(completed.stderr, "")

    def test_runbook_states_local_fake_real_safety_and_artifact_policy(self) -> None:
        text = RUNBOOK.read_text(encoding="utf-8").lower()

        self.assertIn("local-only", text)
        self.assertIn("fake daytona dry-runs", text)
        self.assertIn("guarded real-daytona", text)
        self.assertIn("ow_eval_allow_real_daytona", text)
        self.assertIn("--allow-real-daytona", text)
        self.assertIn("both env readiness and `--allow-real-daytona`", text)
        self.assertIn("no live kaggle submissions", text)
        self.assertIn("does not submit to live kaggle", text)
        self.assertIn("should not be committed", text)
        self.assertIn("generated plans", text)
        self.assertIn("missing upload paths", text)
        self.assertIn("duplicate sandbox names", text)
        self.assertIn("missing env/token", text)
        self.assertIn("blocked readiness", text)
        self.assertIn("no-op-heavy regression gate failures", text)


if __name__ == "__main__":
    unittest.main()
