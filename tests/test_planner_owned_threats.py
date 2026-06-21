"""Tests for owned-production threat fact extraction."""

from __future__ import annotations

import json
import math
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from agents.runtime_state import observation_to_game_state
from ow_planner import (
    IncomingFleetThreatFacts,
    OwnedPlanetThreatFacts,
    OwnedProductionThreatReport,
    owned_production_threat_facts,
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
    from_planet_id: int = 99,
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


def threat_state(*, fleets: tuple[Fleet, ...]) -> GameState:
    return GameState(
        tick=12,
        player_id=0,
        planets=(
            planet(1, 0, 0.0, 0.0, 5, production=3),
            planet(2, 1, 20.0, 0.0, 30, production=4),
            planet(3, -1, 0.0, 12.0, 0, production=0),
        ),
        fleets=fleets,
        raw_observation={"step": 12, "player": 0},
    )


class OwnedThreatFactsTests(unittest.TestCase):
    def test_hostile_inbound_marks_owned_production_likely_flip(self) -> None:
        state = threat_state(
            fleets=(fleet(10, 1, -10.0, 0.0, 0.0, 12),),
        )

        report = owned_production_threat_facts(state)
        fact = report.planet_facts[0]

        self.assertEqual(report.player_id, 0)
        self.assertEqual(report.production_pressure_count, 1)
        self.assertEqual(report.threatened_planet_count, 1)
        self.assertEqual(report.likely_flip_count, 1)
        self.assertEqual(report.production_at_risk, 3)
        self.assertIn("owned_production_pressure", report.labels)
        self.assertIn("owned_production_threat", report.labels)
        self.assertTrue(fact.production_under_pressure)
        self.assertTrue(fact.at_risk)
        self.assertTrue(fact.likely_flip)
        self.assertEqual(fact.incoming_enemy_ships, 12)
        self.assertEqual(fact.current_ships, 5)
        self.assertEqual(fact.production, 3)
        self.assertLessEqual(fact.earliest_hostile_eta or 999, 80)
        self.assertEqual(fact.projected_balance_at_earliest_hostile, -7)
        self.assertEqual(fact.hostile_fleets[0].fleet_id, 10)

    def test_friendly_reinforcement_is_counted_in_projected_balance(self) -> None:
        state = threat_state(
            fleets=(
                fleet(10, 1, -10.0, 0.0, 0.0, 7),
                fleet(11, 0, 10.0, 0.0, math.pi, 3),
            ),
        )

        fact = owned_production_threat_facts(state).planet_facts[0]

        self.assertEqual(fact.incoming_enemy_ships, 7)
        self.assertEqual(fact.incoming_friendly_ships, 3)
        self.assertEqual(fact.projected_balance_at_earliest_hostile, 1)
        self.assertTrue(fact.at_risk)
        self.assertFalse(fact.likely_flip)
        self.assertEqual(fact.friendly_fleets[0].fleet_id, 11)

    def test_outgoing_source_drain_context_is_reported(self) -> None:
        state = GameState(
            tick=12,
            player_id=0,
            planets=(
                planet(1, 0, 0.0, 0.0, 5, production=3),
                planet(2, 1, 20.0, 0.0, 30, production=4),
            ),
            fleets=(
                fleet(20, 0, 0.0, 0.0, 0.0, 5, from_planet_id=1),
                fleet(21, 1, -10.0, 0.0, 0.0, 8),
            ),
            raw_observation={"step": 12, "player": 0},
        )

        report = owned_production_threat_facts(state)
        fact = report.planet_facts[0]

        self.assertTrue(fact.source_drained_by_outgoing)
        self.assertEqual(fact.outgoing_friendly_fleet_count, 1)
        self.assertEqual(fact.outgoing_friendly_ships, 5)
        self.assertIn("threatened_source_drained", report.labels)

    def test_non_threat_control_state_is_not_marked_urgent(self) -> None:
        state = threat_state(
            fleets=(fleet(10, 1, -10.0, 0.0, math.pi, 12),),
        )

        report = owned_production_threat_facts(state)

        self.assertEqual(report.production_pressure_count, 0)
        self.assertEqual(report.threatened_planet_count, 0)
        self.assertEqual(report.likely_flip_count, 0)
        self.assertEqual(report.labels, ())
        self.assertFalse(report.planet_facts[0].production_under_pressure)

    def test_report_is_frozen_and_json_safe(self) -> None:
        report = owned_production_threat_facts(
            threat_state(fleets=(fleet(10, 1, -10.0, 0.0, 0.0, 12),)),
        )

        with self.assertRaises(FrozenInstanceError):
            report.threatened_planet_count = 0  # type: ignore[misc]
        encoded = json.dumps(report.to_dict(), sort_keys=True)
        decoded = json.loads(encoded)
        self.assertEqual(decoded["threatened_planet_count"], 1)
        self.assertIsInstance(decoded["planet_facts"], list)

    def test_malformed_inputs_fail_clearly(self) -> None:
        with self.assertRaisesRegex(ValueError, "state must be a GameState"):
            owned_production_threat_facts(object())  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "horizon_ticks"):
            owned_production_threat_facts(
                threat_state(fleets=()),
                horizon_ticks=-1,
            )

    def test_missing_player_id_is_reported_without_planet_facts(self) -> None:
        state = GameState(
            tick=1,
            player_id=None,
            planets=(planet(1, 0, 0.0, 0.0, 5, production=3),),
            raw_observation={"step": 1},
        )

        report = owned_production_threat_facts(state)

        self.assertIsNone(report.player_id)
        self.assertEqual(report.planet_facts, ())
        self.assertEqual(report.labels, ("missing_player_id",))

    def test_v1_production_retention_fixtures_expose_owned_pressure(self) -> None:
        expected_cases = {
            "two_p_production_retention_80979989_t084_p1.json": True,
            "two_p_production_retention_80987824_t156_p1.json": False,
            "two_p_production_retention_80999800_t150_p0.json": True,
        }

        for name, expected_likely_flip in expected_cases.items():
            with self.subTest(name=name):
                payload = json.loads(
                    (FIXTURE_DIR / name).read_text(encoding="utf-8"),
                )
                state = observation_to_game_state(payload["observation"])

                report = owned_production_threat_facts(state)

                self.assertGreater(report.production_pressure_count, 0)
                self.assertGreater(report.production_under_pressure, 0)
                self.assertIn("owned_production_pressure", report.labels)
                if expected_likely_flip:
                    self.assertGreater(report.threatened_planet_count, 0)
                    self.assertIn("owned_production_threat", report.labels)
                else:
                    self.assertEqual(report.threatened_planet_count, 0)


class OwnedThreatExportTests(unittest.TestCase):
    def test_public_exports_are_importable(self) -> None:
        self.assertIs(IncomingFleetThreatFacts, IncomingFleetThreatFacts)
        self.assertIs(OwnedPlanetThreatFacts, OwnedPlanetThreatFacts)
        self.assertIs(OwnedProductionThreatReport, OwnedProductionThreatReport)


if __name__ == "__main__":
    unittest.main()
