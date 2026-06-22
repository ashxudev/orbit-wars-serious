"""Tests for real-Daytona execution safety-gate contracts."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch

from ow_eval import (
    AUTO_DAYTONA_SNAPSHOT_ID_VALUES,
    DaytonaRealExecutionConfig,
    DaytonaRealExecutionReadiness,
    DEFAULT_DAYTONA_RUNTIME_SNAPSHOT_NAME_PREFIX,
    read_daytona_real_execution_config_from_env,
    resolve_daytona_snapshot_id,
    validate_daytona_real_execution_readiness,
)


class DaytonaRealExecutionConfigTests(unittest.TestCase):
    def test_module_imports_and_exports_are_available(self) -> None:
        import ow_eval.daytona_real_config as daytona_real_config

        self.assertIs(
            daytona_real_config.DaytonaRealExecutionConfig,
            DaytonaRealExecutionConfig,
        )
        self.assertIs(
            daytona_real_config.DaytonaRealExecutionReadiness,
            DaytonaRealExecutionReadiness,
        )
        self.assertIs(
            daytona_real_config.read_daytona_real_execution_config_from_env,
            read_daytona_real_execution_config_from_env,
        )
        self.assertIs(
            daytona_real_config.validate_daytona_real_execution_readiness,
            validate_daytona_real_execution_readiness,
        )

    def test_default_config_fails_closed_without_raising(self) -> None:
        readiness = validate_daytona_real_execution_readiness(
            DaytonaRealExecutionConfig(),
            env={},
        )

        self.assertEqual(readiness.exit_code, 2)
        self.assertFalse(readiness.ready)
        self.assertFalse(readiness.passed)
        self.assertEqual(readiness.missing_env_vars, ("DAYTONA_API_KEY",))
        self.assertIn("not explicitly allowed", readiness.error_text)
        self.assertIn("missing env vars: DAYTONA_API_KEY", readiness.error_text)
        self.assertIn("daytona_real_execution_readiness=BLOCKED", readiness.summary_text)

    def test_readiness_requires_explicit_allow_and_nonempty_token_env(self) -> None:
        config = DaytonaRealExecutionConfig(
            allow_real_daytona=True,
            api_key_env_var="MY_DAYTONA_TOKEN",
        )

        missing = validate_daytona_real_execution_readiness(config, env={})
        empty = validate_daytona_real_execution_readiness(
            config,
            env={"MY_DAYTONA_TOKEN": "   "},
        )
        ready = validate_daytona_real_execution_readiness(
            config,
            env={"MY_DAYTONA_TOKEN": "secret"},
        )

        self.assertEqual(missing.exit_code, 2)
        self.assertEqual(missing.missing_env_vars, ("MY_DAYTONA_TOKEN",))
        self.assertEqual(empty.exit_code, 2)
        self.assertEqual(empty.missing_env_vars, ("MY_DAYTONA_TOKEN",))
        self.assertEqual(ready.exit_code, 0)
        self.assertTrue(ready.ready)
        self.assertTrue(ready.passed)
        self.assertIsNone(ready.error_text)
        self.assertIn("daytona_real_execution_readiness=READY", ready.summary_text)

    def test_readiness_requires_github_token_only_when_bootstrap_requires_it(self) -> None:
        config = DaytonaRealExecutionConfig(
            allow_real_daytona=True,
            api_key_env_var="MY_DAYTONA_TOKEN",
            github_token_env_var="MY_GITHUB_TOKEN",
        )
        clone_config = DaytonaRealExecutionConfig(
            allow_real_daytona=True,
            api_key_env_var="MY_DAYTONA_TOKEN",
            github_token_env_var="MY_GITHUB_TOKEN",
            require_github_token=True,
        )

        no_clone = validate_daytona_real_execution_readiness(
            config,
            env={"MY_DAYTONA_TOKEN": "daytona-secret"},
        )
        clone_missing = validate_daytona_real_execution_readiness(
            clone_config,
            env={"MY_DAYTONA_TOKEN": "daytona-secret"},
        )
        clone_ready = validate_daytona_real_execution_readiness(
            clone_config,
            env={
                "MY_DAYTONA_TOKEN": "daytona-secret",
                "MY_GITHUB_TOKEN": "github-secret",
            },
        )

        self.assertTrue(no_clone.passed)
        self.assertEqual(clone_missing.missing_env_vars, ("MY_GITHUB_TOKEN",))
        self.assertFalse(clone_missing.passed)
        self.assertTrue(clone_ready.passed)
        self.assertIn("github_token_required=True", clone_ready.summary_text)

    def test_env_reader_uses_deterministic_names_and_optional_fields(self) -> None:
        config = read_daytona_real_execution_config_from_env(
            {
                "OW_EVAL_ALLOW_REAL_DAYTONA": "true",
                "DAYTONA_API_KEY_ENV_VAR": "MY_DAYTONA_TOKEN",
                "MY_DAYTONA_TOKEN": "secret",
                "DAYTONA_API_URL": "https://example.daytona.test/api",
                "DAYTONA_TARGET": "us",
                "GITHUB_TOKEN_ENV_VAR": "MY_GITHUB_TOKEN",
                "OW_EVAL_REQUIRE_GITHUB_TOKEN": "1",
                "MY_GITHUB_TOKEN": "github-secret",
                "DAYTONA_PROJECT_ID": "project-1",
                "DAYTONA_WORKSPACE_ID": "workspace-1",
                "DAYTONA_SNAPSHOT_ID": "snapshot-1",
                "DAYTONA_IMAGE": "image-1",
                "DAYTONA_WORKING_DIR": "/workspace/custom",
                "DAYTONA_SANDBOX_NAME_PREFIX": "prefix",
            }
        )

        self.assertTrue(config.allow_real_daytona)
        self.assertEqual(config.api_key_env_var, "MY_DAYTONA_TOKEN")
        self.assertEqual(config.api_url, "https://example.daytona.test/api")
        self.assertEqual(config.target, "us")
        self.assertEqual(config.github_token_env_var, "MY_GITHUB_TOKEN")
        self.assertTrue(config.require_github_token)
        self.assertEqual(config.project_id, "project-1")
        self.assertEqual(config.workspace_id, "workspace-1")
        self.assertEqual(config.snapshot_id, "snapshot-1")
        self.assertEqual(config.image, "image-1")
        self.assertEqual(config.default_working_dir, "/workspace/custom")
        self.assertEqual(config.sandbox_name_prefix, "prefix")

        readiness = validate_daytona_real_execution_readiness(
            config,
            env={
                "MY_DAYTONA_TOKEN": "secret",
                "MY_GITHUB_TOKEN": "github-secret",
            },
        )

        self.assertEqual(readiness.exit_code, 0)

    def test_auto_snapshot_id_resolves_to_current_head_snapshot_name(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        completed = subprocess.run(
            ("git", "rev-parse", "HEAD"),
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
        git_commit = completed.stdout.strip()
        expected_snapshot_id = (
            f"{DEFAULT_DAYTONA_RUNTIME_SNAPSHOT_NAME_PREFIX}-{git_commit[:12]}"
        )

        self.assertEqual(
            resolve_daytona_snapshot_id("auto", repo_root=repo_root),
            expected_snapshot_id,
        )
        self.assertEqual(
            resolve_daytona_snapshot_id("LATEST", repo_root=repo_root),
            expected_snapshot_id,
        )
        self.assertEqual(
            resolve_daytona_snapshot_id("snapshot-explicit", repo_root=repo_root),
            "snapshot-explicit",
        )
        self.assertIn("auto", AUTO_DAYTONA_SNAPSHOT_ID_VALUES)

        config = read_daytona_real_execution_config_from_env(
            {"DAYTONA_SNAPSHOT_ID": "current-head"}
        )

        self.assertEqual(config.snapshot_id, expected_snapshot_id)

    def test_empty_optional_env_values_are_safe(self) -> None:
        config = read_daytona_real_execution_config_from_env(
            {
                "OW_EVAL_ALLOW_REAL_DAYTONA": "1",
                "DAYTONA_API_KEY_ENV_VAR": "",
                "GITHUB_TOKEN_ENV_VAR": "",
                "OW_EVAL_REQUIRE_GITHUB_TOKEN": "1",
                "DAYTONA_WORKING_DIR": "",
                "DAYTONA_SANDBOX_NAME_PREFIX": "",
            }
        )

        self.assertIsNone(config.api_key_env_var)
        self.assertEqual(config.default_working_dir, "/workspace/orbit-wars-serious")
        self.assertIsNone(config.sandbox_name_prefix)

        readiness = validate_daytona_real_execution_readiness(config, env={})
        self.assertEqual(readiness.exit_code, 2)
        self.assertIn("api_key_env_var is required", readiness.error_text)
        self.assertIn("missing env vars: DAYTONA_GITHUB_TOKEN", readiness.error_text)

    def test_dotenv_file_is_loaded_for_process_env_without_overriding_existing_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "\n".join(
                    (
                        "OW_EVAL_ALLOW_REAL_DAYTONA=1",
                        "DAYTONA_API_KEY=from-dotenv",
                        "DAYTONA_TARGET=from-dotenv",
                        "OW_EVAL_REQUIRE_GITHUB_TOKEN=1",
                        "DAYTONA_GITHUB_TOKEN=from-dotenv",
                    )
                ),
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {
                    "OW_EVAL_DOTENV_PATH": str(env_path),
                    "DAYTONA_TARGET": "from-process-env",
                },
                clear=True,
            ):
                config = read_daytona_real_execution_config_from_env()
                readiness = validate_daytona_real_execution_readiness(config)

        self.assertTrue(config.allow_real_daytona)
        self.assertEqual(config.api_key_env_var, "DAYTONA_API_KEY")
        self.assertEqual(config.target, "from-process-env")
        self.assertEqual(config.github_token_env_var, "DAYTONA_GITHUB_TOKEN")
        self.assertTrue(config.require_github_token)
        self.assertTrue(readiness.passed)

    def test_explicit_env_mapping_does_not_load_dotenv(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "\n".join(
                    (
                        "OW_EVAL_ALLOW_REAL_DAYTONA=1",
                        "DAYTONA_API_KEY=from-dotenv",
                    )
                ),
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {"OW_EVAL_DOTENV_PATH": str(env_path)},
                clear=True,
            ):
                config = read_daytona_real_execution_config_from_env({})
                readiness = validate_daytona_real_execution_readiness(config, env={})

        self.assertFalse(config.allow_real_daytona)
        self.assertEqual(readiness.missing_env_vars, ("DAYTONA_API_KEY",))

    def test_dataclasses_are_frozen_slotted_validated_and_json_safe(self) -> None:
        config = DaytonaRealExecutionConfig(
            allow_real_daytona=True,
            api_key_env_var="TOKEN",
            target="us",
            project_id="project",
        )
        readiness = validate_daytona_real_execution_readiness(
            config,
            env={"TOKEN": "secret"},
        )

        with self.assertRaises(FrozenInstanceError):
            config.project_id = "changed"  # type: ignore[misc]
        with self.assertRaises((AttributeError, TypeError)):
            readiness.extra = "nope"  # type: ignore[attr-defined]
        with self.assertRaisesRegex(ValueError, "allow_real_daytona"):
            DaytonaRealExecutionConfig(allow_real_daytona="yes")  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "project_id"):
            DaytonaRealExecutionConfig(project_id="")
        with self.assertRaisesRegex(ValueError, "require_github_token"):
            DaytonaRealExecutionConfig(require_github_token="yes")  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "env keys"):
            read_daytona_real_execution_config_from_env({1: "bad"})  # type: ignore[dict-item]
        with self.assertRaisesRegex(ValueError, "env\\[TOKEN\\]"):
            validate_daytona_real_execution_readiness(config, env={"TOKEN": 1})  # type: ignore[dict-item]

        decoded = json.loads(json.dumps(readiness.to_dict(), sort_keys=True))
        self.assertEqual(decoded["config"]["project_id"], "project")
        self.assertEqual(decoded["config"]["target"], "us")
        self.assertTrue(decoded["passed"])

    def test_importing_ow_eval_does_not_import_daytona_or_kaggle(self) -> None:
        sys.modules.pop("daytona", None)
        sys.modules.pop("kaggle_environments", None)

        import ow_eval  # noqa: F401

        self.assertNotIn("daytona", sys.modules)
        self.assertNotIn("kaggle_environments", sys.modules)


if __name__ == "__main__":
    unittest.main()
