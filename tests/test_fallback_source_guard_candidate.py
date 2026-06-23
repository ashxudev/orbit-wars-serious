"""Tests for the fallback source-guard reserve candidate."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from agents import fallback_source_guard
from scripts import build_fallback_source_guard_submission


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "kaggle_seed7_2p_step0.json"


class FallbackSourceGuardCandidateTests(unittest.TestCase):
    def test_build_source_is_deterministic_and_contains_guard(self) -> None:
        first = fallback_source_guard.build_source()
        second = fallback_source_guard.build_source()

        self.assertEqual(first, second)
        self.assertIn("SOURCE_LOSS_GUARD_TICKS = 24", first)
        self.assertIn("SHORT_HOLD_GUARD_TICKS = 28", first)
        self.assertIn("newly_lost_source", first)
        self.assertIn("already_doomed_source", first)
        self.assertIn("held_for = fl2 - fg2", first)

    def test_candidate_agent_returns_legal_shape_for_seed_fixture(self) -> None:
        observation = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

        actions = fallback_source_guard.agent(observation, {})

        self.assertIsInstance(actions, list)
        self.assertTrue(actions)
        for action in actions:
            self.assertIsInstance(action, list)
            self.assertEqual(len(action), 3)
            self.assertIsInstance(action[0], int)
            self.assertIsInstance(action[1], float)
            self.assertIsInstance(action[2], int)

    def test_standalone_builder_writes_importable_agent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "fallback_source_guard.py"

            build_fallback_source_guard_submission.write_submission(output_path)

            self.assertEqual(
                hashlib.sha256(output_path.read_bytes()).hexdigest(),
                hashlib.sha256(
                    fallback_source_guard.build_source().encode("utf-8")
                ).hexdigest(),
            )
            spec = importlib.util.spec_from_file_location(
                "fallback_source_guard_submission",
                output_path,
            )
            self.assertIsNotNone(spec)
            self.assertIsNotNone(spec.loader)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            observation = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

            self.assertEqual(
                module.agent(observation, {}),
                fallback_source_guard.agent(observation, {}),
            )

    def test_builder_cli_writes_output_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "submission.py"
            result = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "build_fallback_source_guard_submission.py"),
                    "--output",
                    str(output_path),
                ],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.stdout, "")
            self.assertEqual(result.stderr, "")
            self.assertTrue(output_path.is_file())

    def test_already_doomed_productive_source_attack_is_rejected(self) -> None:
        observation = {
            "step": 0,
            "player": 0,
            "remainingOverageTime": 60,
            "angular_velocity": 0.0,
            "comet_planet_ids": [],
            "comets": [],
            "next_fleet_id": 2,
            "initial_planets": [],
            "planets": [
                [0, 0, 60.0, 20.0, 3.0, 80, 4],
                [1, 1, 85.0, 20.0, 3.0, 10, 5],
                [2, 1, 10.0, 70.0, 3.0, 10, 1],
            ],
            "fleets": [
                [0, 1, 22.0, 20.0, 0.0, 1, 150],
            ],
        }

        self.assertEqual(fallback_source_guard.agent(observation, {}), [])


if __name__ == "__main__":
    unittest.main()
