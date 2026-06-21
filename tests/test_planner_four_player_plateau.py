"""Tests for four-player plateau opportunity fact extraction."""

from __future__ import annotations

import json
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from agents.runtime_state import observation_to_game_state
from ow_planner import (
    FourPlayerPlateauReport,
    FourPlayerPlateauTargetFacts,
    four_player_plateau_facts,
)
from ow_sim.state import GameState, Planet


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "v1_replay_leaks"


def planet(
    planet_id: int,
    owner: int,
    x: float,
    y: float,
    ships: int,
    *,
    production: int = 0,
) -> Planet:
    return Planet(
        planet_id=planet_id,
        owner=owner,
        x=x,
        y=y,
        radius=1.0,
        ships=ships,
        production=production,
        raw=(planet_id, owner, x, y, 1.0, ships, production),
    )


def plateau_state() -> GameState:
    return GameState(
        tick=80,
        player_id=0,
        planets=(
            planet(1, 0, 0.0, 0.0, 40, production=4),
            planet(2, 0, 10.0, 0.0, 20, production=2),
            planet(3, -1, 14.0, 0.0, 8, production=3),
            planet(4, 1, 30.0, 0.0, 12, production=5),
            planet(5, 2, 0.0, 30.0, 15, production=4),
            planet(6, 3, 30.0, 30.0, 15, production=4),
        ),
        raw_observation={"step": 80, "player": 0},
    )


def two_player_state() -> GameState:
    return GameState(
        tick=80,
        player_id=0,
        planets=(
            planet(1, 0, 0.0, 0.0, 40, production=4),
            planet(2, 0, 10.0, 0.0, 20, production=2),
            planet(3, -1, 14.0, 0.0, 8, production=3),
            planet(4, 1, 30.0, 0.0, 12, production=5),
        ),
        raw_observation={"step": 80, "player": 0},
    )


class FourPlayerPlateauFactsTests(unittest.TestCase):
    def test_candidate_backlog_no_action_plateau_is_reported(self) -> None:
        report = four_player_plateau_facts(
            plateau_state(),
            declared_player_count=4,
            runtime_metadata={
                "runtime_diagnostic_candidate_count": "6",
                "runtime_diagnostic_action_count": "0",
                "runtime_diagnostic_status": "no_action",
                "runtime_diagnostic_no_action_reason": "strategy_selection_no_action",
            },
        )

        self.assertEqual(report.player_id, 0)
        self.assertEqual(report.active_opponent_ids, (1, 2, 3))
        self.assertEqual(report.declared_player_count, 4)
        self.assertTrue(report.is_four_player_context)
        self.assertEqual(report.owned_planet_count, 2)
        self.assertEqual(report.owned_production, 6)
        self.assertEqual(report.owned_ships, 60)
        self.assertEqual(report.neutral_production_target_count, 1)
        self.assertEqual(report.enemy_production_target_count, 3)
        self.assertEqual(report.nearest_expansion_target_id, 3)
        self.assertEqual(report.nearest_denial_target_id, 4)
        self.assertEqual(report.candidate_count, 6)
        self.assertEqual(report.action_count, 0)
        self.assertTrue(report.underexpanded)
        self.assertTrue(report.plateaued)
        self.assertTrue(report.candidate_backlog_no_action)
        self.assertFalse(report.action_emitting_plateau)
        self.assertIn("four_player_plateau", report.labels)
        self.assertIn("candidate_backlog_no_action", report.labels)

    def test_action_emitting_plateau_is_distinguished_from_no_action(self) -> None:
        report = four_player_plateau_facts(
            plateau_state(),
            declared_player_count=4,
            runtime_metadata={
                "runtime_diagnostic_candidate_count": "8",
                "runtime_diagnostic_action_count": "1",
                "runtime_diagnostic_status": "actions",
                "runtime_diagnostic_no_action_reason": "actions_emitted",
            },
        )

        self.assertTrue(report.plateaued)
        self.assertTrue(report.action_emitting_plateau)
        self.assertFalse(report.candidate_backlog_no_action)
        self.assertIn("action_emitting_plateau", report.labels)

    def test_non_four_player_control_is_not_labeled_plateau(self) -> None:
        report = four_player_plateau_facts(
            two_player_state(),
            declared_player_count=2,
            runtime_metadata={
                "runtime_diagnostic_candidate_count": "6",
                "runtime_diagnostic_action_count": "0",
                "runtime_diagnostic_status": "no_action",
                "runtime_diagnostic_no_action_reason": "strategy_selection_no_action",
            },
        )

        self.assertFalse(report.is_four_player_context)
        self.assertFalse(report.underexpanded)
        self.assertFalse(report.plateaued)
        self.assertNotIn("four_player_plateau", report.labels)

    def test_report_is_frozen_and_json_safe(self) -> None:
        report = four_player_plateau_facts(
            plateau_state(),
            declared_player_count=4,
        )

        with self.assertRaises(FrozenInstanceError):
            report.owned_production = 0  # type: ignore[misc]
        encoded = json.dumps(report.to_dict(), sort_keys=True)
        decoded = json.loads(encoded)
        self.assertEqual(decoded["owned_production"], 6)
        self.assertIsInstance(decoded["target_facts"], list)

    def test_malformed_inputs_fail_clearly(self) -> None:
        with self.assertRaisesRegex(ValueError, "state must be a GameState"):
            four_player_plateau_facts(object())  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "runtime_metadata"):
            four_player_plateau_facts(
                plateau_state(),
                runtime_metadata=object(),  # type: ignore[arg-type]
            )
        with self.assertRaisesRegex(ValueError, "declared_player_count"):
            four_player_plateau_facts(plateau_state(), declared_player_count=0)

    def test_v1_four_player_plateau_fixtures_expose_plateau_facts(self) -> None:
        expected = {
            "four_p_plateau_80981260_t060_p2.json": (True, False),
            "four_p_plateau_80984201_t240_p0.json": (True, False),
            "four_p_plateau_80982912_t250_p0.json": (False, True),
        }

        for fixture_name, expected_flags in expected.items():
            with self.subTest(fixture_name=fixture_name):
                payload = json.loads(
                    (FIXTURE_DIR / fixture_name).read_text(encoding="utf-8"),
                )
                state = observation_to_game_state(payload["observation"])
                runtime = payload["expected_current_runtime"]
                metadata = {
                    "runtime_diagnostic_candidate_count": str(
                        runtime["candidate_count"],
                    ),
                    "runtime_diagnostic_action_count": str(runtime["action_count"]),
                    "runtime_diagnostic_status": runtime["diagnostic_status"],
                    "runtime_diagnostic_no_action_reason": runtime["no_action_reason"],
                }

                report = four_player_plateau_facts(
                    state,
                    declared_player_count=payload["player_count"],
                    runtime_metadata=metadata,
                )

                self.assertTrue(report.is_four_player_context)
                self.assertTrue(report.underexpanded)
                self.assertTrue(report.plateaued)
                self.assertEqual(
                    (
                        report.candidate_backlog_no_action,
                        report.action_emitting_plateau,
                    ),
                    expected_flags,
                )
                self.assertGreater(
                    report.neutral_production_target_count
                    + report.enemy_production_target_count,
                    0,
                )


class FourPlayerPlateauExportTests(unittest.TestCase):
    def test_public_exports_are_importable(self) -> None:
        self.assertIs(FourPlayerPlateauReport, FourPlayerPlateauReport)
        self.assertIs(FourPlayerPlateauTargetFacts, FourPlayerPlateauTargetFacts)


if __name__ == "__main__":
    unittest.main()
