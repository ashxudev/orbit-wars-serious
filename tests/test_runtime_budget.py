"""Tests for Runtime / Submission Cycle 5 turn budget primitives."""

from __future__ import annotations

import importlib
import math
import unittest
from dataclasses import FrozenInstanceError

from agents import (
    RuntimeBudget,
    RuntimeBudgetCheck,
    RuntimeBudgetConfig,
    RuntimeBudgetStatus,
    runtime_budget_check,
    start_runtime_budget,
)


class FakeClock:
    def __init__(self, *times: float) -> None:
        self._times = list(times)
        self.calls = 0
        self.last = times[-1] if times else 0.0

    def __call__(self) -> float:
        self.calls += 1
        if self._times:
            self.last = self._times.pop(0)
        return self.last


class RuntimeBudgetTests(unittest.TestCase):
    def test_runtime_budget_module_imports_and_exports_are_available(self) -> None:
        module = importlib.import_module("agents.runtime_budget")

        self.assertIs(module.RuntimeBudget, RuntimeBudget)
        self.assertIs(module.RuntimeBudgetCheck, RuntimeBudgetCheck)
        self.assertIs(module.RuntimeBudgetConfig, RuntimeBudgetConfig)
        self.assertIs(module.RuntimeBudgetStatus, RuntimeBudgetStatus)
        self.assertIs(module.runtime_budget_check, runtime_budget_check)
        self.assertIs(module.start_runtime_budget, start_runtime_budget)

    def test_budget_config_is_frozen_and_slotted(self) -> None:
        config = RuntimeBudgetConfig(turn_budget_seconds=1.0)

        with self.assertRaises(FrozenInstanceError):
            config.turn_budget_seconds = 2.0  # type: ignore[misc]
        with self.assertRaises((AttributeError, TypeError)):
            config.extra = 1  # type: ignore[attr-defined]

    def test_budget_config_rejects_invalid_turn_budget_values(self) -> None:
        invalid_values = (True, -1, math.inf, math.nan, "1")

        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    RuntimeBudgetConfig(turn_budget_seconds=value)  # type: ignore[arg-type]

    def test_budget_config_rejects_invalid_stage_start_reserve(self) -> None:
        invalid_values = (False, -0.1, math.inf, math.nan, object())

        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    RuntimeBudgetConfig(
                        minimum_stage_start_seconds=value,  # type: ignore[arg-type]
                    )

    def test_budget_config_rejects_noncallable_clock(self) -> None:
        with self.assertRaises(ValueError):
            RuntimeBudgetConfig(clock=object())  # type: ignore[arg-type]

    def test_start_runtime_budget_uses_injected_clock(self) -> None:
        clock = FakeClock(12.5)
        config = RuntimeBudgetConfig(turn_budget_seconds=5.0, clock=clock)

        budget = start_runtime_budget(config)

        self.assertIsInstance(budget, RuntimeBudget)
        self.assertIs(budget.config, config)
        self.assertEqual(budget.started_at, 12.5)
        self.assertEqual(clock.calls, 1)

    def test_disabled_budget_allows_stage_start(self) -> None:
        clock = FakeClock(10.0, 12.0)
        budget = start_runtime_budget(RuntimeBudgetConfig(clock=clock))

        check = runtime_budget_check(budget, "parse")

        self.assertEqual(check.status, RuntimeBudgetStatus.DISABLED)
        self.assertTrue(check.can_start)
        self.assertEqual(check.stage, "parse")
        self.assertEqual(check.elapsed_seconds, 2.0)
        self.assertIsNone(check.remaining_seconds)
        self.assertIsNone(check.turn_budget_seconds)
        self.assertIsNone(check.note)

    def test_available_budget_reports_elapsed_and_remaining_time(self) -> None:
        clock = FakeClock(10.0, 11.25)
        config = RuntimeBudgetConfig(
            turn_budget_seconds=5.0,
            minimum_stage_start_seconds=1.0,
            clock=clock,
        )
        budget = start_runtime_budget(config)

        check = runtime_budget_check(budget, "planner")

        self.assertEqual(check.status, RuntimeBudgetStatus.AVAILABLE)
        self.assertTrue(check.can_start)
        self.assertEqual(check.elapsed_seconds, 1.25)
        self.assertEqual(check.remaining_seconds, 3.75)
        self.assertEqual(check.turn_budget_seconds, 5.0)
        self.assertEqual(check.minimum_stage_start_seconds, 1.0)
        self.assertIsNone(check.note)

    def test_budget_exhausted_reports_deterministic_note(self) -> None:
        clock = FakeClock(10.0, 15.0)
        budget = start_runtime_budget(
            RuntimeBudgetConfig(turn_budget_seconds=5.0, clock=clock),
        )

        check = runtime_budget_check(budget, "parse")

        self.assertEqual(check.status, RuntimeBudgetStatus.EXHAUSTED)
        self.assertFalse(check.can_start)
        self.assertEqual(check.elapsed_seconds, 5.0)
        self.assertEqual(check.remaining_seconds, 0.0)
        self.assertEqual(check.note, "budget exhausted before parse")

    def test_low_budget_reports_stage_start_reserve_note(self) -> None:
        clock = FakeClock(10.0, 14.5)
        budget = start_runtime_budget(
            RuntimeBudgetConfig(
                turn_budget_seconds=5.0,
                minimum_stage_start_seconds=1.0,
                clock=clock,
            ),
        )

        check = runtime_budget_check(budget, "action conversion")

        self.assertEqual(check.status, RuntimeBudgetStatus.LOW_BUDGET)
        self.assertFalse(check.can_start)
        self.assertEqual(check.remaining_seconds, 0.5)
        self.assertEqual(
            check.note,
            "budget below stage-start reserve before action conversion",
        )

    def test_exact_stage_start_reserve_is_available(self) -> None:
        clock = FakeClock(10.0, 14.0)
        budget = start_runtime_budget(
            RuntimeBudgetConfig(
                turn_budget_seconds=5.0,
                minimum_stage_start_seconds=1.0,
                clock=clock,
            ),
        )

        check = runtime_budget_check(budget, "planner")

        self.assertEqual(check.status, RuntimeBudgetStatus.AVAILABLE)
        self.assertTrue(check.can_start)
        self.assertEqual(check.remaining_seconds, 1.0)

    def test_elapsed_time_is_clamped_when_clock_moves_backward(self) -> None:
        clock = FakeClock(10.0, 9.0)
        budget = start_runtime_budget(
            RuntimeBudgetConfig(turn_budget_seconds=5.0, clock=clock),
        )

        check = runtime_budget_check(budget, "parse")

        self.assertEqual(check.elapsed_seconds, 0.0)
        self.assertEqual(check.remaining_seconds, 5.0)
        self.assertTrue(check.can_start)


if __name__ == "__main__":
    unittest.main()
