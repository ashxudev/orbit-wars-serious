"""Tests for Evaluation Harness Cycle 12 experiment manifests."""

from __future__ import annotations

import importlib
import json
import unittest
from dataclasses import FrozenInstanceError

from ow_eval import (
    AgentSourceKind,
    AgentSpec,
    BaselineName,
    ExperimentManifest,
    ExperimentScenario,
    MatchConfig,
    OpponentSpec,
    PlayerCount,
    PromotionThresholds,
    builtin_baseline_spec,
    manifest_to_match_configs,
)


def modular_candidate(name: str = "candidate") -> AgentSpec:
    return AgentSpec(
        name=name,
        source_kind=AgentSourceKind.MODULAR_AGENT,
        module_path="agents.orbit_wars_agent",
    )


def noop_opponent(name: str = "noop") -> OpponentSpec:
    return OpponentSpec(builtin_baseline_spec(BaselineName.NOOP, name=name))


def neutral_opponent(name: str = "nearest") -> OpponentSpec:
    return OpponentSpec(
        builtin_baseline_spec(BaselineName.NEAREST_NEUTRAL, name=name)
    )


def two_player_scenario(seed: int = 7, label: str = "two-player") -> ExperimentScenario:
    return ExperimentScenario(
        seed=seed,
        player_count=PlayerCount.TWO_PLAYER,
        controlled_seat=0,
        opponent_agents=(noop_opponent("opponent-noop"),),
        label=label,
        metadata=(("scenario", label),),
    )


def four_player_scenario(
    seed: int = 9,
    label: str = "four-player",
) -> ExperimentScenario:
    return ExperimentScenario(
        seed=seed,
        player_count=PlayerCount.FOUR_PLAYER,
        controlled_seat=2,
        opponent_agents=(
            noop_opponent("seat-0"),
            neutral_opponent("seat-1"),
            noop_opponent("seat-3"),
        ),
        label=label,
        metadata=(("scenario", label),),
    )


def manifest(
    *scenarios: ExperimentScenario,
    thresholds: PromotionThresholds | None = None,
) -> ExperimentManifest:
    return ExperimentManifest(
        name="quick-smoke",
        candidate_agent=modular_candidate(),
        scenarios=tuple(scenarios) or (two_player_scenario(),),
        description="Quick deterministic local smoke manifest",
        version="v1",
        metadata=(("suite", "unit"),),
        promotion_thresholds=thresholds or PromotionThresholds(
            min_win_rate=0.0,
            max_error_rate=0.0,
            max_mean_rank=2.0,
            min_completed_count=1,
        ),
    )


class EvaluationExperimentManifestTests(unittest.TestCase):
    def test_manifest_module_imports_and_exports_are_available(self) -> None:
        module = importlib.import_module("ow_eval.experiment_manifest")

        self.assertIs(module.ExperimentScenario, ExperimentScenario)
        self.assertIs(module.ExperimentManifest, ExperimentManifest)
        self.assertIs(module.PromotionThresholds, PromotionThresholds)
        self.assertIs(module.manifest_to_match_configs, manifest_to_match_configs)

    def test_contracts_are_frozen_slotted_and_validate(self) -> None:
        thresholds = PromotionThresholds(max_error_rate=0.0)
        scenario = two_player_scenario()
        experiment = manifest(scenario, thresholds=thresholds)

        with self.assertRaises(FrozenInstanceError):
            thresholds.max_error_rate = 0.5  # type: ignore[misc]
        with self.assertRaises((AttributeError, TypeError)):
            scenario.extra = "nope"  # type: ignore[attr-defined]
        with self.assertRaises(FrozenInstanceError):
            experiment.name = "changed"  # type: ignore[misc]
        with self.assertRaisesRegex(ValueError, "seed"):
            ExperimentScenario(
                seed=True,  # type: ignore[arg-type]
                player_count=PlayerCount.TWO_PLAYER,
                controlled_seat=0,
                opponent_agents=(),
            )
        with self.assertRaisesRegex(ValueError, "name"):
            ExperimentManifest(
                name="",
                candidate_agent=modular_candidate(),
                scenarios=(),
            )

    def test_promotion_threshold_validation(self) -> None:
        valid = PromotionThresholds(
            min_win_rate=0.25,
            max_error_rate=0.1,
            max_mean_rank=1.5,
            min_completed_count=2,
        )

        self.assertEqual(valid.min_win_rate, 0.25)
        with self.assertRaisesRegex(ValueError, "min_win_rate"):
            PromotionThresholds(min_win_rate=-0.1)
        with self.assertRaisesRegex(ValueError, "max_error_rate"):
            PromotionThresholds(max_error_rate=1.1)
        with self.assertRaisesRegex(ValueError, "max_mean_rank"):
            PromotionThresholds(max_mean_rank=-1.0)
        with self.assertRaisesRegex(ValueError, "min_completed_count"):
            PromotionThresholds(min_completed_count=-1)
        with self.assertRaisesRegex(ValueError, "max_error_rate"):
            PromotionThresholds(max_error_rate=True)  # type: ignore[arg-type]

    def test_to_dict_and_from_dict_round_trip_json_safe_manifest(self) -> None:
        original = manifest(two_player_scenario(7), four_player_scenario(11))

        encoded = json.dumps(original.to_dict(), sort_keys=True)
        decoded = json.loads(encoded)
        restored = ExperimentManifest.from_dict(decoded)

        self.assertEqual(restored, original)
        self.assertEqual(decoded["name"], "quick-smoke")
        self.assertEqual(decoded["metadata"], {"suite": "unit"})
        self.assertEqual(decoded["promotion_thresholds"]["max_mean_rank"], 2.0)
        self.assertEqual(len(decoded["scenarios"]), 2)

    def test_scenario_and_threshold_from_dict_round_trip(self) -> None:
        scenario = ExperimentScenario.from_dict(two_player_scenario().to_dict())
        thresholds = PromotionThresholds.from_dict(
            PromotionThresholds(min_win_rate=0.5).to_dict()
        )

        self.assertEqual(scenario, two_player_scenario())
        self.assertEqual(thresholds, PromotionThresholds(min_win_rate=0.5))

    def test_manifest_expands_scenarios_to_match_configs_in_order(self) -> None:
        first = two_player_scenario(seed=7, label="first")
        second = two_player_scenario(seed=8, label="second")
        experiment = manifest(first, second)

        matches = manifest_to_match_configs(experiment)

        self.assertEqual(tuple(match.seed for match in matches), (7, 8))
        self.assertTrue(all(isinstance(match, MatchConfig) for match in matches))
        self.assertEqual(tuple(match.label for match in matches), ("first", "second"))
        self.assertTrue(
            all(match.candidate_agent is experiment.candidate_agent for match in matches)
        )
        self.assertEqual(matches[0].opponent_agents, first.opponent_agents)
        self.assertEqual(matches[1].metadata, (("scenario", "second"),))

    def test_two_player_and_four_player_scenarios_expand(self) -> None:
        experiment = manifest(two_player_scenario(), four_player_scenario())

        matches = manifest_to_match_configs(experiment)

        self.assertEqual(matches[0].player_count, PlayerCount.TWO_PLAYER)
        self.assertEqual(matches[0].controlled_seat, 0)
        self.assertEqual(len(matches[0].opponent_agents), 1)
        self.assertEqual(matches[1].player_count, PlayerCount.FOUR_PLAYER)
        self.assertEqual(matches[1].controlled_seat, 2)
        self.assertEqual(len(matches[1].opponent_agents), 3)
        self.assertEqual(
            tuple(opponent.name for opponent in matches[1].opponent_agents),
            ("seat-0", "seat-1", "seat-3"),
        )

    def test_malformed_opponent_counts_fail_during_match_expansion(self) -> None:
        bad_scenario = ExperimentScenario(
            seed=7,
            player_count=PlayerCount.FOUR_PLAYER,
            controlled_seat=0,
            opponent_agents=(noop_opponent("only-one"),),
        )

        with self.assertRaisesRegex(ValueError, "opponent_agents must match"):
            manifest_to_match_configs(manifest(bad_scenario))

    def test_from_dict_rejects_malformed_manifest_entries(self) -> None:
        data = manifest(two_player_scenario()).to_dict()
        data["scenarios"] = [two_player_scenario().to_dict(), "bad"]

        with self.assertRaisesRegex(ValueError, "scenarios\\[1\\]"):
            ExperimentManifest.from_dict(data)

    def test_from_dict_rejects_malformed_opponent_entries(self) -> None:
        data = two_player_scenario().to_dict()
        data["opponent_agents"] = [noop_opponent().to_dict(), "bad"]

        with self.assertRaisesRegex(ValueError, "opponent_agents\\[1\\]"):
            ExperimentScenario.from_dict(data)

    def test_manifest_to_match_configs_rejects_non_manifest(self) -> None:
        with self.assertRaisesRegex(ValueError, "manifest"):
            manifest_to_match_configs("bad")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
