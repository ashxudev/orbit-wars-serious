"""Tests for four-player rank and swing fact extraction."""

from __future__ import annotations

import json
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from agents.runtime_state import observation_to_game_state
from ow_planner import (
    FourPlayerRankReport,
    FourPlayerRankStandingFacts,
    FourPlayerSwingTargetFacts,
    four_player_rank_facts,
)
from ow_sim.state import Fleet, GameState, Planet


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


def fleet(
    fleet_id: int,
    owner: int,
    x: float,
    y: float,
    ships: int,
) -> Fleet:
    return Fleet(
        fleet_id=fleet_id,
        owner=owner,
        x=x,
        y=y,
        angle=0.0,
        from_planet_id=1,
        ships=ships,
        raw=(fleet_id, owner, x, y, 0.0, 1, ships),
    )


def rank_state() -> GameState:
    return GameState(
        tick=90,
        player_id=0,
        planets=(
            planet(1, 0, 0.0, 0.0, 35, production=4),
            planet(2, 0, 10.0, 0.0, 20, production=3),
            planet(3, 1, 30.0, 0.0, 40, production=6),
            planet(4, 1, 40.0, 0.0, 20, production=4),
            planet(5, 2, 0.0, 30.0, 16, production=2),
            planet(6, 3, 30.0, 30.0, 12, production=1),
            planet(7, -1, 16.0, 0.0, 8, production=3),
        ),
        fleets=(
            fleet(100, 0, 2.0, 0.0, 6),
            fleet(101, 2, 5.0, 20.0, 9),
        ),
        raw_observation={"step": 90, "player": 0},
    )


def rank_preservation_state() -> GameState:
    return GameState(
        tick=40,
        player_id=0,
        planets=(
            planet(1, 0, 0.0, 0.0, 60, production=8),
            planet(2, 1, 20.0, 0.0, 20, production=6),
            planet(3, 2, 0.0, 20.0, 20, production=3),
            planet(4, 3, 20.0, 20.0, 20, production=2),
            planet(5, -1, 10.0, 10.0, 10, production=3),
        ),
        raw_observation={"step": 40, "player": 0},
    )


class FourPlayerRankFactsTests(unittest.TestCase):
    def test_four_player_rank_report_includes_leaders_and_deltas(self) -> None:
        report = four_player_rank_facts(rank_state(), declared_player_count=4)

        self.assertEqual(report.player_id, 0)
        self.assertEqual(report.active_player_ids, (0, 1, 2, 3))
        self.assertEqual(report.active_opponent_ids, (1, 2, 3))
        self.assertTrue(report.is_four_player_context)
        self.assertTrue(report.is_active_four_player_context)
        self.assertEqual(report.production_leader_ids, (1,))
        self.assertEqual(report.current_player_production_rank, 2)
        self.assertEqual(report.production_delta_to_leader, 3)
        self.assertEqual(report.production_rival_id, 1)
        self.assertEqual(report.production_delta_to_next_higher_rival, 3)
        self.assertEqual(report.production_delta_to_next_lower_rival, 5)
        self.assertEqual(report.current_player_standing.total_ships, 61)
        self.assertGreater(report.swing_target_count, 0)
        self.assertIn("leader_pressure", report.labels)
        self.assertIn("swing_opportunity", report.labels)

    def test_rank_preservation_pressure_is_labeled_for_close_lead(self) -> None:
        report = four_player_rank_facts(
            rank_preservation_state(),
            declared_player_count=4,
        )

        self.assertEqual(report.current_player_production_rank, 1)
        self.assertTrue(report.rank_preservation_pressure)
        self.assertIn("rank_preservation_pressure", report.labels)
        self.assertFalse(report.leader_pressure)

    def test_non_four_player_control_is_not_labeled_as_four_player_context(
        self,
    ) -> None:
        report = four_player_rank_facts(
            GameState(
                tick=20,
                player_id=0,
                planets=(
                    planet(1, 0, 0.0, 0.0, 20, production=5),
                    planet(2, 1, 10.0, 0.0, 20, production=5),
                ),
            ),
            declared_player_count=2,
        )

        self.assertFalse(report.is_four_player_context)
        self.assertFalse(report.leader_pressure)
        self.assertFalse(report.swing_opportunity)
        self.assertNotIn("active_four_player_context", report.labels)

    def test_report_is_frozen_and_json_safe(self) -> None:
        report = four_player_rank_facts(rank_state(), declared_player_count=4)

        with self.assertRaises(FrozenInstanceError):
            report.leader_pressure = False  # type: ignore[misc]
        decoded = json.loads(json.dumps(report.to_dict(), sort_keys=True))
        self.assertEqual(decoded["player_id"], 0)
        self.assertIsInstance(decoded["standings"], list)
        self.assertIsInstance(decoded["swing_target_facts"], list)

    def test_malformed_inputs_fail_clearly(self) -> None:
        with self.assertRaisesRegex(ValueError, "state must be a GameState"):
            four_player_rank_facts(object())  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "declared_player_count"):
            four_player_rank_facts(rank_state(), declared_player_count=0)

    def test_v1_four_player_rank_fixtures_expose_expected_context(self) -> None:
        expectations = {
            "four_p_plateau_80982912_t250_p0.json": (
                "active_four_player_context",
                "leader_pressure",
                "underexpanded_trailing",
                "swing_opportunity",
            ),
            "four_p_plateau_80984201_t240_p0.json": (
                "declared_four_player_reduced_active_owners",
                "leader_pressure",
            ),
            "four_p_thin_capture_recaptured_80979440_t054_p0.json": (
                "active_four_player_context",
                "swing_opportunity",
                "thin_capture_risk_context",
            ),
        }

        for fixture_name, expected_labels in expectations.items():
            with self.subTest(fixture_name=fixture_name):
                payload = json.loads(
                    (FIXTURE_DIR / fixture_name).read_text(encoding="utf-8"),
                )
                state = observation_to_game_state(payload["observation"])

                report = four_player_rank_facts(
                    state,
                    declared_player_count=payload["player_count"],
                )

                self.assertTrue(report.is_four_player_context)
                for label in expected_labels:
                    self.assertIn(label, report.labels)
                self.assertGreater(report.swing_target_count, 0)

    def test_public_exports_are_importable(self) -> None:
        self.assertIs(FourPlayerRankReport, FourPlayerRankReport)
        self.assertIs(FourPlayerRankStandingFacts, FourPlayerRankStandingFacts)
        self.assertIs(FourPlayerSwingTargetFacts, FourPlayerSwingTargetFacts)


if __name__ == "__main__":
    unittest.main()
