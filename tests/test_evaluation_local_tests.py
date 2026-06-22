"""Tests for local unittest profiling and parallel execution helpers."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from ow_eval import (
    LocalTestModule,
    build_unittest_command,
    default_worker_count,
    discover_test_modules,
    run_test_module,
    run_test_modules,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def write_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text).lstrip(), encoding="utf-8")


class LocalTestRunnerTests(unittest.TestCase):
    def test_discovery_and_command_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_file(root / "tests" / "__init__.py", "")
            write_file(
                root / "tests" / "test_b.py",
                """
                import unittest
                class BTests(unittest.TestCase):
                    def test_b(self): pass
                """,
            )
            write_file(
                root / "tests" / "nested" / "test_a.py",
                """
                import unittest
                class ATests(unittest.TestCase):
                    def test_a(self): pass
                """,
            )

            modules = discover_test_modules(root / "tests", repo_root=root)

        self.assertEqual(
            [module.module for module in modules],
            ["tests.nested.test_a", "tests.test_b"],
        )
        self.assertEqual(
            build_unittest_command("tests.test_b", python_executable="python"),
            ("python", "-m", "unittest", "tests.test_b"),
        )

    def test_run_one_module_captures_pass_failure_and_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_file(root / "tests" / "__init__.py", "")
            write_file(
                root / "tests" / "test_ok.py",
                """
                import unittest
                class OkTests(unittest.TestCase):
                    def test_ok(self): self.assertTrue(True)
                """,
            )
            write_file(
                root / "tests" / "test_fail.py",
                """
                import unittest
                class FailTests(unittest.TestCase):
                    def test_fail(self): self.fail("boom")
                """,
            )
            write_file(
                root / "tests" / "test_sleep.py",
                """
                import time
                import unittest
                class SleepTests(unittest.TestCase):
                    def test_sleep(self): time.sleep(1)
                """,
            )

            ok = run_test_module(
                LocalTestModule("tests.test_ok", "tests/test_ok.py"),
                repo_root=root,
            )
            failed = run_test_module(
                LocalTestModule("tests.test_fail", "tests/test_fail.py"),
                repo_root=root,
            )
            timed_out = run_test_module(
                LocalTestModule("tests.test_sleep", "tests/test_sleep.py"),
                repo_root=root,
                timeout_seconds=0.01,
            )

        self.assertTrue(ok.passed)
        self.assertFalse(failed.passed)
        self.assertIn("boom", failed.stderr)
        self.assertFalse(timed_out.passed)
        self.assertTrue(timed_out.timed_out)
        self.assertEqual(timed_out.returncode, 124)

    def test_parallel_runner_preserves_module_order_and_reports_failures(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_file(root / "tests" / "__init__.py", "")
            for name in ("test_a.py", "test_b.py", "test_c.py"):
                write_file(
                    root / "tests" / name,
                    """
                    import unittest
                    class Tests(unittest.TestCase):
                        def test_ok(self): pass
                    """,
                )
            modules = discover_test_modules(root / "tests", repo_root=root)

            summary = run_test_modules(modules, repo_root=root, workers=3)

        self.assertTrue(summary.passed)
        self.assertEqual(summary.exit_code, 0)
        self.assertEqual([result.module for result in summary.results], [m.module for m in modules])
        self.assertEqual(summary.worker_count, 3)
        decoded = json.loads(json.dumps(summary.to_dict(), sort_keys=True))
        self.assertEqual(decoded["module_count"], 3)

    def test_default_worker_count_is_positive_and_bounded(self) -> None:
        self.assertGreaterEqual(default_worker_count(), 1)
        self.assertLessEqual(default_worker_count(), 6)

    def test_scripts_expose_help_successfully(self) -> None:
        for script in ("scripts/profile_tests.py", "scripts/run_tests_parallel.py"):
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


if __name__ == "__main__":
    unittest.main()
