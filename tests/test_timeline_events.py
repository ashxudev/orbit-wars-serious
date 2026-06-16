"""Tests for Cycle 9 one-tick event summary helpers."""

from __future__ import annotations

import copy
import json
import math
import unittest
from pathlib import Path
from unittest.mock import patch

from ow_sim.collision import FleetRemovalEvent, FleetRemovalReason
from ow_sim.combat import PlanetCombatResult
from ow_sim.state import Fleet, GameState, Planet
from ow_sim.timeline import (
    OneTickEventSummary,
    PlanetArrivalCombatEvent,
    fleet_removal_events_for_tick,
    one_tick_event_summary,
    planet_arrival_combat_events_for_tick,
    planet_arrival_fleets_for_tick,
)


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def load_state(name: str) -> GameState:
    with (FIXTURE_DIR / name).open(encoding="utf-8") as fh:
        return GameState.from_obs(json.load(fh))


def fleet_at(
    fleet_id: int,
    x: float,
    y: float,
    *,
    owner: int = 0,
    angle: float = 0.0,
    ships: int = 1,
) -> Fleet:
    return Fleet(
        fleet_id=fleet_id,
        owner=owner,
        x=x,
        y=y,
        angle=angle,
        from_planet_id=0,
        ships=ships,
        raw=(fleet_id, owner, x, y, angle, 0, ships),
    )


def planet_at(
    planet_id: int,
    x: float,
    y: float,
    *,
    owner: int = -1,
    ships: int = 0,
    radius: float = 0.2,
) -> Planet:
    return Planet(
        planet_id=planet_id,
        owner=owner,
        x=x,
        y=y,
        radius=radius,
        ships=ships,
        production=1,
        raw=(planet_id, owner, x, y, radius, ships, 1),
    )


class TimelineEventTests(unittest.TestCase):
    def test_no_fleets_produces_empty_event_summaries(self) -> None:
        state = GameState(tick=0, planets=(planet_at(1, 0.5, 0.0),))

        self.assertEqual(fleet_removal_events_for_tick(state), ())
        self.assertEqual(planet_arrival_fleets_for_tick(state), {})
        self.assertEqual(planet_arrival_combat_events_for_tick(state), ())
        self.assertEqual(
            one_tick_event_summary(state),
            OneTickEventSummary(
                removal_events=(),
                planet_arrivals=(),
                bounds_fleet_ids=(),
                sun_fleet_ids=(),
            ),
        )

    def test_planet_hit_appears_in_removal_events_and_arrivals(self) -> None:
        target = planet_at(1, 0.5, 0.0, owner=-1, ships=0)
        fleet = fleet_at(10, 0.0, 0.0)
        state = GameState(tick=0, planets=(target,), fleets=(fleet,))

        removal_events = fleet_removal_events_for_tick(state)
        arrivals = planet_arrival_fleets_for_tick(state)

        self.assertEqual(len(removal_events), 1)
        self.assertEqual(removal_events[0].reason, FleetRemovalReason.PLANET)
        self.assertEqual(removal_events[0].fleet_id, fleet.fleet_id)
        self.assertEqual(removal_events[0].planet_id, target.planet_id)
        self.assertEqual(arrivals, {target.planet_id: (fleet,)})

    def test_multiple_fleets_same_planet_group_preserves_fleet_order(self) -> None:
        target = planet_at(1, 0.5, 0.0, owner=-1, ships=1)
        first = fleet_at(10, 0.0, 0.0, owner=0, ships=1)
        second = fleet_at(11, 1.0, 0.0, owner=0, angle=math.pi, ships=1)
        state = GameState(tick=0, planets=(target,), fleets=(first, second))

        arrivals = planet_arrival_fleets_for_tick(state)

        self.assertEqual(arrivals[target.planet_id], (first, second))

    def test_combat_result_is_produced_from_grouped_arrivals(self) -> None:
        target = planet_at(1, 0.5, 0.0, owner=-1, ships=1)
        first = fleet_at(10, 0.0, 0.0, owner=0, ships=1)
        second = fleet_at(11, 1.0, 0.0, owner=0, angle=math.pi, ships=1)
        state = GameState(tick=0, planets=(target,), fleets=(first, second))

        (event,) = planet_arrival_combat_events_for_tick(state)

        self.assertEqual(event.planet_id, target.planet_id)
        self.assertEqual(event.fleet_ids, (10, 11))
        self.assertEqual(event.fleets, (first, second))
        self.assertEqual(
            event.combat_result,
            PlanetCombatResult(owner=0, ships=1, winner_owner=0, winner_ships=2),
        )

    def test_tied_attackers_produce_unchanged_planet_result(self) -> None:
        target = planet_at(1, 0.5, 0.0, owner=2, ships=4)
        first = fleet_at(10, 0.0, 0.0, owner=0, ships=1)
        second = fleet_at(11, 1.0, 0.0, owner=1, angle=math.pi, ships=1)
        state = GameState(tick=0, planets=(target,), fleets=(first, second))

        (event,) = planet_arrival_combat_events_for_tick(state)

        self.assertEqual(
            event.combat_result,
            PlanetCombatResult(owner=2, ships=4, winner_owner=None, winner_ships=0),
        )

    def test_bounds_removal_is_not_a_planet_arrival(self) -> None:
        fleet = fleet_at(20, 99.5, 0.0)
        state = GameState(tick=0, fleets=(fleet,))

        (event,) = fleet_removal_events_for_tick(state)
        summary = one_tick_event_summary(state)

        self.assertEqual(event.reason, FleetRemovalReason.BOUNDS)
        self.assertEqual(planet_arrival_fleets_for_tick(state), {})
        self.assertEqual(summary.bounds_fleet_ids, (fleet.fleet_id,))
        self.assertEqual(summary.planet_arrivals, ())

    def test_sun_removal_is_not_a_planet_arrival(self) -> None:
        fleet = fleet_at(30, 49.0, 50.0)
        state = GameState(tick=0, fleets=(fleet,))

        (event,) = fleet_removal_events_for_tick(state)
        summary = one_tick_event_summary(state)

        self.assertEqual(event.reason, FleetRemovalReason.SUN)
        self.assertEqual(planet_arrival_fleets_for_tick(state), {})
        self.assertEqual(summary.sun_fleet_ids, (fleet.fleet_id,))
        self.assertEqual(summary.planet_arrivals, ())

    def test_mixed_planet_bounds_and_sun_events_are_separated(self) -> None:
        target = planet_at(1, 0.5, 0.0, owner=-1, ships=0)
        planet_fleet = fleet_at(10, 0.0, 0.0)
        bounds_fleet = fleet_at(20, 99.5, 0.0)
        sun_fleet = fleet_at(30, 49.0, 50.0)
        state = GameState(
            tick=0,
            planets=(target,),
            fleets=(planet_fleet, bounds_fleet, sun_fleet),
        )

        summary = one_tick_event_summary(state)

        self.assertEqual(
            tuple(event.reason for event in summary.removal_events),
            (
                FleetRemovalReason.PLANET,
                FleetRemovalReason.BOUNDS,
                FleetRemovalReason.SUN,
            ),
        )
        self.assertEqual(summary.bounds_fleet_ids, (bounds_fleet.fleet_id,))
        self.assertEqual(summary.sun_fleet_ids, (sun_fleet.fleet_id,))
        self.assertEqual(len(summary.planet_arrivals), 1)
        self.assertEqual(summary.planet_arrivals[0].fleet_ids, (planet_fleet.fleet_id,))

    def test_planet_combat_events_follow_state_planet_order(self) -> None:
        first_planet = planet_at(1, 0.5, 10.0, owner=-1, ships=0)
        second_planet = planet_at(2, 0.5, 0.0, owner=-1, ships=0)
        hits_second_first = fleet_at(20, 0.0, 0.0)
        hits_first_second = fleet_at(10, 0.0, 10.0)
        state = GameState(
            tick=0,
            planets=(first_planet, second_planet),
            fleets=(hits_second_first, hits_first_second),
        )

        events = planet_arrival_combat_events_for_tick(state)

        self.assertEqual(tuple(event.planet_id for event in events), (1, 2))
        self.assertEqual(events[0].fleet_ids, (10,))
        self.assertEqual(events[1].fleet_ids, (20,))

    def test_missing_planet_id_in_removal_event_skips_combat(self) -> None:
        fleet = fleet_at(77, 0.0, 0.0)
        state = GameState(tick=0, fleets=(fleet,))
        event = FleetRemovalEvent(
            reason=FleetRemovalReason.PLANET,
            fleet_id=fleet.fleet_id,
            planet_id=999,
            old_position=(0.0, 0.0),
            new_position=(1.0, 0.0),
        )

        with patch("ow_sim.timeline.fleet_removal_event_for_tick", return_value=event):
            self.assertEqual(planet_arrival_fleets_for_tick(state), {999: (fleet,)})
            self.assertEqual(planet_arrival_combat_events_for_tick(state), ())
            self.assertEqual(one_tick_event_summary(state).planet_arrivals, ())

    def test_invalid_dt_raises_value_error(self) -> None:
        state = GameState(
            tick=0,
            planets=(planet_at(1, 0.5, 0.0),),
            fleets=(fleet_at(10, 0.0, 0.0),),
        )

        with self.assertRaises(ValueError):
            fleet_removal_events_for_tick(state, dt=0)
        with self.assertRaises(ValueError):
            planet_arrival_fleets_for_tick(state, dt=0)
        with self.assertRaises(ValueError):
            planet_arrival_combat_events_for_tick(state, dt=0)
        with self.assertRaises(ValueError):
            one_tick_event_summary(state, dt=0)

    def test_helpers_do_not_mutate_fixture_state(self) -> None:
        state = load_state("kaggle_seed7_2p_step1_fleet.json")
        planets_before = state.planets
        fleets_before = state.fleets
        raw_before = copy.deepcopy(state.raw_observation)

        fleet_removal_events_for_tick(state)
        planet_arrival_fleets_for_tick(state)
        planet_arrival_combat_events_for_tick(state)
        one_tick_event_summary(state)

        self.assertEqual(state.planets, planets_before)
        self.assertEqual(state.fleets, fleets_before)
        self.assertEqual(state.raw_observation, raw_before)

    def test_event_result_types_are_frozen_value_objects(self) -> None:
        target = planet_at(1, 0.5, 0.0, owner=-1, ships=0)
        fleet = fleet_at(10, 0.0, 0.0)
        state = GameState(tick=0, planets=(target,), fleets=(fleet,))
        summary = one_tick_event_summary(state)

        self.assertIsInstance(summary, OneTickEventSummary)
        self.assertIsInstance(summary.planet_arrivals[0], PlanetArrivalCombatEvent)


if __name__ == "__main__":
    unittest.main()
