"""Tests for own-to-own transfer intent fact extraction."""

from __future__ import annotations

import json
import math
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from agents.runtime_state import observation_to_game_state
from ow_planner import (
    OwnTransferFleetFacts,
    OwnTransferIntentReport,
    own_transfer_intent_facts,
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
    angle: float,
    ships: int,
    *,
    from_planet_id: int,
) -> Fleet:
    return Fleet(
        fleet_id=fleet_id,
        owner=owner,
        x=x,
        y=y,
        angle=angle,
        from_planet_id=from_planet_id,
        ships=ships,
        raw=(fleet_id, owner, x, y, angle, from_planet_id, ships),
    )


def transfer_state(*fleets: Fleet) -> GameState:
    return GameState(
        tick=20,
        player_id=0,
        planets=(
            planet(1, 0, -10.0, 0.0, 25, production=4),
            planet(2, 0, 0.0, 0.0, 5, production=5),
            planet(3, 1, 20.0, 0.0, 30, production=3),
        ),
        fleets=tuple(fleets),
        raw_observation={"step": 20, "player": 0},
    )


class OwnTransferIntentFactsTests(unittest.TestCase):
    def test_reinforcing_threatened_owned_production_is_purposeful(self) -> None:
        state = transfer_state(
            fleet(10, 0, -5.0, 0.0, 0.0, 4, from_planet_id=1),
            fleet(11, 1, 10.0, 0.0, math.pi, 10, from_planet_id=3),
        )

        report = own_transfer_intent_facts(state)
        fact = report.transfer_facts[0]

        self.assertEqual(report.transfer_count, 1)
        self.assertEqual(report.purposeful_count, 1)
        self.assertEqual(report.potentially_spammy_count, 0)
        self.assertTrue(fact.purposeful)
        self.assertFalse(fact.potentially_spammy)
        self.assertTrue(fact.target_under_pressure)
        self.assertTrue(fact.target_at_risk)
        self.assertEqual(fact.source_planet_id, 1)
        self.assertEqual(fact.target_planet_id, 2)
        self.assertEqual(fact.ships, 4)
        self.assertEqual(fact.source_production, 4)
        self.assertEqual(fact.target_production, 5)
        self.assertIn("reinforces_threatened_owned_production", fact.labels)
        self.assertIn("purposeful_own_transfer", report.labels)

    def test_repeated_low_impact_transfer_without_threat_is_spammy(self) -> None:
        state = transfer_state(
            fleet(10, 0, -5.0, 0.0, 0.0, 1, from_planet_id=1),
            fleet(11, 0, -4.0, 0.0, 0.0, 1, from_planet_id=1),
        )

        report = own_transfer_intent_facts(state)

        self.assertEqual(report.transfer_count, 2)
        self.assertEqual(report.purposeful_count, 2)
        self.assertEqual(report.potentially_spammy_count, 2)
        self.assertEqual(report.repeated_transfer_group_count, 1)
        self.assertIn("potentially_spammy_own_transfer", report.labels)
        self.assertIn("repeated_own_transfer", report.labels)
        for fact in report.transfer_facts:
            self.assertTrue(fact.potentially_spammy)
            self.assertEqual(fact.repeated_source_target_transfer_count, 2)
            self.assertIn("repeated_source_target_transfer", fact.labels)
            self.assertIn("no_visible_defense_purpose", fact.labels)

    def test_non_transfer_control_state_is_not_mislabeled(self) -> None:
        state = transfer_state(
            fleet(10, 0, 0.0, 0.0, 0.0, 5, from_planet_id=2),
        )

        report = own_transfer_intent_facts(state)

        self.assertEqual(report.transfer_count, 0)
        self.assertEqual(report.potentially_spammy_count, 0)
        self.assertEqual(report.labels, ())

    def test_report_is_frozen_and_json_safe(self) -> None:
        report = own_transfer_intent_facts(
            transfer_state(fleet(10, 0, -5.0, 0.0, 0.0, 4, from_planet_id=1)),
        )

        with self.assertRaises(FrozenInstanceError):
            report.transfer_count = 0  # type: ignore[misc]
        encoded = json.dumps(report.to_dict(), sort_keys=True)
        decoded = json.loads(encoded)
        self.assertEqual(decoded["transfer_count"], 1)
        self.assertIsInstance(decoded["transfer_facts"], list)

    def test_malformed_inputs_fail_clearly(self) -> None:
        with self.assertRaisesRegex(ValueError, "state must be a GameState"):
            own_transfer_intent_facts(object())  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "threat_report"):
            own_transfer_intent_facts(
                transfer_state(),
                threat_report=object(),  # type: ignore[arg-type]
            )

    def test_missing_player_id_is_reported_without_transfers(self) -> None:
        report = own_transfer_intent_facts(
            GameState(
                tick=1,
                player_id=None,
                raw_observation={"step": 1},
            ),
        )

        self.assertIsNone(report.player_id)
        self.assertEqual(report.transfer_facts, ())
        self.assertEqual(report.labels, ("missing_player_id",))

    def test_v1_own_transfer_fixtures_expose_spammy_transfer_facts(self) -> None:
        expected_counts = {
            "two_p_own_transfer_spam_80991772_t160_p0.json": (1, 1, 0),
            "two_p_own_transfer_spam_80986331_t161_p1.json": (12, 12, 1),
        }

        for name, expected in expected_counts.items():
            with self.subTest(name=name):
                payload = json.loads(
                    (FIXTURE_DIR / name).read_text(encoding="utf-8"),
                )
                state = observation_to_game_state(payload["observation"])

                report = own_transfer_intent_facts(state)

                self.assertEqual(
                    (
                        report.transfer_count,
                        report.potentially_spammy_count,
                        report.repeated_transfer_group_count,
                    ),
                    expected,
                )
                self.assertIn("potentially_spammy_own_transfer", report.labels)


class OwnTransferExportTests(unittest.TestCase):
    def test_public_exports_are_importable(self) -> None:
        self.assertIs(OwnTransferFleetFacts, OwnTransferFleetFacts)
        self.assertIs(OwnTransferIntentReport, OwnTransferIntentReport)


if __name__ == "__main__":
    unittest.main()
