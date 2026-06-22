"""Tests for guarded Daytona runtime snapshot preparation."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ow_eval import (
    DAYTONA_RUNTIME_COMMIT_MARKER,
    DEFAULT_DAYTONA_RUNTIME_SNAPSHOT_NAME_PREFIX,
    DaytonaRuntimeSnapshotConfig,
    DaytonaRuntimeSnapshotPlan,
    DaytonaRuntimeSnapshotResult,
    prepare_daytona_runtime_snapshot,
    prepare_daytona_runtime_snapshot_context,
)


class DaytonaRuntimeSnapshotTests(unittest.TestCase):
    def test_module_imports_and_exports_are_available(self) -> None:
        import ow_eval.daytona_runtime_snapshot as runtime_snapshot

        self.assertIs(
            runtime_snapshot.DaytonaRuntimeSnapshotConfig,
            DaytonaRuntimeSnapshotConfig,
        )
        self.assertIs(
            runtime_snapshot.DaytonaRuntimeSnapshotPlan,
            DaytonaRuntimeSnapshotPlan,
        )
        self.assertIs(
            runtime_snapshot.DaytonaRuntimeSnapshotResult,
            DaytonaRuntimeSnapshotResult,
        )
        self.assertIs(
            runtime_snapshot.prepare_daytona_runtime_snapshot,
            prepare_daytona_runtime_snapshot,
        )
        self.assertIs(
            runtime_snapshot.prepare_daytona_runtime_snapshot_context,
            prepare_daytona_runtime_snapshot_context,
        )

    def test_context_uses_committed_tracked_source_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            output_dir = Path(temp_dir) / "out"
            repo_root.mkdir()
            self._init_git_repo(repo_root)
            (repo_root / "tracked.txt").write_text("tracked\n", encoding="utf-8")
            (repo_root / "agents").mkdir()
            (repo_root / "agents" / "orbit_wars_agent.py").write_text(
                "def agent(obs, config=None):\n    return []\n",
                encoding="utf-8",
            )
            self._git(repo_root, "add", "tracked.txt", "agents/orbit_wars_agent.py")
            self._git(repo_root, "commit", "-m", "tracked files")
            (repo_root / ".env").write_text("DAYTONA_API_KEY=secret\n", encoding="utf-8")
            (repo_root / ".venv").mkdir()
            (repo_root / ".venv" / "secret.txt").write_text("secret\n", encoding="utf-8")
            (repo_root / "untracked.txt").write_text("untracked\n", encoding="utf-8")

            plan = prepare_daytona_runtime_snapshot_context(
                DaytonaRuntimeSnapshotConfig(
                    repo_root=str(repo_root),
                    output_dir=str(output_dir),
                    snapshot_name="snapshot-test",
                    python_executable=sys.executable,
                ),
                requirements_lines=("kaggle-environments==1.0.0", "daytona==0.189.0"),
            )

            source_dir = Path(plan.source_dir)
            self.assertEqual(plan.snapshot_name, "snapshot-test")
            self.assertTrue((source_dir / "tracked.txt").is_file())
            self.assertTrue((source_dir / "agents" / "orbit_wars_agent.py").is_file())
            self.assertEqual(
                (source_dir / DAYTONA_RUNTIME_COMMIT_MARKER).read_text(
                    encoding="utf-8"
                ),
                plan.git_commit + "\n",
            )
            self.assertFalse((source_dir / ".env").exists())
            self.assertFalse((source_dir / ".venv").exists())
            self.assertFalse((source_dir / "untracked.txt").exists())
            self.assertEqual(
                Path(plan.requirements_path).read_text(encoding="utf-8"),
                "kaggle-environments==1.0.0\ndaytona==0.189.0\n",
            )
            self.assertGreaterEqual(plan.file_count, 3)
            self.assertEqual(plan.requirement_count, 2)
            json.dumps(plan.to_dict(), sort_keys=True)

    def test_default_snapshot_name_matches_current_head_auto_format(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            output_dir = Path(temp_dir) / "out"
            repo_root.mkdir()
            self._init_git_repo(repo_root)
            (repo_root / "tracked.py").write_text("x = 1\n", encoding="utf-8")
            self._git(repo_root, "add", "tracked.py")
            self._git(repo_root, "commit", "-m", "tracked file")

            plan = prepare_daytona_runtime_snapshot_context(
                DaytonaRuntimeSnapshotConfig(
                    repo_root=str(repo_root),
                    output_dir=str(output_dir),
                    python_executable=sys.executable,
                ),
                requirements_lines=("daytona==0.189.0",),
            )

        self.assertEqual(
            plan.snapshot_name,
            f"{DEFAULT_DAYTONA_RUNTIME_SNAPSHOT_NAME_PREFIX}-{plan.git_commit[:12]}",
        )

    def test_dry_run_prepares_context_without_requiring_real_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            repo_root.mkdir()
            self._init_git_repo(repo_root)
            (repo_root / "tracked.py").write_text("x = 1\n", encoding="utf-8")
            self._git(repo_root, "add", "tracked.py")
            self._git(repo_root, "commit", "-m", "tracked file")

            result = prepare_daytona_runtime_snapshot(
                DaytonaRuntimeSnapshotConfig(
                    repo_root=str(repo_root),
                    output_dir=str(Path(temp_dir) / "out"),
                    snapshot_name="dry-run-test",
                    python_executable=sys.executable,
                ),
                allow_real_daytona=False,
                env={},
                requirements_lines=("daytona==0.189.0",),
            )

        self.assertTrue(result.passed)
        self.assertFalse(result.readiness.passed)
        self.assertFalse(result.snapshot_created)
        self.assertEqual(result.snapshot_name, "dry-run-test")
        self.assertIn("snapshot_created=False", result.summary_text)

    def test_real_create_fails_closed_when_readiness_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            repo_root.mkdir()
            self._init_git_repo(repo_root)
            (repo_root / "tracked.py").write_text("x = 1\n", encoding="utf-8")
            self._git(repo_root, "add", "tracked.py")
            self._git(repo_root, "commit", "-m", "tracked file")
            calls: list[str] = []

            result = prepare_daytona_runtime_snapshot(
                DaytonaRuntimeSnapshotConfig(
                    repo_root=str(repo_root),
                    output_dir=str(Path(temp_dir) / "out"),
                    snapshot_name="blocked-test",
                    python_executable=sys.executable,
                ),
                allow_real_daytona=True,
                env={},
                requirements_lines=("daytona==0.189.0",),
                snapshot_creator=lambda plan, config: calls.append(plan.snapshot_name) or plan.snapshot_name,
            )

        self.assertEqual(result.exit_code, 2)
        self.assertFalse(result.passed)
        self.assertFalse(result.snapshot_created)
        self.assertEqual(calls, [])
        self.assertIn("not explicitly allowed", result.error_text)

    def test_real_create_uses_injected_snapshot_creator_after_readiness_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            repo_root.mkdir()
            self._init_git_repo(repo_root)
            (repo_root / "tracked.py").write_text("x = 1\n", encoding="utf-8")
            self._git(repo_root, "add", "tracked.py")
            self._git(repo_root, "commit", "-m", "tracked file")
            calls: list[tuple[str, str | None]] = []

            def fake_creator(plan, real_config):
                calls.append((plan.snapshot_name, real_config.target))
                return f"{plan.snapshot_name}-remote"

            result = prepare_daytona_runtime_snapshot(
                DaytonaRuntimeSnapshotConfig(
                    repo_root=str(repo_root),
                    output_dir=str(Path(temp_dir) / "out"),
                    snapshot_name="real-test",
                    python_executable=sys.executable,
                ),
                allow_real_daytona=True,
                env={
                    "OW_EVAL_ALLOW_REAL_DAYTONA": "1",
                    "DAYTONA_API_KEY": "test-token",
                    "DAYTONA_TARGET": "us",
                },
                requirements_lines=("daytona==0.189.0",),
                snapshot_creator=fake_creator,
            )

        self.assertTrue(result.passed)
        self.assertTrue(result.snapshot_created)
        self.assertEqual(result.snapshot_name, "real-test-remote")
        self.assertEqual(calls, [("real-test", "us")])
        self.assertIn("snapshot_created=True", result.summary_text)
        json.dumps(result.to_dict(), sort_keys=True)

    def test_script_help_exits_successfully(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        completed = subprocess.run(
            [sys.executable, "scripts/prepare_daytona_runtime_snapshot.py", "--help"],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0)
        self.assertIn("usage:", completed.stdout)
        self.assertEqual(completed.stderr, "")

    def _init_git_repo(self, repo_root: Path) -> None:
        self._git(repo_root, "init")
        self._git(repo_root, "config", "user.name", "Test User")
        self._git(repo_root, "config", "user.email", "test@example.com")

    def _git(self, repo_root: Path, *args: str) -> None:
        subprocess.run(
            ("git", *args),
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )


if __name__ == "__main__":
    unittest.main()
