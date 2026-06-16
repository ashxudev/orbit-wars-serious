"""Tests for provisional state containers."""

from __future__ import annotations

import unittest

from ow_sim.state import Fleet, GameState, Planet


class StatePlaceholderTests(unittest.TestCase):
    def test_placeholder_state_objects_can_be_constructed(self) -> None:
        planet = Planet(
            planet_id="planet-0",
            position=(10.0, 20.0),
            owner=None,
            ships=12.0,
        )
        fleet = Fleet(
            fleet_id="fleet-0",
            owner=1,
            ships=5.0,
            position=(12.0, 20.0),
            source_id="planet-0",
            target_id="planet-1",
        )
        state = GameState(
            tick=0,
            player_id=1,
            planets=(planet,),
            fleets=(fleet,),
        )

        self.assertEqual(state.planets[0].planet_id, "planet-0")
        self.assertEqual(state.fleets[0].fleet_id, "fleet-0")
        self.assertEqual(state.tick, 0)
