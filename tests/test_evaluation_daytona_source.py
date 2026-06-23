"""Tests for Daytona GitHub source-mode helpers."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ow_eval import (
    COMMIT_PUSH_REQUIRED_MESSAGE,
    DAYTONA_SOURCE_MODE_GITHUB,
    DAYTONA_SOURCE_MODE_LOCAL,
    DaytonaGitPreflightResult,
    build_github_bootstrap_argv,
    normalize_daytona_source_mode,
    redacted_github_repo_url,
    resolve_daytona_git_ref,
    validate_daytona_git_preflight,
)


class DaytonaSourceTests(unittest.TestCase):
    def test_module_imports_and_exports_are_available(self) -> None:
        import ow_eval.daytona_source as daytona_source

        self.assertIs(daytona_source.DaytonaGitPreflightResult, DaytonaGitPreflightResult)
        self.assertIs(daytona_source.validate_daytona_git_preflight, validate_daytona_git_preflight)
        self.assertIs(daytona_source.resolve_daytona_git_ref, resolve_daytona_git_ref)

    def test_source_mode_normalization_and_bootstrap_are_json_safe(self) -> None:
        argv = build_github_bootstrap_argv(
            github_repo="https://github.com/ashxudev/orbit-wars-serious.git",
            git_ref="abc123",
            github_token_env_var="DAYTONA_GITHUB_TOKEN",
            checkout_dir="/workspace/orbit-wars-serious",
            python_command=".venv/bin/python",
            runner_script="scripts/run_evaluation_shard_job.py",
            job_path="/tmp/job.json",
        )

        self.assertEqual(normalize_daytona_source_mode(None), DAYTONA_SOURCE_MODE_GITHUB)
        self.assertEqual(normalize_daytona_source_mode("LOCAL"), DAYTONA_SOURCE_MODE_LOCAL)
        self.assertEqual(argv[:2], ("bash", "-lc"))
        self.assertIn("DAYTONA_GITHUB_TOKEN", argv[2])
        self.assertIn("abc123", argv[2])
        self.assertIn("scripts/run_evaluation_shard_job.py", argv[2])
        self.assertIn('pip install -r "$CHECKOUT_DIR/requirements.txt"', argv[2])
        self.assertIn("\ncd /\n", argv[2])
        self.assertNotIn("secret-token", argv[2])
        self.assertEqual(
            redacted_github_repo_url("https://token@github.com/owner/repo.git"),
            "https://<redacted>@github.com/owner/repo.git",
        )
        json.dumps({"argv": argv}, sort_keys=True)

    def test_git_preflight_passes_for_clean_pushed_head(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo, _remote = self._pushed_repo(Path(temp_dir))

            result = validate_daytona_git_preflight(repo_root=repo, fetch=True)

        self.assertTrue(result.passed)
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.dirty_paths, ())
        self.assertEqual(result.head_commit, result.remote_commit)

    def test_git_preflight_allows_non_github_source_modes_without_fetch(self) -> None:
        result = validate_daytona_git_preflight(
            source_mode=DAYTONA_SOURCE_MODE_LOCAL,
            repo_root="/tmp/not-a-repo",
            fetch=True,
        )

        self.assertTrue(result.passed)
        self.assertIn("SKIPPED", result.summary_text)

    def test_git_preflight_fails_for_dirty_source_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo, _remote = self._pushed_repo(Path(temp_dir))
            (repo / "tracked.py").write_text("changed\n", encoding="utf-8")

            result = validate_daytona_git_preflight(repo_root=repo, fetch=False)

        self.assertFalse(result.passed)
        self.assertIn("tracked.py", result.dirty_paths)
        self.assertIn(COMMIT_PUSH_REQUIRED_MESSAGE, result.error_text or "")

    def test_git_preflight_fails_for_unpushed_head(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo, _remote = self._pushed_repo(Path(temp_dir))
            (repo / "new.py").write_text("new\n", encoding="utf-8")
            self._git(repo, "add", "new.py")
            self._git(repo, "commit", "-m", "unpushed")

            result = validate_daytona_git_preflight(repo_root=repo, fetch=False)

        self.assertFalse(result.passed)
        self.assertIn(COMMIT_PUSH_REQUIRED_MESSAGE, result.error_text or "")
        self.assertNotEqual(result.head_commit, result.remote_commit)

    def test_git_preflight_fails_for_missing_remote_ref(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir) / "repo"
            repo.mkdir()
            self._init_git_repo(repo)
            (repo / "tracked.py").write_text("x = 1\n", encoding="utf-8")
            self._git(repo, "add", "tracked.py")
            self._git(repo, "commit", "-m", "initial")

            result = validate_daytona_git_preflight(repo_root=repo, fetch=False)

        self.assertFalse(result.passed)
        self.assertTrue(result.missing_remote)
        self.assertIn(COMMIT_PUSH_REQUIRED_MESSAGE, result.error_text or "")

    def test_resolve_daytona_git_ref_auto_uses_repo_head(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo, _remote = self._pushed_repo(Path(temp_dir))
            expected = self._git(repo, "rev-parse", "HEAD").strip()

            self.assertEqual(resolve_daytona_git_ref("auto", repo_root=repo), expected)
            self.assertEqual(resolve_daytona_git_ref("explicit", repo_root=repo), "explicit")

    def _pushed_repo(self, temp_dir: Path) -> tuple[Path, Path]:
        remote = temp_dir / "remote.git"
        subprocess.run(
            ("git", "init", "--bare", str(remote)),
            check=True,
            capture_output=True,
            text=True,
        )
        repo = temp_dir / "repo"
        repo.mkdir()
        self._init_git_repo(repo)
        self._git(repo, "checkout", "-b", "main")
        (repo / "tracked.py").write_text("x = 1\n", encoding="utf-8")
        self._git(repo, "add", "tracked.py")
        self._git(repo, "commit", "-m", "initial")
        self._git(repo, "remote", "add", "origin", str(remote))
        self._git(repo, "push", "-u", "origin", "main")
        return repo, remote

    def _init_git_repo(self, repo: Path) -> None:
        self._git(repo, "init")
        self._git(repo, "config", "user.name", "Test User")
        self._git(repo, "config", "user.email", "test@example.com")

    def _git(self, repo: Path, *args: str) -> str:
        completed = subprocess.run(
            ("git", *args),
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout


if __name__ == "__main__":
    unittest.main()
