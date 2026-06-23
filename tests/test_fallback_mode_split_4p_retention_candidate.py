"""Tests for the fallback 4P-retention mode-split candidate."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from agents import (
    fallback_mode_split_4p_retention,
    fallback_mode_split_retention,
    fallback_source_guard,
)
from scripts import build_fallback_mode_split_4p_retention_submission


REPO_ROOT = Path(__file__).resolve().parents[1]
TWO_P_FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "kaggle_seed7_2p_step0.json"
FOUR_P_FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "kaggle_seed7_4p_step0.json"


class FallbackModeSplit4PRetentionCandidateTests(unittest.TestCase):
    def test_build_source_is_deterministic_and_contains_selected_modes(self) -> None:
        first = fallback_mode_split_4p_retention.build_source()
        second = fallback_mode_split_4p_retention.build_source()

        self.assertEqual(first, second)
        self.assertIn("_SOURCE_GUARD_SOURCE", first)
        self.assertIn("_RESPONSE_MARGIN_RETENTION_SOURCE", first)
        self.assertIn("DEFENSE_MARGIN = 18", first)
        self.assertIn("MARGIN_ENEMY = 8", first)

    def test_player_count_detects_two_and_four_player_observations(self) -> None:
        two_p = json.loads(TWO_P_FIXTURE_PATH.read_text(encoding="utf-8"))
        four_p = json.loads(FOUR_P_FIXTURE_PATH.read_text(encoding="utf-8"))

        self.assertEqual(
            fallback_mode_split_4p_retention.player_count_for_observation(two_p),
            2,
        )
        self.assertEqual(
            fallback_mode_split_4p_retention.player_count_for_observation(four_p),
            4,
        )

    def test_two_player_dispatch_matches_source_guard(self) -> None:
        observation = json.loads(TWO_P_FIXTURE_PATH.read_text(encoding="utf-8"))

        self.assertEqual(
            fallback_mode_split_4p_retention.agent(observation, {}),
            fallback_source_guard.agent(observation, {}),
        )

    def test_four_player_dispatch_matches_retention_response_mode(self) -> None:
        observation = json.loads(FOUR_P_FIXTURE_PATH.read_text(encoding="utf-8"))
        response_margin_agent = fallback_mode_split_retention.generated_symbols[
            "_response_margin_namespace"
        ]["agent"]

        self.assertEqual(
            fallback_mode_split_4p_retention.agent(observation, {}),
            response_margin_agent(observation, {}),
        )

    def test_standalone_builder_writes_importable_agent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "fallback_mode_split_4p_retention.py"

            build_fallback_mode_split_4p_retention_submission.write_submission(
                output_path,
            )

            self.assertEqual(
                hashlib.sha256(output_path.read_bytes()).hexdigest(),
                hashlib.sha256(
                    fallback_mode_split_4p_retention.build_source().encode("utf-8")
                ).hexdigest(),
            )
            spec = importlib.util.spec_from_file_location(
                "fallback_mode_split_4p_retention_submission",
                output_path,
            )
            self.assertIsNotNone(spec)
            self.assertIsNotNone(spec.loader)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            observation = json.loads(TWO_P_FIXTURE_PATH.read_text(encoding="utf-8"))

            self.assertEqual(
                module.agent(observation, {}),
                fallback_mode_split_4p_retention.agent(observation, {}),
            )

    def test_builder_cli_writes_output_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "submission.py"
            result = subprocess.run(
                [
                    sys.executable,
                    str(
                        REPO_ROOT
                        / "scripts"
                        / "build_fallback_mode_split_4p_retention_submission.py"
                    ),
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


if __name__ == "__main__":
    unittest.main()
