"""Tests for Evaluation Harness Cycle 4 match artifacts."""

from __future__ import annotations

import importlib
import json
import sys
import tempfile
import types
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch

from ow_eval import (
    AgentSourceKind,
    AgentSpec,
    BaselineName,
    EvaluationArtifactConfig,
    EvaluationStatus,
    MatchConfig,
    MatchResult,
    OpponentSpec,
    PlayerCount,
    builtin_baseline_spec,
    run_official_match,
    write_match_result_artifact,
    write_replay_artifact,
)


def artifact_match_config(
    *,
    label: str | None = "artifact smoke",
    candidate_agent: AgentSpec | None = None,
) -> MatchConfig:
    if candidate_agent is None:
        candidate_agent = builtin_baseline_spec(BaselineName.NOOP, name="candidate-noop")
    return MatchConfig(
        seed=7,
        player_count=PlayerCount.TWO_PLAYER,
        controlled_seat=0,
        candidate_agent=candidate_agent,
        opponent_agents=(
            OpponentSpec(
                builtin_baseline_spec(BaselineName.NOOP, name="opponent-noop")
            ),
        ),
        label=label,
    )


class FakeOrbitWarsEnvironment:
    def __init__(self, replay_payload: object | None = None) -> None:
        self.reset_players: int | None = None
        self.run_called = False
        self.replay_payload = replay_payload or {"steps": [{"status": "done"}]}

    def reset(self, players: int) -> None:
        self.reset_players = players

    def run(self, agents: list[object]) -> list[object]:
        self.run_called = True
        for agent in agents:
            agent({"step": 0}, {})
        return []

    def toJSON(self) -> object:
        return self.replay_payload


class EvaluationArtifactTests(unittest.TestCase):
    def tearDown(self) -> None:
        for module_name in tuple(sys.modules):
            if module_name == "kaggle_environments" or module_name.startswith(
                "kaggle_environments."
            ):
                sys.modules.pop(module_name, None)

    def test_artifact_module_imports_and_exports_are_available(self) -> None:
        module = importlib.import_module("ow_eval.artifacts")

        self.assertIs(module.EvaluationArtifactConfig, EvaluationArtifactConfig)
        self.assertIs(module.write_match_result_artifact, write_match_result_artifact)
        self.assertIs(module.write_replay_artifact, write_replay_artifact)

    def test_artifact_config_is_frozen_slotted_and_validates(self) -> None:
        config = EvaluationArtifactConfig(output_dir="/tmp/ow-eval")

        with self.assertRaises(FrozenInstanceError):
            config.write_result = False  # type: ignore[misc]
        with self.assertRaises((AttributeError, TypeError)):
            config.extra = "nope"  # type: ignore[attr-defined]
        with self.assertRaisesRegex(ValueError, "output_dir must be a non-empty path"):
            EvaluationArtifactConfig(output_dir="")
        with self.assertRaisesRegex(ValueError, "write_replay must be a boolean"):
            EvaluationArtifactConfig(output_dir="/tmp", write_replay=1)  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "prefix must be non-empty"):
            EvaluationArtifactConfig(output_dir="/tmp", prefix="")

    def test_write_match_result_artifact_round_trips_deterministic_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "result.json"
            result = MatchResult(
                config=artifact_match_config(),
                status=EvaluationStatus.COMPLETED,
                artifact_path=str(path),
            )

            written_path = write_match_result_artifact(result, path)

            self.assertEqual(written_path, path)
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.endswith("\n"))
            data = json.loads(text)
            self.assertEqual(MatchResult.from_dict(data), result)

    def test_write_replay_artifact_writes_valid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "replay.json"
            payload = {"steps": [{"actions": []}], "configuration": {"seed": 7}}

            written_path = write_replay_artifact(payload, path)

            self.assertEqual(written_path, path)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), payload)

    def test_successful_official_match_writes_replay_and_result_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = artifact_match_config(label="Smoke Match / Unsafe?")
            artifact_config = EvaluationArtifactConfig(output_dir=tmp)

            result = run_official_match(config, artifacts=artifact_config)

            self.assertEqual(result.status, EvaluationStatus.COMPLETED)
            self.assertIsNotNone(result.artifact_path)
            self.assertIsNotNone(result.replay_path)
            artifact_path = Path(result.artifact_path or "")
            replay_path = Path(result.replay_path or "")
            self.assertEqual(artifact_path.parent, Path(tmp))
            self.assertEqual(replay_path.parent, Path(tmp))
            self.assertEqual(artifact_path.name, "smoke-match-unsafe-result.json")
            self.assertEqual(replay_path.name, "smoke-match-unsafe-replay.json")
            self.assertTrue(artifact_path.is_file())
            self.assertTrue(replay_path.is_file())

            result_data = json.loads(artifact_path.read_text(encoding="utf-8"))
            replay_data = json.loads(replay_path.read_text(encoding="utf-8"))

        self.assertEqual(MatchResult.from_dict(result_data), result)
        self.assertIn("steps", replay_data)

    def test_import_failure_writes_result_without_replay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = artifact_match_config(
                candidate_agent=AgentSpec(
                    name="missing",
                    source_kind=AgentSourceKind.MODULAR_AGENT,
                    module_path="missing_artifact_candidate_module",
                )
            )

            result = run_official_match(
                config,
                artifacts=EvaluationArtifactConfig(output_dir=tmp),
            )

            self.assertEqual(result.status, EvaluationStatus.IMPORT_ERROR)
            self.assertIsNotNone(result.artifact_path)
            self.assertIsNone(result.replay_path)
            self.assertTrue(Path(result.artifact_path or "").is_file())
            self.assertEqual(
                MatchResult.from_dict(
                    json.loads(Path(result.artifact_path or "").read_text("utf-8"))
                ),
                result,
            )
            self.assertEqual(len(tuple(Path(tmp).iterdir())), 1)

    def test_artifact_file_names_fall_back_to_match_config_when_no_label(self) -> None:
        fake_env = FakeOrbitWarsEnvironment()
        fake_kaggle = fake_kaggle_module(fake_env)

        with tempfile.TemporaryDirectory() as tmp:
            config = artifact_match_config(label=None)
            with patch.dict(sys.modules, {"kaggle_environments": fake_kaggle}):
                result = run_official_match(
                    config,
                    artifacts=EvaluationArtifactConfig(output_dir=tmp),
                )

            self.assertEqual(result.status, EvaluationStatus.COMPLETED)
            self.assertEqual(
                Path(result.artifact_path or "").name,
                "seed-7-players-2-seat-0-result.json",
            )
            self.assertEqual(
                Path(result.replay_path or "").name,
                "seed-7-players-2-seat-0-replay.json",
            )

    def test_artifact_prefix_overrides_label(self) -> None:
        fake_env = FakeOrbitWarsEnvironment()
        fake_kaggle = fake_kaggle_module(fake_env)

        with tempfile.TemporaryDirectory() as tmp:
            config = artifact_match_config(label="ignored label")
            with patch.dict(sys.modules, {"kaggle_environments": fake_kaggle}):
                result = run_official_match(
                    config,
                    artifacts=EvaluationArtifactConfig(output_dir=tmp, prefix="Run 01"),
                )

            self.assertEqual(Path(result.artifact_path or "").name, "run-01-result.json")
            self.assertEqual(Path(result.replay_path or "").name, "run-01-replay.json")

    def test_disabling_result_or_replay_suppresses_only_that_file(self) -> None:
        fake_kaggle = fake_kaggle_module(FakeOrbitWarsEnvironment())
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(sys.modules, {"kaggle_environments": fake_kaggle}):
                result = run_official_match(
                    artifact_match_config(label="no replay"),
                    artifacts=EvaluationArtifactConfig(
                        output_dir=tmp,
                        write_replay=False,
                    ),
                )

            self.assertIsNotNone(result.artifact_path)
            self.assertIsNone(result.replay_path)
            self.assertTrue(Path(result.artifact_path or "").is_file())

        fake_kaggle = fake_kaggle_module(FakeOrbitWarsEnvironment())
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(sys.modules, {"kaggle_environments": fake_kaggle}):
                result = run_official_match(
                    artifact_match_config(label="no result"),
                    artifacts=EvaluationArtifactConfig(
                        output_dir=tmp,
                        write_result=False,
                    ),
                )

            self.assertIsNone(result.artifact_path)
            self.assertIsNotNone(result.replay_path)
            self.assertTrue(Path(result.replay_path or "").is_file())
            self.assertEqual(
                sorted(path.name for path in Path(tmp).iterdir()),
                ["no-result-replay.json"],
            )

    def test_artifact_write_failure_returns_unknown_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_file = Path(tmp) / "not-a-directory"
            output_file.write_text("occupied", encoding="utf-8")

            result = run_official_match(
                artifact_match_config(),
                artifacts=EvaluationArtifactConfig(output_dir=output_file),
            )

            self.assertEqual(result.status, EvaluationStatus.UNKNOWN_ERROR)
            self.assertIsNotNone(result.error_text)
            self.assertIn("FileExistsError", result.error_text)
            self.assertIsNone(result.artifact_path)
            self.assertIsNone(result.replay_path)

    def test_unavailable_error_replay_is_skipped_without_hiding_error(self) -> None:
        fake_env = FakeOrbitWarsEnvironment(replay_payload="not a replay mapping")
        fake_kaggle = fake_kaggle_module(fake_env)
        failing_module = types.ModuleType("artifact_failing_agent")

        def failing_agent(observation: object, configuration: object = None):
            raise RuntimeError("boom")

        failing_module.agent = failing_agent  # type: ignore[attr-defined]

        with tempfile.TemporaryDirectory() as tmp:
            config = artifact_match_config(
                candidate_agent=AgentSpec(
                    name="candidate",
                    source_kind=AgentSourceKind.MODULAR_AGENT,
                    module_path="artifact_failing_agent",
                )
            )
            with patch.dict(
                sys.modules,
                {
                    "kaggle_environments": fake_kaggle,
                    "artifact_failing_agent": failing_module,
                },
            ):
                result = run_official_match(
                    config,
                    artifacts=EvaluationArtifactConfig(output_dir=tmp),
                )

            self.assertEqual(result.status, EvaluationStatus.AGENT_ERROR)
            self.assertIsNotNone(result.artifact_path)
            self.assertIsNone(result.replay_path)
            self.assertTrue(Path(result.artifact_path or "").is_file())


def fake_kaggle_module(fake_env: FakeOrbitWarsEnvironment) -> types.ModuleType:
    module = types.ModuleType("kaggle_environments")

    def make(name: str, configuration: dict[str, object], debug: bool = False):
        return fake_env

    module.make = make  # type: ignore[attr-defined]
    return module


if __name__ == "__main__":
    unittest.main()
