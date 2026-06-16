"""Tests for schema-backed state containers."""

from __future__ import annotations

import unittest

from ow_sim.state import Fleet, GameState, Planet


class StatePlaceholderTests(unittest.TestCase):
    def test_state_objects_can_be_constructed(self) -> None:
        planet = Planet(
            planet_id=0,
            owner=-1,
            x=10.0,
            y=20.0,
            radius=2.0,
            ships=12,
            production=1,
        )
        fleet = Fleet(
            fleet_id=0,
            owner=1,
            x=12.0,
            y=20.0,
            angle=0.0,
            from_planet_id=0,
            ships=5,
        )
        state = GameState(
            tick=0,
            player_id=1,
            planets=(planet,),
            fleets=(fleet,),
        )

        self.assertEqual(state.planets[0].planet_id, 0)
        self.assertEqual(state.planets[0].position, (10.0, 20.0))
        self.assertEqual(state.fleets[0].fleet_id, 0)
        self.assertEqual(state.fleets[0].position, (12.0, 20.0))
        self.assertEqual(state.tick, 0)
