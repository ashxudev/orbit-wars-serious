"""Tests for Evaluation Harness Cycle 7 submission parity checks."""

from __future__ import annotations

import importlib
import sys
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch

from ow_eval import (
    AgentSourceKind,
    AgentSpec,
    BaselineName,
    EvaluationArtifactConfig,
    EvaluationBatchConfig,
    EvaluationBatchResult,
    EvaluationBatchSummary,
    EvaluationStatus,
    MatchConfig,
    MatchMetrics,
    MatchResult,
    OpponentSpec,
    PlayerCount,
    SubmissionParityComparison,
    SubmissionParityConfig,
    SubmissionParityResult,
    builtin_baseline_spec,
    run_submission_parity_check,
    submission_agent_spec,
)
from scripts.build_submission import write_submission


def parity_match_config(seed: int, label: str | None = None) -> MatchConfig:
    return MatchConfig(
        seed=seed,
        player_count=PlayerCount.TWO_PLAYER,
        controlled_seat=0,
        candidate_agent=builtin_baseline_spec(BaselineName.NOOP, name="placeholder"),
        opponent_agents=(
            OpponentSpec(
                builtin_baseline_spec(BaselineName.NOOP, name="opponent-noop")
            ),
        ),
        label=label,
        metadata=(("episode_steps", "5"),),
    )


def completed_result(
    config: MatchConfig,
    *,
    rank: int = 1,
    score: float = 10.0,
    ships: int = 20,
) -> MatchResult:
    return MatchResult(
        config=config,
        status=EvaluationStatus.COMPLETED,
        metrics=MatchMetrics(
            final_rank=rank,
            final_score=score,
            final_planets=2,
            final_ships=ships,
            final_production=3,
            turns_survived=100,
            error_count=0,
            invalid_action_count=0,
            timeout_count=0,
        ),
    )


class SubmissionParityTests(unittest.TestCase):
    def tearDown(self) -> None:
        for module_name in tuple(sys.modules):
            if module_name == "kaggle_environments" or module_name.startswith(
                "kaggle_environments."
            ):
                sys.modules.pop(module_name, None)

    def test_parity_module_imports_and_exports_are_available(self) -> None:
        module = importlib.import_module("ow_eval.parity")

        self.assertIs(module.SubmissionParityConfig, SubmissionParityConfig)
        self.assertIs(module.SubmissionParityComparison, SubmissionParityComparison)
        self.assertIs(module.SubmissionParityResult, SubmissionParityResult)
        self.assertIs(module.run_submission_parity_check, run_submission_parity_check)
        self.assertIs(module.submission_agent_spec, submission_agent_spec)

    def test_parity_contracts_are_frozen_slotted_and_validate(self) -> None:
        match = parity_match_config(7)
        config = SubmissionParityConfig(matches=(match,))
        comparison = SubmissionParityComparison(
            index=0,
            modular_result=completed_result(match),
            submission_result=completed_result(match),
            status_matches=True,
            metrics_match=True,
            matched=True,
        )
        parity_result = SubmissionParityResult(
            comparisons=(comparison,),
            modular_batch=EvaluationBatchResult(),
            submission_batch=EvaluationBatchResult(),
            passed=True,
            mismatch_count=0,
        )

        with self.assertRaises(FrozenInstanceError):
            config.matches = ()  # type: ignore[misc]
        with self.assertRaises((AttributeError, TypeError)):
            comparison.extra = "nope"  # type: ignore[attr-defined]
        with self.assertRaises(FrozenInstanceError):
            parity_result.passed = False  # type: ignore[misc]
        with self.assertRaisesRegex(ValueError, "matches must be a tuple"):
            SubmissionParityConfig(matches=[match])  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "matches entries must be MatchConfig"):
            SubmissionParityConfig(matches=("bad",))  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "artifact_prefix must be non-empty"):
            SubmissionParityConfig(matches=(), artifact_prefix="")

    def test_submission_agent_spec_uses_submission_file_source(self) -> None:
        spec = submission_agent_spec("/tmp/submission.py", name="bundle")

        self.assertEqual(spec.name, "bundle")
        self.assertEqual(spec.source_kind, AgentSourceKind.SUBMISSION_FILE)
        self.assertEqual(spec.file_path, "/tmp/submission.py")

    def test_rewrites_match_configs_for_modular_and_submission_batches(self) -> None:
        matches = (parity_match_config(7, label="fixed"), parity_match_config(8))
        submission_path = "/tmp/submission.py"
        seen_configs: list[EvaluationBatchConfig] = []

        def fake_batch(config: EvaluationBatchConfig) -> EvaluationBatchResult:
            seen_configs.append(config)
            return EvaluationBatchResult(
                results=tuple(
                    completed_result(match)
                    for match in config.matches
                ),
                summary=EvaluationBatchSummary(
                    total_matches=len(config.matches),
                    completed_count=len(config.matches),
                ),
            )

        with patch("ow_eval.parity.run_evaluation_batch", side_effect=fake_batch):
            result = run_submission_parity_check(
                SubmissionParityConfig(
                    matches=matches,
                    submission_path=submission_path,
                )
            )

        self.assertTrue(result.passed)
        self.assertEqual(len(seen_configs), 2)
        modular_matches = seen_configs[0].matches
        submission_matches = seen_configs[1].matches
        self.assertEqual(
            tuple(match.label for match in modular_matches),
            ("fixed-modular", "match-0001-modular"),
        )
        self.assertEqual(
            tuple(match.label for match in submission_matches),
            ("fixed-submission", "match-0001-submission"),
        )
        self.assertTrue(
            all(
                match.candidate_agent.module_path == "agents.orbit_wars_agent"
                for match in modular_matches
            )
        )
        self.assertTrue(
            all(
                match.candidate_agent.file_path == submission_path
                for match in submission_matches
            )
        )
        self.assertEqual(
            tuple(match.seed for match in submission_matches),
            tuple(match.seed for match in matches),
        )
        self.assertEqual(
            tuple(match.opponent_agents for match in submission_matches),
            tuple(match.opponent_agents for match in matches),
        )

    def test_custom_modular_agent_is_used_when_supplied(self) -> None:
        match = parity_match_config(7)
        custom_agent = AgentSpec(
            name="custom",
            source_kind=AgentSourceKind.MODULAR_AGENT,
            module_path="custom.agent",
        )
        seen_configs: list[EvaluationBatchConfig] = []

        def fake_batch(config: EvaluationBatchConfig) -> EvaluationBatchResult:
            seen_configs.append(config)
            return EvaluationBatchResult(
                results=(completed_result(config.matches[0]),),
                summary=EvaluationBatchSummary(total_matches=1, completed_count=1),
            )

        with patch("ow_eval.parity.run_evaluation_batch", side_effect=fake_batch):
            run_submission_parity_check(
                SubmissionParityConfig(
                    matches=(match,),
                    modular_agent=custom_agent,
                    submission_path="/tmp/submission.py",
                )
            )

        self.assertIs(seen_configs[0].matches[0].candidate_agent, custom_agent)

    def test_internal_submission_build_is_used_when_path_is_missing(self) -> None:
        match = parity_match_config(7)
        seen_configs: list[EvaluationBatchConfig] = []

        def fake_batch(config: EvaluationBatchConfig) -> EvaluationBatchResult:
            seen_configs.append(config)
            return EvaluationBatchResult(
                results=(completed_result(config.matches[0]),),
                summary=EvaluationBatchSummary(total_matches=1, completed_count=1),
            )

        with patch("ow_eval.parity.run_evaluation_batch", side_effect=fake_batch):
            with patch(
                "ow_eval.parity.write_submission",
                return_value=Path("/tmp/generated-submission.py"),
            ) as write_submission_mock:
                run_submission_parity_check(SubmissionParityConfig(matches=(match,)))

        write_submission_mock.assert_called_once()
        self.assertEqual(
            Path(write_submission_mock.call_args.args[0]).name,
            "orbit_wars_submission.py",
        )
        self.assertEqual(
            seen_configs[1].matches[0].candidate_agent.file_path,
            "/tmp/generated-submission.py",
        )

    def test_provided_submission_path_does_not_rebuild(self) -> None:
        match = parity_match_config(7)

        def fake_batch(config: EvaluationBatchConfig) -> EvaluationBatchResult:
            return EvaluationBatchResult(
                results=(completed_result(config.matches[0]),),
                summary=EvaluationBatchSummary(total_matches=1, completed_count=1),
            )

        with patch("ow_eval.parity.run_evaluation_batch", side_effect=fake_batch):
            with patch("ow_eval.parity.write_submission") as write_submission_mock:
                run_submission_parity_check(
                    SubmissionParityConfig(
                        matches=(match,),
                        submission_path="/tmp/provided-submission.py",
                    )
                )

        write_submission_mock.assert_not_called()

    def test_mismatch_reporting_from_mocked_batch_results(self) -> None:
        match = parity_match_config(7)
        modular_result = completed_result(match, rank=1, score=10.0)
        submission_result = completed_result(match, rank=2, score=9.0)
        seen_calls = 0

        def fake_batch(config: EvaluationBatchConfig) -> EvaluationBatchResult:
            nonlocal seen_calls
            seen_calls += 1
            result = modular_result if seen_calls == 1 else submission_result
            return EvaluationBatchResult(
                results=(result,),
                summary=EvaluationBatchSummary(total_matches=1, completed_count=1),
            )

        with patch("ow_eval.parity.run_evaluation_batch", side_effect=fake_batch):
            result = run_submission_parity_check(
                SubmissionParityConfig(
                    matches=(match,),
                    submission_path="/tmp/submission.py",
                )
            )

        self.assertFalse(result.passed)
        self.assertEqual(result.mismatch_count, 1)
        comparison = result.comparisons[0]
        self.assertFalse(comparison.metrics_match)
        self.assertEqual(
            comparison.mismatch_reasons,
            ("final_rank differs", "final_score differs"),
        )

    def test_status_mismatch_reporting_from_mocked_batch_results(self) -> None:
        match = parity_match_config(7)
        modular_result = completed_result(match)
        submission_result = MatchResult(
            config=match,
            status=EvaluationStatus.IMPORT_ERROR,
            error_text="ImportError: bad",
        )
        seen_calls = 0

        def fake_batch(config: EvaluationBatchConfig) -> EvaluationBatchResult:
            nonlocal seen_calls
            seen_calls += 1
            return EvaluationBatchResult(
                results=(modular_result if seen_calls == 1 else submission_result,),
                summary=EvaluationBatchSummary(total_matches=1),
            )

        with patch("ow_eval.parity.run_evaluation_batch", side_effect=fake_batch):
            result = run_submission_parity_check(
                SubmissionParityConfig(
                    matches=(match,),
                    submission_path="/tmp/submission.py",
                )
            )

        self.assertFalse(result.passed)
        self.assertEqual(
            result.comparisons[0].mismatch_reasons,
            (
                "status differs",
                "final_rank differs",
                "final_score differs",
                "final_planets differs",
                "final_ships differs",
                "final_production differs",
                "turns_survived differs",
                "error_count differs",
                "invalid_action_count differs",
                "timeout_count differs",
            ),
        )

    def test_artifact_prefixes_are_collision_free_for_both_batches(self) -> None:
        match = parity_match_config(7)
        artifact_config = EvaluationArtifactConfig(
            output_dir="/tmp/ow-eval-parity",
            prefix="ignored",
        )
        seen_configs: list[EvaluationBatchConfig] = []

        def fake_batch(config: EvaluationBatchConfig) -> EvaluationBatchResult:
            seen_configs.append(config)
            return EvaluationBatchResult(
                results=(completed_result(config.matches[0]),),
                summary=EvaluationBatchSummary(total_matches=1, completed_count=1),
            )

        with patch("ow_eval.parity.run_evaluation_batch", side_effect=fake_batch):
            run_submission_parity_check(
                SubmissionParityConfig(
                    matches=(match,),
                    submission_path="/tmp/submission.py",
                    artifacts=artifact_config,
                )
            )

        self.assertIs(seen_configs[0].artifacts, artifact_config)
        self.assertIs(seen_configs[1].artifacts, artifact_config)
        self.assertEqual(seen_configs[0].artifact_prefix, "parity-modular")
        self.assertEqual(seen_configs[1].artifact_prefix, "parity-submission")

    def test_artifact_prefix_override_is_used(self) -> None:
        match = parity_match_config(7)
        artifact_config = EvaluationArtifactConfig(output_dir="/tmp/ow-eval-parity")
        seen_configs: list[EvaluationBatchConfig] = []

        def fake_batch(config: EvaluationBatchConfig) -> EvaluationBatchResult:
            seen_configs.append(config)
            return EvaluationBatchResult(
                results=(completed_result(config.matches[0]),),
                summary=EvaluationBatchSummary(total_matches=1, completed_count=1),
            )

        with patch("ow_eval.parity.run_evaluation_batch", side_effect=fake_batch):
            run_submission_parity_check(
                SubmissionParityConfig(
                    matches=(match,),
                    submission_path="/tmp/submission.py",
                    artifacts=artifact_config,
                    artifact_prefix="custom",
                )
            )

        self.assertEqual(seen_configs[0].artifact_prefix, "custom-modular")
        self.assertEqual(seen_configs[1].artifact_prefix, "custom-submission")

    def test_bounded_parity_uses_deterministic_runtime_clock(self) -> None:
        from ow_eval import official_runner
        from ow_eval.parity import _bounded_runtime_agent_for_parity

        observed: list[tuple[str, object]] = []
        namespace = {"observed": observed}
        exec(
            "class RuntimeDefaultConfig:\n"
            "    def __init__(self, *, clock):\n"
            "        self.clock = clock\n"
            "def runtime_turn_config_for_observation(\n"
            "    observation, configuration=None, *, defaults=None\n"
            "):\n"
            "    observed.append(('remaining', observation['remainingOverageTime']))\n"
            "    observed.append(('clock', defaults.clock()))\n"
            "    return {'clock': defaults.clock()}\n"
            "def safe_actions_for_observation(\n"
            "    observation, configuration=None, config=None\n"
            "):\n"
            "    observed.append(('config_clock', config['clock']))\n"
            "    return [[4, 0.0, 1]]\n"
            "def agent(observation, configuration=None):\n"
            "    raise AssertionError('raw agent should not be called')\n",
            namespace,
        )
        fake_agent = namespace["agent"]

        def fake_loader(agent_spec: AgentSpec):
            return fake_agent

        original_loader = official_runner.load_agent_callable
        official_runner.load_agent_callable = fake_loader
        try:
            with _bounded_runtime_agent_for_parity():
                bounded_agent = official_runner.load_agent_callable(
                    AgentSpec(
                        name="fake",
                        source_kind=AgentSourceKind.MODULAR_AGENT,
                        module_path="fake",
                    )
                )
                actions = bounded_agent({"remainingOverageTime": 0.01}, {})
        finally:
            official_runner.load_agent_callable = original_loader

        self.assertEqual(actions, [[4, 0.0, 1]])
        self.assertEqual(
            observed,
            [
                ("remaining", 1.25),
                ("clock", 100.0),
                ("config_clock", 100.0),
            ],
        )

    def test_real_parity_check_builds_temporary_submission_and_passes(self) -> None:
        result = run_submission_parity_check(
            SubmissionParityConfig(
                matches=(parity_match_config(7, label="parity-real"),),
            )
        )

        self.assertTrue(result.passed)
        self.assertEqual(result.mismatch_count, 0)
        self.assertEqual(len(result.comparisons), 1)
        self.assertTrue(result.comparisons[0].matched)
        self.assertEqual(result.modular_batch.summary.completed_count, 1)
        self.assertEqual(result.submission_batch.summary.completed_count, 1)

    def test_real_parity_check_uses_provided_submission_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            submission_path = write_submission(Path(tmp) / "submission.py")

            result = run_submission_parity_check(
                SubmissionParityConfig(
                    matches=(parity_match_config(7, label="provided"),),
                    submission_path=submission_path,
                )
            )

            self.assertTrue(submission_path.is_file())

        self.assertTrue(result.passed)
        self.assertEqual(result.mismatch_count, 0)

    def test_real_parity_artifacts_are_written_under_temp_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_submission_parity_check(
                SubmissionParityConfig(
                    matches=(parity_match_config(7, label="artifact"),),
                    artifacts=EvaluationArtifactConfig(output_dir=tmp),
                )
            )
            artifact_names = sorted(path.name for path in Path(tmp).iterdir())

        self.assertTrue(result.passed)
        self.assertEqual(
            artifact_names,
            [
                "parity-modular-match-0000-replay.json",
                "parity-modular-match-0000-result.json",
                "parity-submission-match-0000-replay.json",
                "parity-submission-match-0000-result.json",
            ],
        )


if __name__ == "__main__":
    unittest.main()
