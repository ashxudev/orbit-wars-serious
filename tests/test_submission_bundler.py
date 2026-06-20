"""Tests for Runtime / Submission Cycle 7 single-file bundler."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import build_submission


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "kaggle_seed7_2p_step0.json"


class SubmissionBundlerTests(unittest.TestCase):
    def test_build_submission_module_imports_and_exports_are_available(self) -> None:
        self.assertEqual(
            build_submission.BUNDLE_PACKAGES,
            ("ow_sim", "ow_planner", "agents"),
        )
        self.assertTrue(callable(build_submission.discover_bundle_modules))
        self.assertTrue(callable(build_submission.build_submission_source))
        self.assertTrue(callable(build_submission.write_submission))
        self.assertTrue(callable(build_submission.main))

    def test_discovered_modules_include_runtime_planner_and_simulator(self) -> None:
        modules = build_submission.discover_bundle_modules(REPO_ROOT)
        module_names = {module.module_name for module in modules}

        self.assertIn("agents", module_names)
        self.assertIn("agents.orbit_wars_agent", module_names)
        self.assertIn("agents.runtime_config", module_names)
        self.assertIn("ow_planner", module_names)
        self.assertIn("ow_planner.actions", module_names)
        self.assertIn("ow_planner.two_player_pressure", module_names)
        self.assertIn("ow_sim", module_names)
        self.assertIn("ow_sim.state", module_names)
        self.assertTrue(all(not name.startswith("tests") for name in module_names))
        self.assertTrue(all(not name.startswith("scripts") for name in module_names))
        self.assertTrue(all("agent_workflows" not in name for name in module_names))

    def test_build_submission_source_is_deterministic(self) -> None:
        first = build_submission.build_submission_source(REPO_ROOT)
        second = build_submission.build_submission_source(REPO_ROOT)

        self.assertEqual(first, second)
        self.assertIn("agent = importlib.import_module", first)
        self.assertIn("'agents.orbit_wars_agent'", first)
        self.assertIn("'ow_planner.actions'", first)
        self.assertIn("'ow_planner.two_player_pressure'", first)
        self.assertIn("'ow_sim.state'", first)

    def test_write_submission_twice_produces_identical_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first_path = Path(tmp) / "submission_a.py"
            second_path = Path(tmp) / "submission_b.py"

            build_submission.write_submission(first_path, REPO_ROOT)
            build_submission.write_submission(second_path, REPO_ROOT)

            self.assertEqual(first_path.read_bytes(), second_path.read_bytes())

    def test_cli_writes_output_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "orbit_wars_submission.py"
            result = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "build_submission.py"),
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
            self.assertTrue(output_path.exists())
            self.assertIn("def _module_file", output_path.read_text(encoding="utf-8"))

    def test_generated_submission_imports_outside_repo_and_exposes_agent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            output_path = tmp_path / "orbit_wars_submission.py"
            build_submission.write_submission(output_path, REPO_ROOT)

            script = (
                "import importlib.util, json\n"
                f"spec = importlib.util.spec_from_file_location("
                f"'orbit_wars_submission', {str(output_path)!r})\n"
                "mod = importlib.util.module_from_spec(spec)\n"
                "spec.loader.exec_module(mod)\n"
                f"obs = json.load(open({str(FIXTURE_PATH)!r}, encoding='utf-8'))\n"
                "result = mod.agent(obs, {})\n"
                "print(json.dumps(result))\n"
                "print(callable(mod.agent))\n"
            )
            env = os.environ.copy()
            env.pop("PYTHONPATH", None)

            result = subprocess.run(
                [sys.executable, "-c", script],
                cwd=tmp_path,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )

            lines = result.stdout.strip().splitlines()
            self.assertEqual(json.loads(lines[0]), [[0, 1.0810892066581865, 10]])
            self.assertEqual(lines[1], "True")


if __name__ == "__main__":
    unittest.main()
