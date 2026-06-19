"""Tests for Runtime / Submission Cycle 6 runtime config defaults."""

from __future__ import annotations

import copy
import importlib
import math
import unittest
from dataclasses import FrozenInstanceError
from unittest.mock import patch

from agents import (
    RuntimeDefaultConfig,
    RuntimeTurnConfig,
    RuntimeTurnStatus,
    runtime_turn_config_for_observation,
    run_runtime_turn,
)
from tests.test_runtime_state_adapter import load_fixture


class FakeClock:
    def __init__(self, *times: float) -> None:
        self._times = list(times)
        self.last = times[-1] if times else 0.0

    def __call__(self) -> float:
        if self._times:
            self.last = self._times.pop(0)
        return self.last


class RuntimeConfigTests(unittest.TestCase):
    def test_runtime_config_module_imports_and_exports_are_available(self) -> None:
        module = importlib.import_module("agents.runtime_config")

        self.assertIs(module.RuntimeDefaultConfig, RuntimeDefaultConfig)
        self.assertIs(
            module.runtime_turn_config_for_observation,
            runtime_turn_config_for_observation,
        )

    def test_runtime_default_config_is_frozen_and_slotted(self) -> None:
        defaults = RuntimeDefaultConfig()

        with self.assertRaises(FrozenInstanceError):
            defaults.default_turn_budget_seconds = 2.0  # type: ignore[misc]
        with self.assertRaises((AttributeError, TypeError)):
            defaults.extra = 1  # type: ignore[attr-defined]

    def test_runtime_default_config_rejects_invalid_numbers(self) -> None:
        invalid_values = (True, -1, math.inf, math.nan, "1")

        for value in invalid_values:
            with self.subTest(field="default_turn_budget_seconds", value=value):
                with self.assertRaises(ValueError):
                    RuntimeDefaultConfig(
                        default_turn_budget_seconds=value,  # type: ignore[arg-type]
                    )
            with self.subTest(field="minimum_stage_start_seconds", value=value):
                with self.assertRaises(ValueError):
                    RuntimeDefaultConfig(
                        minimum_stage_start_seconds=value,  # type: ignore[arg-type]
                    )
            with self.subTest(
                field="remaining_overage_reserve_seconds",
                value=value,
            ):
                with self.assertRaises(ValueError):
                    RuntimeDefaultConfig(
                        remaining_overage_reserve_seconds=value,  # type: ignore[arg-type]
                    )
        for value in (True, math.inf, math.nan, "1"):
            with self.subTest(field="runtime_minimum_total_score", value=value):
                with self.assertRaises(ValueError):
                    RuntimeDefaultConfig(
                        runtime_minimum_total_score=value,  # type: ignore[arg-type]
                    )

    def test_runtime_default_config_rejects_invalid_candidate_caps(self) -> None:
        for value in (True, -1, 1.5, "1"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    RuntimeDefaultConfig(
                        runtime_max_candidates=value,  # type: ignore[arg-type]
                    )

    def test_runtime_default_config_rejects_noncallable_clock(self) -> None:
        with self.assertRaises(ValueError):
            RuntimeDefaultConfig(clock=object())  # type: ignore[arg-type]

    def test_fixture_observation_uses_default_guarded_budget(self) -> None:
        observation = load_fixture("kaggle_seed7_2p_step0.json")

        config = runtime_turn_config_for_observation(observation, {})

        self.assertIsInstance(config, RuntimeTurnConfig)
        self.assertIsNotNone(config.budget_config)
        self.assertEqual(config.budget_config.turn_budget_seconds, 1.0)
        self.assertEqual(config.budget_config.minimum_stage_start_seconds, 0.05)
        self.assertIsNotNone(config.planner_config)
        self.assertIsNotNone(config.planner_config.candidate_config)
        self.assertEqual(config.planner_config.candidate_config.max_candidates, 8)
        self.assertIsNotNone(config.planner_config.strategy_dispatch_config)
        dispatch_config = config.planner_config.strategy_dispatch_config
        self.assertIsNotNone(dispatch_config.two_player_config)
        self.assertIsNotNone(dispatch_config.four_player_config)
        self.assertEqual(
            dispatch_config.two_player_config.minimum_total_score,
            -100.0,
        )
        self.assertEqual(
            dispatch_config.four_player_config.minimum_total_score,
            -100.0,
        )

    def test_runtime_candidate_cap_can_be_configured_or_disabled(self) -> None:
        capped = runtime_turn_config_for_observation(
            {},
            defaults=RuntimeDefaultConfig(runtime_max_candidates=3),
        )
        uncapped = runtime_turn_config_for_observation(
            {},
            defaults=RuntimeDefaultConfig(runtime_max_candidates=None),
        )

        self.assertIsNotNone(capped.planner_config)
        self.assertIsNotNone(capped.planner_config.candidate_config)
        self.assertEqual(capped.planner_config.candidate_config.max_candidates, 3)
        self.assertIsNotNone(uncapped.planner_config)
        self.assertIsNotNone(uncapped.planner_config.candidate_config)
        self.assertIsNone(uncapped.planner_config.candidate_config.max_candidates)

    def test_bounded_parity_remaining_overage_preserves_turn_budget(self) -> None:
        defaults = RuntimeDefaultConfig(
            default_turn_budget_seconds=1.0,
            remaining_overage_reserve_seconds=0.25,
        )

        config = runtime_turn_config_for_observation(
            {"remainingOverageTime": 1.25},
            defaults=defaults,
        )

        self.assertIsNotNone(config.budget_config)
        self.assertEqual(config.budget_config.turn_budget_seconds, 1.0)

    def test_numeric_remaining_overage_caps_budget_after_reserve(self) -> None:
        defaults = RuntimeDefaultConfig(
            default_turn_budget_seconds=1.0,
            remaining_overage_reserve_seconds=0.25,
        )

        config = runtime_turn_config_for_observation(
            {"remainingOverageTime": 0.75},
            defaults=defaults,
        )

        self.assertIsNotNone(config.budget_config)
        self.assertEqual(config.budget_config.turn_budget_seconds, 0.5)

    def test_large_remaining_overage_keeps_default_budget_cap(self) -> None:
        defaults = RuntimeDefaultConfig(
            default_turn_budget_seconds=1.0,
            remaining_overage_reserve_seconds=0.25,
        )

        config = runtime_turn_config_for_observation(
            {"remainingOverageTime": 60},
            defaults=defaults,
        )

        self.assertIsNotNone(config.budget_config)
        self.assertEqual(config.budget_config.turn_budget_seconds, 1.0)

    def test_missing_or_nonnumeric_remaining_overage_uses_default_budget(self) -> None:
        observations = (
            {},
            {"remainingOverageTime": None},
            {"remainingOverageTime": "60"},
            {"remainingOverageTime": True},
            {"remainingOverageTime": math.inf},
        )

        for observation in observations:
            with self.subTest(observation=observation):
                config = runtime_turn_config_for_observation(observation)

                self.assertIsNotNone(config.budget_config)
                self.assertEqual(config.budget_config.turn_budget_seconds, 1.0)

    def test_low_remaining_overage_forces_safe_fallback_before_parse(self) -> None:
        defaults = RuntimeDefaultConfig(
            default_turn_budget_seconds=1.0,
            remaining_overage_reserve_seconds=0.25,
            clock=FakeClock(10.0, 10.0),
        )
        config = runtime_turn_config_for_observation(
            {"remainingOverageTime": 0.1},
            defaults=defaults,
        )

        with patch(
            "agents.runtime_turn.observation_to_game_state",
            side_effect=AssertionError("observation_to_game_state called"),
        ) as parse:
            result = run_runtime_turn(
                {"remainingOverageTime": 0.1},
                config=config,
            )

        self.assertEqual(result.status, RuntimeTurnStatus.BUDGET_EXHAUSTED)
        self.assertEqual(result.actions, [])
        self.assertEqual(result.error, "budget exhausted before parse")
        parse.assert_not_called()

    def test_config_builder_does_not_mutate_observation_or_configuration(self) -> None:
        observation = {"remainingOverageTime": 60, "nested": {"safe": True}}
        configuration = {"episodeSteps": 400, "nested": {"safe": True}}
        observation_before = copy.deepcopy(observation)
        configuration_before = copy.deepcopy(configuration)

        runtime_turn_config_for_observation(observation, configuration)

        self.assertEqual(observation, observation_before)
        self.assertEqual(configuration, configuration_before)

    def test_invalid_observation_object_still_returns_safe_config(self) -> None:
        config = runtime_turn_config_for_observation(object())  # type: ignore[arg-type]

        self.assertIsNotNone(config.budget_config)
        self.assertEqual(config.budget_config.turn_budget_seconds, 1.0)


if __name__ == "__main__":
    unittest.main()
