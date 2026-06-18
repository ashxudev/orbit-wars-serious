"""Tests for Evaluation Harness Cycle 3 built-in baselines."""

from __future__ import annotations

import copy
import importlib
import unittest

from ow_eval import (
    AgentSourceKind,
    AgentSpec,
    BaselineName,
    available_builtin_baselines,
    builtin_baseline_spec,
    load_builtin_baseline,
)
from ow_sim.geometry import angle_between, distance
from ow_sim.state import GameState
from tests.test_runtime_state_adapter import load_fixture


def minimal_observation(planets: list[list[object]], player: int = 0) -> dict[str, object]:
    return {
        "step": 0,
        "player": player,
        "planets": planets,
        "fleets": [],
        "initial_planets": planets,
        "remainingOverageTime": 60,
    }


class EvaluationBaselineTests(unittest.TestCase):
    def test_baseline_module_imports_and_exports_are_available(self) -> None:
        module = importlib.import_module("ow_eval.baselines")

        self.assertIs(module.BaselineName, BaselineName)
        self.assertIs(module.available_builtin_baselines, available_builtin_baselines)
        self.assertIs(module.builtin_baseline_spec, builtin_baseline_spec)
        self.assertIs(module.load_builtin_baseline, load_builtin_baseline)

    def test_available_builtin_baselines_are_stable(self) -> None:
        self.assertEqual(
            available_builtin_baselines(),
            ("noop", "nearest_neutral"),
        )
        self.assertEqual(BaselineName.NOOP.value, "noop")
        self.assertEqual(BaselineName.NEAREST_NEUTRAL.value, "nearest_neutral")

    def test_builtin_baseline_spec_marks_explicit_baseline(self) -> None:
        spec = builtin_baseline_spec(BaselineName.NEAREST_NEUTRAL, name="nn")

        self.assertEqual(spec.name, "nn")
        self.assertEqual(spec.source_kind, AgentSourceKind.BUILTIN_BASELINE)
        self.assertEqual(spec.metadata, (("baseline", "nearest_neutral"),))

    def test_builtin_baseline_spec_rejects_unknown_baseline(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown builtin baseline: unknown"):
            builtin_baseline_spec("unknown")

    def test_noop_baseline_returns_fresh_empty_list(self) -> None:
        agent = load_builtin_baseline(builtin_baseline_spec(BaselineName.NOOP))

        first = agent({}, {})
        second = agent({}, {})

        self.assertEqual(first, [])
        self.assertEqual(second, [])
        self.assertIsNot(first, second)

    def test_unknown_builtin_name_without_metadata_defaults_to_noop(self) -> None:
        spec = AgentSpec(
            name="idle-compatible",
            source_kind=AgentSourceKind.BUILTIN_BASELINE,
        )

        agent = load_builtin_baseline(spec)

        self.assertEqual(agent({}, {}), [])

    def test_idle_prefixed_name_without_metadata_defaults_to_noop(self) -> None:
        spec = AgentSpec(
            name="idle-2",
            source_kind=AgentSourceKind.BUILTIN_BASELINE,
        )

        agent = load_builtin_baseline(spec)

        self.assertEqual(agent({}, {}), [])

    def test_explicit_unknown_baseline_metadata_raises(self) -> None:
        spec = AgentSpec(
            name="bad",
            source_kind=AgentSourceKind.BUILTIN_BASELINE,
            metadata=(("baseline", "unknown"),),
        )

        with self.assertRaisesRegex(ValueError, "unknown builtin baseline: unknown"):
            load_builtin_baseline(spec)

    def test_nearest_neutral_returns_deterministic_fixture_action(self) -> None:
        observation = load_fixture("kaggle_seed7_2p_step0.json")
        observation_before = copy.deepcopy(observation)
        state = GameState.from_obs(observation)
        expected_action = expected_nearest_neutral_action(state)
        agent = load_builtin_baseline(
            builtin_baseline_spec(BaselineName.NEAREST_NEUTRAL)
        )

        actions = agent(observation, {})

        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0][0], expected_action[0])
        self.assertAlmostEqual(actions[0][1], expected_action[1], places=12)
        self.assertEqual(actions[0][2], expected_action[2])
        self.assertEqual(observation, observation_before)

    def test_nearest_neutral_returns_empty_for_malformed_observation(self) -> None:
        agent = load_builtin_baseline(
            builtin_baseline_spec(BaselineName.NEAREST_NEUTRAL)
        )

        self.assertEqual(agent({"planets": [[1]]}, {}), [])

    def test_nearest_neutral_returns_empty_without_valid_source(self) -> None:
        observation = minimal_observation(
            planets=[
                [1, 0, 0.0, 0.0, 0.5, 1, 1],
                [2, -1, 1.0, 0.0, 0.5, 5, 1],
            ]
        )
        agent = load_builtin_baseline(
            builtin_baseline_spec(BaselineName.NEAREST_NEUTRAL)
        )

        self.assertEqual(agent(observation, {}), [])

    def test_nearest_neutral_returns_empty_without_neutral_target(self) -> None:
        observation = minimal_observation(
            planets=[
                [1, 0, 0.0, 0.0, 0.5, 5, 1],
                [2, 1, 1.0, 0.0, 0.5, 5, 1],
            ]
        )
        agent = load_builtin_baseline(
            builtin_baseline_spec(BaselineName.NEAREST_NEUTRAL)
        )

        self.assertEqual(agent(observation, {}), [])


def expected_nearest_neutral_action(state: GameState) -> list[int | float]:
    assert state.player_id is not None
    sources = tuple(
        planet
        for planet in state.planets
        if planet.owner == state.player_id and planet.ships > 1
    )
    targets = tuple(planet for planet in state.planets if planet.owner == -1)
    source, target = min(
        (
            (source, target)
            for source in sources
            for target in targets
        ),
        key=lambda pair: (
            distance(pair[0].position, pair[1].position),
            pair[0].planet_id,
            pair[1].planet_id,
        ),
    )
    return [
        source.planet_id,
        angle_between(source.position, target.position),
        1,
    ]


if __name__ == "__main__":
    unittest.main()
