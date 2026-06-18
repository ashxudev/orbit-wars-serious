"""Tests for Evaluation Harness Cycle 0 contracts."""

from __future__ import annotations

import importlib
import sys
import unittest
from dataclasses import FrozenInstanceError

from ow_eval import (
    AgentSourceKind,
    AgentSpec,
    EvaluationStatus,
    MatchConfig,
    MatchMetrics,
    MatchResult,
    OpponentSpec,
    PlayerCount,
)
from ow_eval import contracts


def modular_agent(name: str = "candidate") -> AgentSpec:
    return AgentSpec(
        name=name,
        source_kind=AgentSourceKind.MODULAR_AGENT,
        module_path="agents.orbit_wars_agent",
        callable_name="agent",
        metadata=(("role", name),),
    )


def baseline_agent(name: str) -> OpponentSpec:
    return OpponentSpec(
        AgentSpec(
            name=name,
            source_kind=AgentSourceKind.BUILTIN_BASELINE,
            callable_name="agent",
        )
    )


class EvaluationContractTests(unittest.TestCase):
    def test_public_imports_are_available_from_package_and_contracts(self) -> None:
        module = importlib.import_module("ow_eval")
        contracts_module = importlib.import_module("ow_eval.contracts")

        self.assertIs(module.AgentSpec, AgentSpec)
        self.assertIs(module.MatchConfig, MatchConfig)
        self.assertIs(module.MatchResult, MatchResult)
        self.assertIs(contracts_module.AgentSpec, AgentSpec)
        self.assertIs(contracts_module.MatchConfig, MatchConfig)
        self.assertIs(contracts_module.MatchResult, MatchResult)
        self.assertIs(contracts.AgentSourceKind, AgentSourceKind)

    def test_enums_have_stable_values(self) -> None:
        self.assertEqual(AgentSourceKind.MODULAR_AGENT.value, "modular_agent")
        self.assertEqual(AgentSourceKind.SUBMISSION_FILE.value, "submission_file")
        self.assertEqual(AgentSourceKind.PYTHON_FILE.value, "python_file")
        self.assertEqual(AgentSourceKind.BUILTIN_BASELINE.value, "builtin_baseline")
        self.assertEqual(PlayerCount.TWO_PLAYER.value, 2)
        self.assertEqual(PlayerCount.FOUR_PLAYER.value, 4)
        self.assertEqual(EvaluationStatus.NOT_RUN.value, "not_run")
        self.assertEqual(EvaluationStatus.COMPLETED.value, "completed")
        self.assertEqual(EvaluationStatus.IMPORT_ERROR.value, "import_error")
        self.assertEqual(EvaluationStatus.ENV_ERROR.value, "env_error")
        self.assertEqual(EvaluationStatus.AGENT_ERROR.value, "agent_error")
        self.assertEqual(EvaluationStatus.TIMEOUT.value, "timeout")
        self.assertEqual(EvaluationStatus.INVALID_ACTION.value, "invalid_action")
        self.assertEqual(EvaluationStatus.UNKNOWN_ERROR.value, "unknown_error")

    def test_contract_objects_are_frozen_and_slotted(self) -> None:
        spec = modular_agent()
        config = MatchConfig(
            seed=7,
            player_count=PlayerCount.TWO_PLAYER,
            controlled_seat=0,
            candidate_agent=spec,
            opponent_agents=(baseline_agent("baseline"),),
        )
        result = MatchResult(config=config)

        with self.assertRaises(FrozenInstanceError):
            spec.name = "other"  # type: ignore[misc]
        with self.assertRaises((AttributeError, TypeError)):
            config.extra = "nope"  # type: ignore[attr-defined]
        with self.assertRaises(FrozenInstanceError):
            result.status = EvaluationStatus.COMPLETED  # type: ignore[misc]

    def test_representative_two_player_match_config_constructs(self) -> None:
        config = MatchConfig(
            seed=7,
            player_count=PlayerCount.TWO_PLAYER,
            controlled_seat=0,
            candidate_agent=modular_agent(),
            opponent_agents=(baseline_agent("baseline-1"),),
            label="2p-smoke",
            metadata=(("fixture", "seed7"),),
        )

        self.assertEqual(config.seed, 7)
        self.assertEqual(config.player_count, PlayerCount.TWO_PLAYER)
        self.assertEqual(config.controlled_seat, 0)
        self.assertEqual(config.candidate_agent.module_path, "agents.orbit_wars_agent")
        self.assertEqual(tuple(opponent.name for opponent in config.opponent_agents), ("baseline-1",))
        self.assertEqual(config.metadata, (("fixture", "seed7"),))

    def test_representative_four_player_match_config_constructs(self) -> None:
        config = MatchConfig(
            seed=11,
            player_count=PlayerCount.FOUR_PLAYER,
            controlled_seat=2,
            candidate_agent=modular_agent(),
            opponent_agents=(
                baseline_agent("baseline-1"),
                baseline_agent("baseline-2"),
                baseline_agent("baseline-3"),
            ),
            label="4p-smoke",
        )

        self.assertEqual(config.player_count, PlayerCount.FOUR_PLAYER)
        self.assertEqual(config.controlled_seat, 2)
        self.assertEqual(len(config.opponent_agents), 3)
        self.assertEqual(config.label, "4p-smoke")

    def test_result_objects_represent_not_run_completed_and_error_states(self) -> None:
        config = MatchConfig(
            seed=7,
            player_count=PlayerCount.TWO_PLAYER,
            controlled_seat=0,
            candidate_agent=modular_agent(),
            opponent_agents=(baseline_agent("baseline"),),
        )
        not_run = MatchResult(config=config)
        completed = MatchResult(
            config=config,
            status=EvaluationStatus.COMPLETED,
            metrics=MatchMetrics(
                final_rank=1,
                final_score=12.5,
                final_planets=8,
                final_ships=150,
                turns_survived=400,
                no_action_count=3,
                error_count=0,
            ),
        )
        errored = MatchResult(
            config=config,
            status=EvaluationStatus.IMPORT_ERROR,
            error_text="ImportError: missing agent",
        )

        self.assertEqual(not_run.status, EvaluationStatus.NOT_RUN)
        self.assertEqual(completed.metrics.final_rank, 1)
        self.assertEqual(completed.metrics.error_count, 0)
        self.assertEqual(errored.status, EvaluationStatus.IMPORT_ERROR)
        self.assertEqual(errored.error_text, "ImportError: missing agent")

    def test_optional_paths_and_metadata_default_safely(self) -> None:
        config = MatchConfig(
            seed=7,
            player_count=PlayerCount.TWO_PLAYER,
            controlled_seat=0,
            candidate_agent=modular_agent(),
            opponent_agents=(baseline_agent("baseline"),),
        )
        result = MatchResult(
            config=config,
            replay_path="artifacts/not-created/replay.json",
            artifact_path="artifacts/not-created/result.json",
        )

        self.assertEqual(config.metadata, ())
        self.assertEqual(result.metadata, ())
        self.assertEqual(result.replay_path, "artifacts/not-created/replay.json")
        self.assertEqual(result.artifact_path, "artifacts/not-created/result.json")

    def test_match_result_to_dict_has_deterministic_field_names(self) -> None:
        config = MatchConfig(
            seed=7,
            player_count=PlayerCount.TWO_PLAYER,
            controlled_seat=0,
            candidate_agent=modular_agent(),
            opponent_agents=(baseline_agent("baseline"),),
            metadata=(("b", "2"), ("a", "1")),
        )
        result = MatchResult(
            config=config,
            status=EvaluationStatus.COMPLETED,
            metrics=MatchMetrics(final_rank=1, final_score=10.0),
            replay_path="replay.json",
            artifact_path="result.json",
            metadata=(("suite", "smoke"),),
        )

        data = result.to_dict()

        self.assertEqual(
            tuple(data.keys()),
            (
                "config",
                "status",
                "metrics",
                "error_text",
                "replay_path",
                "artifact_path",
                "metadata",
            ),
        )
        self.assertEqual(data["status"], "completed")
        self.assertEqual(data["metadata"], {"suite": "smoke"})
        self.assertEqual(data["config"]["metadata"], {"b": "2", "a": "1"})

    def test_match_config_and_result_round_trip_from_dict(self) -> None:
        config = MatchConfig(
            seed=11,
            player_count=PlayerCount.FOUR_PLAYER,
            controlled_seat=1,
            candidate_agent=AgentSpec(
                name="submission",
                source_kind=AgentSourceKind.SUBMISSION_FILE,
                file_path="/tmp/orbit_wars_submission.py",
            ),
            opponent_agents=(
                baseline_agent("baseline-1"),
                baseline_agent("baseline-2"),
                baseline_agent("baseline-3"),
            ),
            label="round-trip",
            metadata=(("mode", "4p"),),
        )
        result = MatchResult(
            config=config,
            status=EvaluationStatus.UNKNOWN_ERROR,
            metrics=MatchMetrics(final_rank=4, error_count=1),
            error_text="RuntimeError: test",
            replay_path="replay.json",
            artifact_path="result.json",
        )

        self.assertEqual(MatchConfig.from_dict(config.to_dict()), config)
        self.assertEqual(MatchResult.from_dict(result.to_dict()), result)

    def test_match_config_from_dict_rejects_malformed_opponent_entry(self) -> None:
        config = MatchConfig(
            seed=11,
            player_count=PlayerCount.FOUR_PLAYER,
            controlled_seat=1,
            candidate_agent=modular_agent(),
            opponent_agents=(
                baseline_agent("baseline-1"),
                baseline_agent("baseline-2"),
                baseline_agent("baseline-3"),
            ),
        )
        data = config.to_dict()
        data["opponent_agents"] = [*data["opponent_agents"], "bad"]

        with self.assertRaisesRegex(
            ValueError,
            r"opponent_agents\[3\] must be a mapping",
        ):
            MatchConfig.from_dict(data)

    def test_invalid_config_shapes_raise_without_running_environment(self) -> None:
        with self.assertRaises(ValueError):
            MatchConfig(
                seed=7,
                player_count=PlayerCount.TWO_PLAYER,
                controlled_seat=2,
                candidate_agent=modular_agent(),
                opponent_agents=(baseline_agent("baseline"),),
            )
        with self.assertRaises(ValueError):
            MatchConfig(
                seed=7,
                player_count=PlayerCount.FOUR_PLAYER,
                controlled_seat=0,
                candidate_agent=modular_agent(),
                opponent_agents=(baseline_agent("baseline"),),
            )

    def test_contract_import_does_not_import_kaggle_environments(self) -> None:
        self.assertNotIn("kaggle_environments", sys.modules)


if __name__ == "__main__":
    unittest.main()
