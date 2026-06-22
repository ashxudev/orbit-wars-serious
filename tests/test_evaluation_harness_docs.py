"""Guardrail tests for the evaluation harness runbook."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNBOOK = REPO_ROOT / "docs" / "evaluation-harness.md"
DOCUMENTED_SCRIPTS = (
    "scripts/build_submission.py",
    "scripts/evaluation_gate.py",
    "scripts/profile_tests.py",
    "scripts/run_evaluation_experiment.py",
    "scripts/run_evaluation_suite.py",
    "scripts/run_tests_parallel.py",
    "scripts/submission_preflight.py",
)
HELP_SCRIPTS = (
    "scripts/build_submission.py",
    "scripts/profile_tests.py",
    "scripts/run_evaluation_experiment.py",
    "scripts/run_evaluation_suite.py",
    "scripts/run_tests_parallel.py",
    "scripts/submission_preflight.py",
)
MANIFEST_FIXTURES = (
    "experiments/manifests/quick-2p-smoke.json",
    "experiments/manifests/quick-4p-smoke.json",
    "experiments/manifests/promotion-smoke.json",
)
KEY_COMMANDS = (
    ".venv/bin/python -m unittest discover -s tests",
    ".venv/bin/python scripts/run_tests_parallel.py --workers 6",
    ".venv/bin/python scripts/profile_tests.py --top 20",
    ".venv/bin/python scripts/build_submission.py --output /tmp/orbit_wars_submission.py",
    ".venv/bin/python scripts/evaluation_gate.py",
    ".venv/bin/python scripts/run_evaluation_experiment.py experiments/manifests/quick-2p-smoke.json",
    ".venv/bin/python scripts/run_evaluation_suite.py",
    ".venv/bin/python scripts/submission_preflight.py",
)


class EvaluationHarnessDocsTests(unittest.TestCase):
    def test_runbook_exists(self) -> None:
        self.assertTrue(RUNBOOK.is_file())

    def test_documented_script_paths_exist_and_are_mentioned(self) -> None:
        text = RUNBOOK.read_text(encoding="utf-8")

        for script in DOCUMENTED_SCRIPTS:
            with self.subTest(script=script):
                self.assertTrue((REPO_ROOT / script).is_file())
                self.assertIn(script, text)

    def test_documented_manifest_fixture_paths_exist_and_are_mentioned(self) -> None:
        text = RUNBOOK.read_text(encoding="utf-8")

        for fixture in MANIFEST_FIXTURES:
            with self.subTest(fixture=fixture):
                self.assertTrue((REPO_ROOT / fixture).is_file())
                self.assertIn(fixture, text)

    def test_key_commands_appear_in_runbook(self) -> None:
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

    def test_runbook_states_local_not_live_and_artifact_policy(self) -> None:
        text = RUNBOOK.read_text(encoding="utf-8").lower()

        self.assertIn("local evaluation", text)
        self.assertIn("not submit to live kaggle", text)
        self.assertIn("live kaggle competition submissions", text)
        self.assertIn("generated submissions", text)
        self.assertIn("should not be committed", text)
        self.assertIn("scripts/submission_preflight.py", text)


if __name__ == "__main__":
    unittest.main()
