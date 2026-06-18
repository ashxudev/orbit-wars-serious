"""Tests for Evaluation Harness Cycle 5 match metrics extraction."""

from __future__ import annotations

import importlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from ow_eval import (
    AgentSourceKind,
    AgentSpec,
    BaselineName,
    EvaluationArtifactConfig,
    EvaluationStatus,
    MatchConfig,
    MatchMetrics,
    MatchResult,
    OpponentSpec,
    PlayerCount,
    builtin_baseline_spec,
    extract_match_metrics,
    run_official_match,
)


def metric_observation(
    *,
    player: int = 0,
    planets: list[list[object]] | None = None,
    fleets: list[list[object]] | None = None,
) -> dict[str, object]:
    planet_rows = planets or [
        [1, 0, 0.0, 0.0, 0.5, 10, 2],
        [2, 0, 1.0, 0.0, 0.5, 5, 3],
        [3, 1, 2.0, 0.0, 0.5, 8, 1],
        [4, -1, 3.0, 0.0, 0.5, 4, 1],
    ]
    return {
        "step": 0,
        "player": player,
        "planets": planet_rows,
        "fleets": fleets or [[100, 0, 0.5, 0.5, 0.0, 1, 7]],
        "initial_planets": planet_rows,
        "remainingOverageTime": 60.0,
    }


def step_record(
    *,
    status: str = "ACTIVE",
    reward: object = 0,
    action: object = None,
    observation: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "status": status,
        "reward": reward,
        "action": [] if action is None else action,
        "observation": observation if observation is not None else metric_observation(),
    }


def replay_payload(
    *,
    rewards: object = (3, 5, 3),
    controlled_records: tuple[dict[str, object], ...] | None = None,
) -> dict[str, object]:
    records = controlled_records or (
        step_record(status="ACTIVE", reward=0, action=[]),
        step_record(status="ACTIVE", reward=0, action=[[1, 0.0, 1]]),
        step_record(status="DONE", reward=3, action=[], observation=metric_observation()),
    )
    return {
        "rewards": list(rewards) if isinstance(rewards, tuple) else rewards,
        "steps": [
            [
                controlled_record,
                step_record(status="ACTIVE", reward=0, action=[]),
                step_record(status="ACTIVE", reward=0, action=[]),
            ]
            for controlled_record in records
        ],
    }


class FakeOrbitWarsEnvironment:
    def __init__(self, replay: dict[str, object]) -> None:
        self.replay = replay

    def reset(self, players: int) -> None:
        self.players = players

    def run(self, agents: list[object]) -> list[object]:
        for agent in agents:
            agent({"step": 0}, {})
        return []

    def toJSON(self) -> dict[str, object]:
        return self.replay


class EvaluationMetricTests(unittest.TestCase):
    def tearDown(self) -> None:
        for module_name in tuple(sys.modules):
            if module_name == "kaggle_environments" or module_name.startswith(
                "kaggle_environments."
            ):
                sys.modules.pop(module_name, None)

    def test_metrics_module_imports_and_export_are_available(self) -> None:
        module = importlib.import_module("ow_eval.metrics")

        self.assertIs(module.extract_match_metrics, extract_match_metrics)

    def test_extracts_rank_score_final_board_and_action_metrics(self) -> None:
        metrics = extract_match_metrics(replay_payload(), controlled_seat=0)

        self.assertEqual(metrics.final_rank, 2)
        self.assertEqual(metrics.final_score, 3.0)
        self.assertEqual(metrics.final_planets, 2)
        self.assertEqual(metrics.final_ships, 22)
        self.assertEqual(metrics.final_production, 5)
        self.assertEqual(metrics.turns_survived, 3)
        self.assertEqual(metrics.no_action_count, 2)
        self.assertEqual(metrics.error_count, 0)
        self.assertEqual(metrics.invalid_action_count, 0)
        self.assertEqual(metrics.timeout_count, 0)

    def test_tied_rewards_share_rank(self) -> None:
        metrics = extract_match_metrics(
            replay_payload(rewards=(3, 3, 2)),
            controlled_seat=0,
        )

        self.assertEqual(metrics.final_rank, 1)

    def test_falls_back_to_final_step_reward_when_top_level_reward_missing(self) -> None:
        metrics = extract_match_metrics(
            replay_payload(rewards=None),
            controlled_seat=0,
        )

        self.assertIsNone(metrics.final_rank)
        self.assertEqual(metrics.final_score, 3.0)

    def test_missing_optional_observation_degrades_to_none_fields(self) -> None:
        records = (
            {
                "status": "ACTIVE",
                "reward": 1,
                "action": [],
            },
        )

        metrics = extract_match_metrics(
            replay_payload(rewards=None, controlled_records=records),
            controlled_seat=0,
        )

        self.assertIsNone(metrics.final_planets)
        self.assertIsNone(metrics.final_ships)
        self.assertIsNone(metrics.final_production)
        self.assertEqual(metrics.turns_survived, 1)
        self.assertEqual(metrics.no_action_count, 1)

    def test_empty_steps_degrade_to_empty_count_metrics(self) -> None:
        metrics = extract_match_metrics({"steps": []}, controlled_seat=0)

        self.assertEqual(
            metrics,
            MatchMetrics(
                turns_survived=0,
                no_action_count=0,
                error_count=0,
                invalid_action_count=0,
                timeout_count=0,
            ),
        )

    def test_error_status_counts_and_first_terminal_turn(self) -> None:
        records = (
            step_record(status="ACTIVE", action=[]),
            step_record(status="INVALID", action=[[1, 0.0, 99]]),
            step_record(status="TIMEOUT", action=[]),
        )

        metrics = extract_match_metrics(
            replay_payload(rewards=(0, 1), controlled_records=records),
            controlled_seat=0,
        )

        self.assertEqual(metrics.turns_survived, 2)
        self.assertEqual(metrics.no_action_count, 2)
        self.assertEqual(metrics.error_count, 2)
        self.assertEqual(metrics.invalid_action_count, 1)
        self.assertEqual(metrics.timeout_count, 1)

    def test_malformed_required_replay_shapes_raise_clear_value_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "replay_payload must be a mapping"):
            extract_match_metrics([], controlled_seat=0)  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "steps must be a sequence"):
            extract_match_metrics({}, controlled_seat=0)
        with self.assertRaisesRegex(ValueError, r"steps\[0\] must be a sequence"):
            extract_match_metrics({"steps": [{}]}, controlled_seat=0)
        with self.assertRaisesRegex(
            ValueError,
            r"steps\[0\] missing controlled seat 1",
        ):
            extract_match_metrics({"steps": [[{}]]}, controlled_seat=1)
        with self.assertRaisesRegex(
            ValueError,
            r"steps\[0\]\[0\] must be a mapping",
        ):
            extract_match_metrics({"steps": [[[1]]]}, controlled_seat=0)

    def test_controlled_seat_validation(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "controlled_seat must be a non-negative integer",
        ):
            extract_match_metrics({"steps": []}, controlled_seat=-1)
        with self.assertRaisesRegex(
            ValueError,
            "controlled_seat must be a non-negative integer",
        ):
            extract_match_metrics({"steps": []}, controlled_seat=True)  # type: ignore[arg-type]

    def test_run_official_match_attaches_completed_metrics(self) -> None:
        config = metrics_match_config()

        result = run_official_match(config)

        self.assertEqual(result.status, EvaluationStatus.COMPLETED)
        self.assertIsNotNone(result.metrics.final_rank)
        self.assertIsNotNone(result.metrics.final_score)
        self.assertIsNotNone(result.metrics.turns_survived)
        self.assertIsNotNone(result.metrics.final_planets)
        self.assertIsNotNone(result.metrics.final_ships)

    def test_run_official_match_artifact_includes_populated_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = metrics_match_config(label="metrics artifact")

            result = run_official_match(
                config,
                artifacts=EvaluationArtifactConfig(output_dir=tmp),
            )

            artifact_data = Path(result.artifact_path or "").read_text(encoding="utf-8")
            artifact_result = MatchResult.from_dict(json.loads(artifact_data))

        self.assertEqual(artifact_result.metrics, result.metrics)
        self.assertIsNotNone(artifact_result.metrics.turns_survived)

    def test_run_official_match_attaches_metrics_to_error_with_safe_replay(self) -> None:
        fake_env = FakeOrbitWarsEnvironment(replay_payload())
        fake_kaggle = fake_kaggle_module(fake_env)
        failing_module = types.ModuleType("metrics_failing_agent")

        def failing_agent(observation: object, configuration: object = None):
            raise RuntimeError("boom")

        failing_module.agent = failing_agent  # type: ignore[attr-defined]
        config = metrics_match_config(
            candidate_agent=AgentSpec(
                name="candidate",
                source_kind=AgentSourceKind.MODULAR_AGENT,
                module_path="metrics_failing_agent",
            )
        )

        with patch.dict(
            sys.modules,
            {
                "kaggle_environments": fake_kaggle,
                "metrics_failing_agent": failing_module,
            },
        ):
            result = run_official_match(config)

        self.assertEqual(result.status, EvaluationStatus.AGENT_ERROR)
        self.assertEqual(result.metrics.final_score, 3.0)
        self.assertEqual(result.metrics.turns_survived, 3)


def metrics_match_config(
    *,
    label: str | None = "metrics smoke",
    candidate_agent: AgentSpec | None = None,
) -> MatchConfig:
    return MatchConfig(
        seed=7,
        player_count=PlayerCount.TWO_PLAYER,
        controlled_seat=0,
        candidate_agent=(
            candidate_agent
            or builtin_baseline_spec(BaselineName.NOOP, name="candidate-noop")
        ),
        opponent_agents=(
            OpponentSpec(
                builtin_baseline_spec(BaselineName.NOOP, name="opponent-noop")
            ),
        ),
        label=label,
    )


def fake_kaggle_module(fake_env: FakeOrbitWarsEnvironment) -> types.ModuleType:
    module = types.ModuleType("kaggle_environments")

    def make(name: str, configuration: dict[str, object], debug: bool = False):
        return fake_env

    module.make = make  # type: ignore[attr-defined]
    return module


if __name__ == "__main__":
    unittest.main()
