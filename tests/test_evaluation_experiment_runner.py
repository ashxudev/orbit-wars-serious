"""Tests for Evaluation Harness Cycle 13 experiment manifest runner."""

from __future__ import annotations

import importlib
import json
import unittest
from dataclasses import FrozenInstanceError
from unittest.mock import patch

from ow_eval import (
    AgentSourceKind,
    AgentSpec,
    BaselineName,
    DEFAULT_EVALUATION_ARTIFACT_DIR,
    EvaluationArtifactConfig,
    EvaluationBatchConfig,
    EvaluationBatchResult,
    EvaluationStatus,
    ExperimentManifest,
    ExperimentRunConfig,
    ExperimentRunResult,
    ExperimentScenario,
    MatchConfig,
    MatchMetrics,
    MatchResult,
    OpponentSpec,
    PlayerCount,
    builtin_baseline_spec,
    run_experiment_manifest,
    summarize_match_results,
)


def modular_candidate(name: str = "candidate") -> AgentSpec:
    return AgentSpec(
        name=name,
        source_kind=AgentSourceKind.MODULAR_AGENT,
        module_path="agents.orbit_wars_agent",
    )


def noop_opponent(name: str = "opponent") -> OpponentSpec:
    return OpponentSpec(builtin_baseline_spec(BaselineName.NOOP, name=name))


def scenario(seed: int, label: str) -> ExperimentScenario:
    return ExperimentScenario(
        seed=seed,
        player_count=PlayerCount.TWO_PLAYER,
        controlled_seat=0,
        opponent_agents=(noop_opponent(f"opponent-{seed}"),),
        label=label,
        metadata=(("scenario", label),),
    )


def manifest(*scenarios: ExperimentScenario) -> ExperimentManifest:
    return ExperimentManifest(
        name="experiment-smoke",
        candidate_agent=modular_candidate("candidate-agent"),
        scenarios=tuple(scenarios),
        description="Local smoke experiment",
        version="v2",
        metadata=(("suite", "runner"),),
    )


def result_for_match(
    match: MatchConfig,
    *,
    final_rank: int | None = 1,
    final_score: float | None = 10.0,
    status: EvaluationStatus = EvaluationStatus.COMPLETED,
    error_text: str | None = None,
) -> MatchResult:
    return MatchResult(
        config=match,
        status=status,
        metrics=MatchMetrics(
            final_rank=final_rank,
            final_score=final_score,
            turns_survived=100,
        ),
        error_text=error_text,
    )


def batch_result(*results: MatchResult) -> EvaluationBatchResult:
    result_tuple = tuple(results)
    return EvaluationBatchResult(
        results=result_tuple,
        summary=summarize_match_results(result_tuple),
    )


class EvaluationExperimentRunnerTests(unittest.TestCase):
    def test_runner_module_imports_and_exports_are_available(self) -> None:
        module = importlib.import_module("ow_eval.experiment_runner")

        self.assertIs(module.ExperimentRunConfig, ExperimentRunConfig)
        self.assertIs(module.ExperimentRunResult, ExperimentRunResult)
        self.assertIs(module.run_experiment_manifest, run_experiment_manifest)

    def test_runner_contracts_are_frozen_slotted_and_validate(self) -> None:
        run_config = ExperimentRunConfig(commit="abc123", notes=("note",))
        experiment = manifest()
        empty_batch = batch_result()
        run_result = ExperimentRunResult(
            manifest=experiment,
            matches=(),
            batch_result=empty_batch,
            scoreboard_record=run_experiment_manifest_with_batch(
                experiment,
                empty_batch,
            ).scoreboard_record,
            analysis_pack=run_experiment_manifest_with_batch(
                experiment,
                empty_batch,
            ).analysis_pack,
            summary_text="summary",
        )

        with self.assertRaises(FrozenInstanceError):
            run_config.commit = "changed"  # type: ignore[misc]
        with self.assertRaises((AttributeError, TypeError)):
            run_result.extra = "nope"  # type: ignore[attr-defined]
        with self.assertRaisesRegex(ValueError, "commit"):
            ExperimentRunConfig(commit="")
        with self.assertRaisesRegex(ValueError, "notes"):
            ExperimentRunConfig(notes=["bad"])  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "artifact_prefix"):
            ExperimentRunConfig(artifact_prefix="")

    def test_manifest_expansion_order_is_passed_to_batch_config(self) -> None:
        experiment = manifest(scenario(7, "first"), scenario(8, "second"))
        seen_configs: list[EvaluationBatchConfig] = []

        def fake_batch(config: EvaluationBatchConfig) -> EvaluationBatchResult:
            seen_configs.append(config)
            return batch_result(
                result_for_match(config.matches[0], final_rank=1),
                result_for_match(config.matches[1], final_rank=2, final_score=4.0),
            )

        with patch(
            "ow_eval.experiment_runner.run_evaluation_batch",
            side_effect=fake_batch,
        ):
            result = run_experiment_manifest(experiment)

        self.assertEqual(len(seen_configs), 1)
        batch_config = seen_configs[0]
        self.assertEqual(tuple(match.seed for match in batch_config.matches), (7, 8))
        self.assertEqual(
            tuple(match.label for match in result.matches),
            ("first", "second"),
        )
        self.assertIsInstance(batch_config.artifacts, EvaluationArtifactConfig)
        self.assertEqual(batch_config.artifacts.output_dir, DEFAULT_EVALUATION_ARTIFACT_DIR)
        self.assertEqual(batch_config.artifact_prefix, "experiment-smoke")
        self.assertEqual(result.matches, batch_config.matches)
        self.assertEqual(result.batch_result.results[1].metrics.final_rank, 2)

    def test_scoreboard_fields_are_derived_from_manifest_and_config(self) -> None:
        experiment = manifest(scenario(7, "only"))
        config = ExperimentRunConfig(commit="abc123", notes=("candidate smoke",))

        run_result = run_experiment_manifest_with_batch(
            experiment,
            batch_result(result_for_match_from_manifest(experiment, final_rank=1)),
            config=config,
        )

        record = run_result.scoreboard_record
        self.assertEqual(record.agent_name, "candidate-agent")
        self.assertEqual(record.agent_version, "v2")
        self.assertEqual(record.commit, "abc123")
        self.assertEqual(record.scenario_set, "experiment-smoke")
        self.assertEqual(record.notes, ("candidate smoke",))
        self.assertEqual(record.metadata, (("suite", "runner"),))
        self.assertEqual(record.match_count, 1)
        self.assertEqual(record.win_count, 1)

    def test_analysis_pack_is_included_in_result(self) -> None:
        experiment = manifest(scenario(7, "win"), scenario(8, "loss"))
        matches = tuple(
            MatchConfig(
                seed=scenario.seed,
                player_count=scenario.player_count,
                controlled_seat=scenario.controlled_seat,
                candidate_agent=experiment.candidate_agent,
                opponent_agents=scenario.opponent_agents,
                label=scenario.label,
                metadata=scenario.metadata,
            )
            for scenario in experiment.scenarios
        )
        run_result = run_experiment_manifest_with_batch(
            experiment,
            batch_result(
                result_for_match(matches[0], final_rank=1),
                result_for_match(matches[1], final_rank=2),
            ),
        )

        self.assertEqual(run_result.analysis_pack.total_results, 2)
        self.assertEqual(run_result.analysis_pack.included_count, 1)
        self.assertEqual(run_result.analysis_pack.items[0].label, "loss")
        self.assertIn("analysis_items=1", run_result.summary_text)

    def test_empty_manifest_behavior_is_deterministic(self) -> None:
        experiment = manifest()

        run_result = run_experiment_manifest_with_batch(experiment, batch_result())

        self.assertEqual(run_result.matches, ())
        self.assertEqual(run_result.batch_result.results, ())
        self.assertEqual(run_result.scoreboard_record.match_count, 0)
        self.assertEqual(run_result.analysis_pack.items, ())
        self.assertEqual(
            run_result.summary_text,
            (
                "experiment=experiment-smoke matches=0 completed=0 errors=0 "
                "win_rate=none mean_rank=none analysis_items=0"
            ),
        )

    def test_to_dict_output_is_json_safe(self) -> None:
        experiment = manifest(scenario(7, "json"))
        run_result = run_experiment_manifest_with_batch(
            experiment,
            batch_result(result_for_match_from_manifest(experiment, final_rank=2)),
        )

        encoded = json.dumps(run_result.to_dict(), sort_keys=True)
        decoded = json.loads(encoded)

        self.assertEqual(decoded["manifest"]["name"], "experiment-smoke")
        self.assertEqual(decoded["matches"][0]["seed"], 7)
        self.assertEqual(decoded["batch_result"]["summary"]["total_matches"], 1)
        self.assertEqual(decoded["scoreboard_record"]["agent_name"], "candidate-agent")
        self.assertEqual(decoded["analysis_pack"]["included_count"], 1)
        self.assertIn("summary_text", decoded)

    def test_config_to_dict_includes_artifact_settings(self) -> None:
        artifact_config = EvaluationArtifactConfig(
            output_dir="/tmp/ow-eval-experiment",
            write_replay=False,
            prefix="base",
        )
        config = ExperimentRunConfig(
            commit="abc123",
            notes=("note",),
            artifacts=artifact_config,
            artifact_prefix="experiment",
        )

        data = config.to_dict()

        self.assertEqual(data["commit"], "abc123")
        self.assertEqual(data["notes"], ["note"])
        self.assertEqual(data["artifact_prefix"], "experiment")
        self.assertEqual(
            data["artifacts"],
            {
                "output_dir": "/tmp/ow-eval-experiment",
                "write_replay": False,
                "write_result": True,
                "prefix": "base",
            },
        )

    def test_artifact_config_is_passed_to_batch_runner_when_configured(self) -> None:
        experiment = manifest(scenario(7, "artifact"))
        artifact_config = EvaluationArtifactConfig(output_dir="/tmp/ow-eval-runner")
        seen_configs: list[EvaluationBatchConfig] = []

        def fake_batch(config: EvaluationBatchConfig) -> EvaluationBatchResult:
            seen_configs.append(config)
            return batch_result(result_for_match(config.matches[0]))

        with patch(
            "ow_eval.experiment_runner.run_evaluation_batch",
            side_effect=fake_batch,
        ):
            run_experiment_manifest(
                experiment,
                ExperimentRunConfig(
                    artifacts=artifact_config,
                    artifact_prefix="runner",
                ),
            )

        self.assertIs(seen_configs[0].artifacts, artifact_config)
        self.assertEqual(seen_configs[0].artifact_prefix, "runner")

    def test_non_manifest_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "manifest"):
            run_experiment_manifest("bad")  # type: ignore[arg-type]


def run_experiment_manifest_with_batch(
    experiment: ExperimentManifest,
    batch: EvaluationBatchResult,
    config: ExperimentRunConfig | None = None,
) -> ExperimentRunResult:
    with patch(
        "ow_eval.experiment_runner.run_evaluation_batch",
        return_value=batch,
    ):
        return run_experiment_manifest(experiment, config)


def result_for_match_from_manifest(
    experiment: ExperimentManifest,
    *,
    final_rank: int,
) -> MatchResult:
    matches = tuple(
        MatchConfig(
            seed=scenario.seed,
            player_count=scenario.player_count,
            controlled_seat=scenario.controlled_seat,
            candidate_agent=experiment.candidate_agent,
            opponent_agents=scenario.opponent_agents,
            label=scenario.label,
            metadata=scenario.metadata,
        )
        for scenario in experiment.scenarios
    )
    return result_for_match(matches[0], final_rank=final_rank)


if __name__ == "__main__":
    unittest.main()
