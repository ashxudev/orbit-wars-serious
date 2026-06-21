"""Tests for enemy-production denial opportunity fact extraction."""

from __future__ import annotations

import json
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from agents.runtime_state import observation_to_game_state
from ow_planner import (
    EnemyDenialOpportunityReport,
    EnemyDenialTargetFacts,
    enemy_denial_opportunity_facts,
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


def denial_state(*, target_ships: int = 12, target_production: int = 4) -> GameState:
    return GameState(
        tick=40,
        player_id=0,
        planets=(
            planet(1, 0, 0.0, 0.0, 35, production=5),
            planet(2, 0, 20.0, 0.0, 12, production=3),
            planet(3, 1, 10.0, 0.0, target_ships, production=target_production),
            planet(4, 1, 30.0, 0.0, 4, production=1),
            planet(5, -1, 40.0, 0.0, 0, production=0),
        ),
        raw_observation={"step": 40, "player": 0},
    )


class EnemyDenialFactsTests(unittest.TestCase):
    def test_high_value_opponent_production_target_is_reported(self) -> None:
        report = enemy_denial_opportunity_facts(denial_state())
        fact = report.target_facts[0]

        self.assertEqual(report.player_id, 0)
        self.assertEqual(report.opponent_id, 1)
        self.assertEqual(report.target_count, 2)
        self.assertEqual(report.plausible_denial_count, 2)
        self.assertEqual(report.high_value_denial_count, 1)
        self.assertEqual(report.player_production, 8)
        self.assertEqual(report.opponent_production, 5)
        self.assertTrue(report.player_ahead_by_production)
        self.assertIn("high_value_enemy_denial", report.labels)
        self.assertEqual(fact.target_planet_id, 3)
        self.assertEqual(fact.target_owner, 1)
        self.assertEqual(fact.target_ships, 12)
        self.assertEqual(fact.target_production, 4)
        self.assertTrue(fact.production_bearing)
        self.assertEqual(fact.owned_source_count, 2)
        self.assertEqual(fact.owned_source_capacity, 45)
        self.assertEqual(fact.sufficient_source_count, 1)
        self.assertEqual(fact.nearest_owned_source_id, 1)
        self.assertEqual(fact.nearest_owned_source_ships, 35)
        self.assertEqual(fact.nearest_owned_source_production, 5)
        self.assertEqual(fact.distance_to_nearest_source, 10.0)
        self.assertIsNotNone(fact.eta_ticks_from_nearest_source)
        self.assertTrue(fact.plausible_denial)
        self.assertTrue(fact.high_value_denial)
        self.assertIn("high_value_denial_opportunity", fact.labels)

    def test_no_meaningful_opponent_production_is_not_mislabeled(self) -> None:
        report = enemy_denial_opportunity_facts(
            denial_state(target_ships=2, target_production=0),
        )

        self.assertEqual(report.target_count, 1)
        self.assertEqual(report.high_value_denial_count, 0)
        self.assertNotIn("high_value_enemy_denial", report.labels)
        self.assertFalse(report.target_facts[0].high_value_denial)

    def test_insufficient_owned_capacity_blocks_plausible_denial_label(self) -> None:
        state = GameState(
            tick=40,
            player_id=0,
            planets=(
                planet(1, 0, 0.0, 0.0, 3, production=5),
                planet(2, 1, 10.0, 0.0, 20, production=5),
            ),
            raw_observation={"step": 40, "player": 0},
        )

        report = enemy_denial_opportunity_facts(state)
        fact = report.target_facts[0]

        self.assertEqual(report.target_count, 1)
        self.assertEqual(report.plausible_denial_count, 0)
        self.assertEqual(report.high_value_denial_count, 0)
        self.assertFalse(fact.plausible_denial)
        self.assertFalse(fact.high_value_denial)
        self.assertEqual(fact.sufficient_source_count, 0)
        self.assertNotIn("plausible_enemy_denial", report.labels)

    def test_missing_opponent_and_player_are_reported_without_targets(self) -> None:
        no_opponent = GameState(
            tick=1,
            player_id=0,
            planets=(planet(1, 0, 0.0, 0.0, 5, production=3),),
            raw_observation={"step": 1, "player": 0},
        )
        missing_player = GameState(
            tick=1,
            player_id=None,
            planets=(planet(1, 0, 0.0, 0.0, 5, production=3),),
            raw_observation={"step": 1},
        )

        self.assertEqual(
            enemy_denial_opportunity_facts(no_opponent).labels,
            ("missing_opponent_id",),
        )
        self.assertEqual(
            enemy_denial_opportunity_facts(missing_player).labels,
            ("missing_player_id",),
        )

    def test_report_is_frozen_and_json_safe(self) -> None:
        report = enemy_denial_opportunity_facts(denial_state())

        with self.assertRaises(FrozenInstanceError):
            report.high_value_denial_count = 0  # type: ignore[misc]
        encoded = json.dumps(report.to_dict(), sort_keys=True)
        decoded = json.loads(encoded)
        self.assertEqual(decoded["high_value_denial_count"], 1)
        self.assertIsInstance(decoded["target_facts"], list)

    def test_malformed_inputs_fail_clearly(self) -> None:
        with self.assertRaisesRegex(ValueError, "state must be a GameState"):
            enemy_denial_opportunity_facts(object())  # type: ignore[arg-type]

    def test_v1_enemy_denial_fixture_exposes_high_value_opportunities(self) -> None:
        payload = json.loads(
            (
                FIXTURE_DIR / "two_p_enemy_denial_absent_80989880_t200_p0.json"
            ).read_text(encoding="utf-8"),
        )
        state = observation_to_game_state(payload["observation"])

        report = enemy_denial_opportunity_facts(state)
        targets_by_id = {
            facts.target_planet_id: facts for facts in report.target_facts
        }

        self.assertEqual(report.target_count, 7)
        self.assertEqual(report.plausible_denial_count, 7)
        self.assertEqual(report.high_value_denial_count, 4)
        self.assertIn("high_value_enemy_denial", report.labels)
        self.assertIn(10, targets_by_id)
        self.assertTrue(targets_by_id[10].high_value_denial)
        self.assertEqual(targets_by_id[10].target_production, 5)
        self.assertEqual(targets_by_id[10].nearest_owned_source_id, 4)


class EnemyDenialExportTests(unittest.TestCase):
    def test_public_exports_are_importable(self) -> None:
        self.assertIs(EnemyDenialOpportunityReport, EnemyDenialOpportunityReport)
        self.assertIs(EnemyDenialTargetFacts, EnemyDenialTargetFacts)


if __name__ == "__main__":
    unittest.main()
