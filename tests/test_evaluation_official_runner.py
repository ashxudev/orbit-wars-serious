"""Tests for Evaluation Harness Cycle 1 official match runner."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from agents import RuntimeBudgetConfig, RuntimeTurnConfig
from ow_eval import (
    AgentSourceKind,
    AgentSpec,
    BaselineName,
    EvaluationStatus,
    MatchConfig,
    MatchResult,
    OpponentSpec,
    PlayerCount,
    builtin_baseline_spec,
    run_official_match,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def candidate_config(
    *,
    seed: int = 7,
    controlled_seat: int = 0,
    player_count: PlayerCount = PlayerCount.TWO_PLAYER,
    candidate_agent: AgentSpec | None = None,
    opponent_agents: tuple[OpponentSpec, ...] | None = None,
    metadata: tuple[tuple[str, str], ...] = (),
) -> MatchConfig:
    if candidate_agent is None:
        candidate_agent = AgentSpec(
            name="candidate",
            source_kind=AgentSourceKind.MODULAR_AGENT,
            module_path="agents.orbit_wars_agent",
        )
    if opponent_agents is None:
        opponent_agents = tuple(
            builtin_opponent(f"idle-{index}")
            for index in range(player_count.value - 1)
        )
    return MatchConfig(
        seed=seed,
        player_count=player_count,
        controlled_seat=controlled_seat,
        candidate_agent=candidate_agent,
        opponent_agents=opponent_agents,
        metadata=metadata,
    )


def builtin_opponent(name: str) -> OpponentSpec:
    return OpponentSpec(
        AgentSpec(
            name=name,
            source_kind=AgentSourceKind.BUILTIN_BASELINE,
        )
    )


class FakeOrbitWarsEnvironment:
    def __init__(self) -> None:
        self.reset_players: int | None = None
        self.run_results: list[object] = []

    def reset(self, players: int) -> None:
        self.reset_players = players

    def run(self, agents: list[object]) -> list[object]:
        self.run_results = [
            agent({"step": 0}, {})
            for agent in agents
        ]
        return []


class EvaluationOfficialRunnerTests(unittest.TestCase):
    def test_ow_eval_import_does_not_eagerly_import_kaggle_environments(self) -> None:
        script = (
            "import sys\n"
            "sys.modules.pop('kaggle_environments', None)\n"
            "import ow_eval\n"
            "print('kaggle_environments' in sys.modules)\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.stdout.strip(), "False")

    def test_real_two_player_official_match_completes(self) -> None:
        config = candidate_config()

        fast_no_action_config = RuntimeTurnConfig(
            budget_config=RuntimeBudgetConfig(turn_budget_seconds=0.0),
        )
        with patch(
            "agents.orbit_wars_agent.runtime_turn_config_for_observation",
            return_value=fast_no_action_config,
        ):
            result = run_official_match(config)

        self.assertIsInstance(result, MatchResult)
        self.assertIs(result.config, config)
        self.assertEqual(result.status, EvaluationStatus.COMPLETED)
        self.assertIsNone(result.error_text)
        self.assertIsNone(result.replay_path)
        self.assertIsNone(result.artifact_path)

    def test_real_builtin_baseline_official_match_completes(self) -> None:
        config = candidate_config(
            candidate_agent=builtin_baseline_spec(
                BaselineName.NOOP,
                name="candidate-noop",
            ),
            opponent_agents=(
                OpponentSpec(
                    builtin_baseline_spec(
                        BaselineName.NEAREST_NEUTRAL,
                        name="nearest-neutral",
                    )
                ),
            ),
        )

        result = run_official_match(config)

        self.assertEqual(result.status, EvaluationStatus.COMPLETED)
        self.assertIsNone(result.error_text)

    def test_runner_respects_controlled_seat_when_building_players(self) -> None:
        fake_env = FakeOrbitWarsEnvironment()
        fake_kaggle = types.ModuleType("kaggle_environments")
        make_calls: list[tuple[str, dict[str, object], bool]] = []

        def make(name: str, configuration: dict[str, object], debug: bool = False):
            make_calls.append((name, configuration, debug))
            return fake_env

        fake_kaggle.make = make  # type: ignore[attr-defined]
        fake_candidate_module = types.ModuleType("fake_candidate_agent")

        def fake_agent(observation: object, configuration: object = None):
            return [["candidate"]]

        fake_candidate_module.agent = fake_agent  # type: ignore[attr-defined]
        config = candidate_config(
            seed=42,
            controlled_seat=2,
            player_count=PlayerCount.FOUR_PLAYER,
            candidate_agent=AgentSpec(
                name="candidate",
                source_kind=AgentSourceKind.MODULAR_AGENT,
                module_path="fake_candidate_agent",
            ),
            metadata=(("episode_steps", "5"),),
        )

        with patch.dict(
            sys.modules,
            {
                "kaggle_environments": fake_kaggle,
                "fake_candidate_agent": fake_candidate_module,
            },
        ):
            result = run_official_match(config)

        self.assertEqual(result.status, EvaluationStatus.COMPLETED)
        self.assertEqual(
            make_calls,
            [("orbit_wars", {"seed": 42, "episodeSteps": 5}, True)],
        )
        self.assertEqual(fake_env.reset_players, 4)
        self.assertEqual(fake_env.run_results, [[], [], [["candidate"]], []])

    def test_runner_attaches_candidate_runtime_diagnostic_summary(self) -> None:
        fake_env = FakeOrbitWarsEnvironment()
        fake_kaggle = types.ModuleType("kaggle_environments")

        def make(name: str, configuration: dict[str, object], debug: bool = False):
            return fake_env

        fake_kaggle.make = make  # type: ignore[attr-defined]
        fake_candidate_module = types.ModuleType("diagnostic_candidate_agent")
        exec(
            "def last_runtime_diagnostic_metadata():\n"
            "    return (\n"
            "        ('runtime_diagnostic_status', 'no_action'),\n"
            "        ('runtime_diagnostic_no_action_reason', 'strategy_selection_no_action'),\n"
            "        ('runtime_diagnostic_action_count', '0'),\n"
            "        ('runtime_diagnostic_candidate_count', '3'),\n"
            "        ('runtime_diagnostic_evaluation_count', '3'),\n"
            "        ('runtime_diagnostic_selection_status', 'no_action'),\n"
            "    )\n"
            "def safe_actions_for_observation(observation, configuration=None):\n"
            "    return []\n"
            "def agent(observation, configuration=None):\n"
            "    return []\n",
            fake_candidate_module.__dict__,
        )
        config = candidate_config(
            candidate_agent=AgentSpec(
                name="candidate",
                source_kind=AgentSourceKind.MODULAR_AGENT,
                module_path="diagnostic_candidate_agent",
            ),
        )

        with patch.dict(
            sys.modules,
            {
                "kaggle_environments": fake_kaggle,
                "diagnostic_candidate_agent": fake_candidate_module,
            },
        ):
            result = run_official_match(config)

        metadata = dict(result.metadata)
        self.assertEqual(metadata["runtime_diagnostic_turn_count"], "1")
        self.assertEqual(metadata["runtime_diagnostic_no_action_turn_count"], "1")
        self.assertEqual(
            metadata["runtime_diagnostic_primary_no_action_reason"],
            "strategy_selection_no_action",
        )
        self.assertEqual(
            metadata["runtime_diagnostic_no_action_reasons"],
            "strategy_selection_no_action:1",
        )

    def test_candidate_import_failure_returns_import_error(self) -> None:
        config = candidate_config(
            candidate_agent=AgentSpec(
                name="missing",
                source_kind=AgentSourceKind.MODULAR_AGENT,
                module_path="missing_candidate_module",
            )
        )

        result = run_official_match(config)

        self.assertEqual(result.status, EvaluationStatus.IMPORT_ERROR)
        self.assertIsNotNone(result.error_text)
        self.assertIn("ModuleNotFoundError", result.error_text)

    def test_candidate_callable_lookup_failure_returns_import_error(self) -> None:
        config = candidate_config(
            candidate_agent=AgentSpec(
                name="bad-callable",
                source_kind=AgentSourceKind.MODULAR_AGENT,
                module_path="math",
                callable_name="missing_agent",
            )
        )

        result = run_official_match(config)

        self.assertEqual(result.status, EvaluationStatus.IMPORT_ERROR)
        self.assertIsNotNone(result.error_text)
        self.assertIn("AttributeError", result.error_text)

    def test_runner_places_candidate_and_file_opponents_in_seat_order(self) -> None:
        fake_env = FakeOrbitWarsEnvironment()
        fake_kaggle = types.ModuleType("kaggle_environments")

        def make(name: str, configuration: dict[str, object], debug: bool = False):
            return fake_env

        fake_kaggle.make = make  # type: ignore[attr-defined]
        with tempfile.TemporaryDirectory() as tmp:
            candidate_path = Path(tmp) / "candidate.py"
            first_opponent_path = Path(tmp) / "first_opponent.py"
            second_opponent_path = Path(tmp) / "second_opponent.py"
            candidate_path.write_text(
                "def agent(observation, configuration=None):\n"
                "    return [['candidate']]\n",
                encoding="utf-8",
            )
            first_opponent_path.write_text(
                "def agent(observation, configuration=None):\n"
                "    return [['first']]\n",
                encoding="utf-8",
            )
            second_opponent_path.write_text(
                "def agent(observation, configuration=None):\n"
                "    return [['second']]\n",
                encoding="utf-8",
            )
            config = candidate_config(
                controlled_seat=1,
                player_count=PlayerCount.FOUR_PLAYER,
                candidate_agent=AgentSpec(
                    name="candidate",
                    source_kind=AgentSourceKind.SUBMISSION_FILE,
                    file_path=str(candidate_path),
                ),
                opponent_agents=(
                    OpponentSpec(
                        AgentSpec(
                            name="first",
                            source_kind=AgentSourceKind.PYTHON_FILE,
                            file_path=str(first_opponent_path),
                        )
                    ),
                    builtin_opponent("idle"),
                    OpponentSpec(
                        AgentSpec(
                            name="second",
                            source_kind=AgentSourceKind.SUBMISSION_FILE,
                            file_path=str(second_opponent_path),
                        )
                    ),
                ),
            )

            with patch.dict(sys.modules, {"kaggle_environments": fake_kaggle}):
                result = run_official_match(config)

        self.assertEqual(result.status, EvaluationStatus.COMPLETED)
        self.assertEqual(
            fake_env.run_results,
            [[["first"]], [["candidate"]], [], [["second"]]],
        )

    def test_missing_submission_file_candidate_returns_import_error(self) -> None:
        config = candidate_config(
            candidate_agent=AgentSpec(
                name="submission",
                source_kind=AgentSourceKind.SUBMISSION_FILE,
                file_path="/tmp/missing-ow-eval-submission.py",
            )
        )

        result = run_official_match(config)

        self.assertEqual(result.status, EvaluationStatus.IMPORT_ERROR)
        self.assertEqual(
            result.error_text,
            "ValueError: submission_file file not found: "
            "/tmp/missing-ow-eval-submission.py",
        )

    def test_environment_creation_failure_returns_env_error(self) -> None:
        fake_kaggle = types.ModuleType("kaggle_environments")

        def make(name: str, configuration: dict[str, object], debug: bool = False):
            raise RuntimeError("env failed")

        fake_kaggle.make = make  # type: ignore[attr-defined]

        with patch.dict(sys.modules, {"kaggle_environments": fake_kaggle}):
            result = run_official_match(candidate_config())

        self.assertEqual(result.status, EvaluationStatus.ENV_ERROR)
        self.assertEqual(result.error_text, "RuntimeError: env failed")

    def test_candidate_runtime_failure_returns_agent_error(self) -> None:
        fake_env = FakeOrbitWarsEnvironment()
        fake_kaggle = types.ModuleType("kaggle_environments")

        def make(name: str, configuration: dict[str, object], debug: bool = False):
            return fake_env

        fake_kaggle.make = make  # type: ignore[attr-defined]
        fake_candidate_module = types.ModuleType("failing_candidate_agent")

        def failing_agent(observation: object, configuration: object = None):
            raise RuntimeError("agent boom")

        fake_candidate_module.agent = failing_agent  # type: ignore[attr-defined]
        config = candidate_config(
            candidate_agent=AgentSpec(
                name="candidate",
                source_kind=AgentSourceKind.MODULAR_AGENT,
                module_path="failing_candidate_agent",
            )
        )

        with patch.dict(
            sys.modules,
            {
                "kaggle_environments": fake_kaggle,
                "failing_candidate_agent": fake_candidate_module,
            },
        ):
            result = run_official_match(config)

        self.assertEqual(result.status, EvaluationStatus.AGENT_ERROR)
        self.assertEqual(
            result.error_text,
            "AgentExecutionError: candidate: RuntimeError: agent boom",
        )


if __name__ == "__main__":
    unittest.main()
