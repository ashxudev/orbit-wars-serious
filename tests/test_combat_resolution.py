"""Tests for Cycle 8 pure combat resolution helpers."""

from __future__ import annotations

import unittest

from ow_sim.combat import (
    FleetCombatWinner,
    PlanetCombatResult,
    fleet_ships_by_owner,
    resolve_fleet_combat,
    resolve_planet_combat,
)
from ow_sim.state import Fleet, Planet


def fleet(owner: int, ships: int, fleet_id: int = 1) -> Fleet:
    return Fleet(
        fleet_id=fleet_id,
        owner=owner,
        x=0.0,
        y=0.0,
        angle=0.0,
        from_planet_id=0,
        ships=ships,
        raw=(fleet_id, owner, 0.0, 0.0, 0.0, 0, ships),
    )


def planet(owner: int, ships: int) -> Planet:
    return Planet(
        planet_id=7,
        owner=owner,
        x=10.0,
        y=20.0,
        radius=2.0,
        ships=ships,
        production=1,
        raw=(7, owner, 10.0, 20.0, 2.0, ships, 1),
    )


class CombatResolutionTests(unittest.TestCase):
    def test_fleet_ships_by_owner_one_fleet(self) -> None:
        self.assertEqual(fleet_ships_by_owner([fleet(0, 5)]), {0: 5})

    def test_fleet_ships_by_owner_multiple_fleets_same_owner(self) -> None:
        self.assertEqual(
            fleet_ships_by_owner([fleet(0, 5, 1), fleet(0, 7, 2)]),
            {0: 12},
        )

    def test_fleet_ships_by_owner_multiple_owners(self) -> None:
        self.assertEqual(
            fleet_ships_by_owner(
                [fleet(0, 5, 1), fleet(1, 7, 2), fleet(0, 3, 3)]
            ),
            {0: 8, 1: 7},
        )

    def test_resolve_fleet_combat_no_fleets(self) -> None:
        self.assertEqual(
            resolve_fleet_combat([]),
            FleetCombatWinner(owner=None, ships=0),
        )

    def test_resolve_fleet_combat_one_owner(self) -> None:
        self.assertEqual(
            resolve_fleet_combat([fleet(1, 4, 1), fleet(1, 6, 2)]),
            FleetCombatWinner(owner=1, ships=10),
        )

    def test_resolve_fleet_combat_two_owners_clear_winner(self) -> None:
        self.assertEqual(
            resolve_fleet_combat([fleet(1, 8, 1), fleet(2, 5, 2)]),
            FleetCombatWinner(owner=1, ships=3),
        )

    def test_resolve_fleet_combat_two_owners_tied(self) -> None:
        self.assertEqual(
            resolve_fleet_combat([fleet(1, 8, 1), fleet(2, 8, 2)]),
            FleetCombatWinner(owner=None, ships=0),
        )

    def test_resolve_fleet_combat_three_owners_ignores_third(self) -> None:
        self.assertEqual(
            resolve_fleet_combat(
                [fleet(1, 10, 1), fleet(2, 6, 2), fleet(3, 5, 3)]
            ),
            FleetCombatWinner(owner=1, ships=4),
        )

    def test_resolve_fleet_combat_three_owners_top_tie(self) -> None:
        self.assertEqual(
            resolve_fleet_combat(
                [fleet(1, 10, 1), fleet(2, 10, 2), fleet(3, 1, 3)]
            ),
            FleetCombatWinner(owner=None, ships=0),
        )

    def test_planet_combat_no_arrivals_leaves_planet_unchanged(self) -> None:
        self.assertEqual(
            resolve_planet_combat(planet(0, 5), []),
            PlanetCombatResult(owner=0, ships=5, winner_owner=None, winner_ships=0),
        )

    def test_planet_combat_same_owner_reinforcement_adds_ships(self) -> None:
        self.assertEqual(
            resolve_planet_combat(planet(0, 5), [fleet(0, 3)]),
            PlanetCombatResult(owner=0, ships=8, winner_owner=0, winner_ships=3),
        )

    def test_planet_combat_neutral_capture(self) -> None:
        self.assertEqual(
            resolve_planet_combat(planet(-1, 2), [fleet(1, 5)]),
            PlanetCombatResult(owner=1, ships=3, winner_owner=1, winner_ships=5),
        )

    def test_planet_combat_enemy_damages_without_capture(self) -> None:
        self.assertEqual(
            resolve_planet_combat(planet(0, 10), [fleet(1, 4)]),
            PlanetCombatResult(owner=0, ships=6, winner_owner=1, winner_ships=4),
        )

    def test_planet_combat_exact_zero_preserves_owner(self) -> None:
        self.assertEqual(
            resolve_planet_combat(planet(0, 4), [fleet(1, 4)]),
            PlanetCombatResult(owner=0, ships=0, winner_owner=1, winner_ships=4),
        )

    def test_planet_combat_enemy_capture_uses_overkill_amount(self) -> None:
        self.assertEqual(
            resolve_planet_combat(planet(0, 3), [fleet(1, 5)]),
            PlanetCombatResult(owner=1, ships=2, winner_owner=1, winner_ships=5),
        )

    def test_planet_combat_tied_attackers_leave_planet_unchanged(self) -> None:
        self.assertEqual(
            resolve_planet_combat(planet(0, 3), [fleet(1, 5), fleet(2, 5)]),
            PlanetCombatResult(owner=0, ships=3, winner_owner=None, winner_ships=0),
        )

    def test_multi_owner_survivor_reinforces_by_top_minus_second(self) -> None:
        self.assertEqual(
            resolve_planet_combat(
                planet(1, 3),
                [fleet(1, 10, 1), fleet(2, 6, 2), fleet(3, 5, 3)],
            ),
            PlanetCombatResult(owner=1, ships=7, winner_owner=1, winner_ships=4),
        )

    def test_multi_owner_survivor_captures_by_top_minus_second(self) -> None:
        self.assertEqual(
            resolve_planet_combat(
                planet(3, 3),
                [fleet(1, 10, 1), fleet(2, 6, 2), fleet(0, 5, 3)],
            ),
            PlanetCombatResult(owner=1, ships=1, winner_owner=1, winner_ships=4),
        )

    def test_helpers_do_not_mutate_planet_fleets_or_raw_fields(self) -> None:
        target = planet(0, 5)
        arrivals = [fleet(1, 7, 1), fleet(2, 3, 2)]
        target_before = (
            target.owner,
            target.ships,
            target.raw,
        )
        arrivals_before = tuple(
            (arrival.owner, arrival.ships, arrival.raw) for arrival in arrivals
        )

        fleet_ships_by_owner(arrivals)
        resolve_fleet_combat(arrivals)
        resolve_planet_combat(target, arrivals)

        self.assertEqual(target_before, (target.owner, target.ships, target.raw))
        self.assertEqual(
            arrivals_before,
            tuple((arrival.owner, arrival.ships, arrival.raw) for arrival in arrivals),
        )


if __name__ == "__main__":
    unittest.main()
