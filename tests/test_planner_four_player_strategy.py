"""Tests for Strategy Modes Cycle 5 four-player board/rank facts."""

from __future__ import annotations

import copy
import importlib
import unittest
from dataclasses import FrozenInstanceError
from unittest.mock import patch

from ow_planner import (
    FourPlayerBoardFacts,
    FourPlayerStandingFacts,
    StrategyMode,
    StrategyModeFacts,
    four_player_board_facts,
)
from ow_sim.state import Fleet, GameState, Planet


def planet(
    planet_id: int,
    owner: int,
    *,
    ships: int,
    production: int,
) -> Planet:
    return Planet(
        planet_id=planet_id,
        owner=owner,
        x=float(planet_id),
        y=10.0,
        radius=1.0,
        ships=ships,
        production=production,
        raw=(planet_id, owner, float(planet_id), 10.0, 1.0, ships, production),
    )


def fleet(fleet_id: int, owner: int, *, ships: int) -> Fleet:
    return Fleet(
        fleet_id=fleet_id,
        owner=owner,
        x=float(fleet_id),
        y=20.0,
        angle=0.0,
        from_planet_id=1,
        ships=ships,
        raw=(fleet_id, owner, float(fleet_id), 20.0, 0.0, 1, ships),
    )


def state(
    *,
    player_id: int | None = 0,
    planets: tuple[Planet, ...] = (),
    fleets: tuple[Fleet, ...] = (),
) -> GameState:
    return GameState(
        tick=15,
        player_id=player_id,
        planets=planets,
        fleets=fleets,
        raw_observation={
            "step": 15,
            "player": player_id,
            "planets": [list(item.raw) for item in planets],
            "fleets": [list(item.raw) for item in fleets],
        },
    )


def four_player_mode_facts(
    *,
    player_id: int | None = 0,
    active_player_ids: tuple[int, ...] = (0, 1, 2, 3),
) -> StrategyModeFacts:
    return StrategyModeFacts(
        mode=StrategyMode.FOUR_PLAYER,
        player_id=player_id,
        active_player_ids=active_player_ids,
        opponent_player_ids=tuple(
            player for player in active_player_ids if player != player_id
        )
        if player_id is not None
        else (),
        player_count=len(active_player_ids),
    )


def sample_four_player_state(*, player_id: int | None = 0) -> GameState:
    return state(
        player_id=player_id,
        planets=(
            planet(1, 0, ships=10, production=2),
            planet(2, 0, ships=5, production=1),
            planet(3, 1, ships=20, production=5),
            planet(4, 3, ships=12, production=3),
            planet(5, -1, ships=99, production=99),
        ),
        fleets=(
            fleet(1, 0, ships=4),
            fleet(2, 3, ships=15),
            fleet(3, -1, ships=50),
        ),
    )


def standings_by_player(
    facts: FourPlayerBoardFacts,
) -> dict[int, FourPlayerStandingFacts]:
    return {standing.player_id: standing for standing in facts.standings}


class PlannerFourPlayerStrategyTests(unittest.TestCase):
    def test_four_player_strategy_module_imports_and_exports_are_available(self) -> None:
        importlib.import_module("ow_planner.four_player_strategy")

        self.assertIs(FourPlayerBoardFacts, FourPlayerBoardFacts)
        self.assertIs(FourPlayerStandingFacts, FourPlayerStandingFacts)
        self.assertIsNotNone(four_player_board_facts)

    def test_four_player_fact_dataclasses_are_constructible_frozen_and_slotted(
        self,
    ) -> None:
        standing = FourPlayerStandingFacts(player_id=0)
        facts = FourPlayerBoardFacts(standings=(standing,))

        self.assertEqual(standing.total_ships, 0)
        self.assertEqual(facts.standings, (standing,))
        self.assertTrue(hasattr(FourPlayerStandingFacts, "__slots__"))
        self.assertTrue(hasattr(FourPlayerBoardFacts, "__slots__"))
        with self.assertRaises(FrozenInstanceError):
            standing.production = 1
        with self.assertRaises(FrozenInstanceError):
            facts.survival_pressure = True

    def test_provided_strategy_mode_facts_are_attached_by_identity(self) -> None:
        mode_facts = four_player_mode_facts()

        facts = four_player_board_facts(
            sample_four_player_state(),
            strategy_mode_facts=mode_facts,
        )

        self.assertIs(facts.strategy_mode_facts, mode_facts)
        self.assertTrue(facts.is_four_player_mode)
        self.assertEqual(facts.player_id, 0)
        self.assertEqual(facts.active_player_ids, (0, 1, 2, 3))
        self.assertEqual(facts.notes, ())

    def test_four_player_mode_can_be_detected_from_state(self) -> None:
        facts = four_player_board_facts(
            state(
                player_id=0,
                planets=(
                    planet(1, 0, ships=1, production=1),
                    planet(2, 1, ships=1, production=1),
                    planet(3, 2, ships=1, production=1),
                    planet(4, 3, ships=1, production=1),
                ),
            )
        )

        self.assertTrue(facts.is_four_player_mode)
        self.assertEqual(facts.active_player_ids, (0, 1, 2, 3))
        self.assertEqual(facts.notes, ())

    def test_counts_ships_production_planets_and_fleets_for_active_players(self) -> None:
        facts = four_player_board_facts(
            sample_four_player_state(),
            strategy_mode_facts=four_player_mode_facts(),
        )
        standings = standings_by_player(facts)

        self.assertEqual(tuple(standings), (0, 1, 2, 3))
        self.assertEqual(standings[0].planet_count, 2)
        self.assertEqual(standings[0].fleet_count, 1)
        self.assertEqual(standings[0].planet_ships, 15)
        self.assertEqual(standings[0].fleet_ships, 4)
        self.assertEqual(standings[0].total_ships, 19)
        self.assertEqual(standings[0].production, 3)
        self.assertEqual(standings[1].planet_count, 1)
        self.assertEqual(standings[1].fleet_count, 0)
        self.assertEqual(standings[1].total_ships, 20)
        self.assertEqual(standings[1].production, 5)
        self.assertEqual(standings[2].planet_count, 0)
        self.assertEqual(standings[2].fleet_count, 0)
        self.assertEqual(standings[2].total_ships, 0)
        self.assertEqual(standings[2].production, 0)
        self.assertEqual(standings[3].planet_count, 1)
        self.assertEqual(standings[3].fleet_count, 1)
        self.assertEqual(standings[3].total_ships, 27)
        self.assertEqual(standings[3].production, 3)

    def test_rankings_leaders_deficits_and_tie_breaks_are_deterministic(self) -> None:
        facts = four_player_board_facts(
            sample_four_player_state(),
            strategy_mode_facts=four_player_mode_facts(),
        )
        standings = standings_by_player(facts)

        self.assertEqual(standings[1].production_rank, 1)
        self.assertEqual(standings[0].production_rank, 2)
        self.assertEqual(standings[3].production_rank, 3)
        self.assertEqual(standings[2].production_rank, 4)
        self.assertEqual(standings[3].total_ship_rank, 1)
        self.assertEqual(standings[1].total_ship_rank, 2)
        self.assertEqual(standings[0].total_ship_rank, 3)
        self.assertEqual(standings[2].total_ship_rank, 4)
        self.assertEqual(standings[0].planet_count_rank, 1)
        self.assertEqual(standings[1].planet_count_rank, 2)
        self.assertEqual(standings[3].planet_count_rank, 3)
        self.assertEqual(facts.production_leader_player_id, 1)
        self.assertEqual(facts.total_ship_leader_player_id, 3)
        self.assertEqual(facts.current_player_production_rank, 2)
        self.assertEqual(facts.current_player_total_ship_rank, 3)
        self.assertFalse(facts.current_player_is_production_leader)
        self.assertFalse(facts.current_player_is_total_ship_leader)
        self.assertEqual(facts.production_deficit_to_leader, 2)
        self.assertEqual(facts.total_ship_deficit_to_leader, 8)
        self.assertFalse(facts.current_player_is_last_by_production)
        self.assertFalse(facts.current_player_is_last_by_total_ships)
        self.assertFalse(facts.survival_pressure)

    def test_survival_pressure_when_current_player_is_last(self) -> None:
        facts = four_player_board_facts(
            sample_four_player_state(player_id=2),
            strategy_mode_facts=four_player_mode_facts(player_id=2),
        )

        self.assertEqual(facts.current_player_standing.player_id, 2)
        self.assertTrue(facts.current_player_is_last_by_production)
        self.assertTrue(facts.current_player_is_last_by_total_ships)
        self.assertEqual(facts.production_deficit_to_leader, 5)
        self.assertEqual(facts.total_ship_deficit_to_leader, 27)
        self.assertTrue(facts.survival_pressure)

    def test_non_four_player_inputs_return_notes_without_throwing(self) -> None:
        mode_facts = StrategyModeFacts(
            mode=StrategyMode.TWO_PLAYER,
            player_id=0,
            active_player_ids=(0, 1),
            opponent_player_ids=(1,),
            player_count=2,
        )

        facts = four_player_board_facts(
            sample_four_player_state(),
            strategy_mode_facts=mode_facts,
        )

        self.assertFalse(facts.is_four_player_mode)
        self.assertEqual(facts.active_player_ids, (0, 1))
        self.assertIn("not four-player mode", facts.notes)

    def test_missing_player_and_inactive_current_player_notes_are_deterministic(
        self,
    ) -> None:
        missing_player = four_player_board_facts(
            sample_four_player_state(player_id=None),
            strategy_mode_facts=four_player_mode_facts(player_id=None),
        )
        inactive_player = four_player_board_facts(
            sample_four_player_state(player_id=9),
            strategy_mode_facts=four_player_mode_facts(player_id=9),
        )

        self.assertIn("missing player id", missing_player.notes)
        self.assertIsNone(missing_player.current_player_standing)
        self.assertIn("current player not active", inactive_player.notes)
        self.assertIsNone(inactive_player.current_player_standing)
        self.assertIsNone(inactive_player.current_player_production_rank)
        self.assertIsNone(inactive_player.survival_pressure)

    def test_missing_active_players_note_is_deterministic(self) -> None:
        facts = four_player_board_facts(
            state(player_id=None),
            strategy_mode_facts=StrategyModeFacts(
                mode=StrategyMode.UNKNOWN,
                player_id=None,
                active_player_ids=(),
                opponent_player_ids=(),
                player_count=0,
            ),
        )

        self.assertFalse(facts.is_four_player_mode)
        self.assertEqual(facts.standings, ())
        self.assertEqual(
            facts.notes,
            (
                "not four-player mode",
                "missing player id",
                "missing active players",
            ),
        )

    def test_four_player_board_facts_do_not_mutate_state(self) -> None:
        original = sample_four_player_state()
        before = copy.deepcopy(original)

        four_player_board_facts(
            original,
            strategy_mode_facts=four_player_mode_facts(),
        )

        self.assertEqual(original, before)

    def test_four_player_board_facts_do_not_call_deferred_planner_or_simulator_logic(
        self,
    ) -> None:
        with (
            patch(
                "ow_planner.candidates.generate_candidates",
                side_effect=AssertionError("generate_candidates called"),
            ),
            patch(
                "ow_planner.evaluation.evaluate_candidates",
                side_effect=AssertionError("evaluate_candidates called"),
            ),
            patch(
                "ow_planner.scoring.score_evaluations",
                side_effect=AssertionError("score_evaluations called"),
            ),
            patch(
                "ow_planner.response.evaluate_responses",
                side_effect=AssertionError("evaluate_responses called"),
            ),
            patch(
                "ow_planner.commitment.commitment_options_for_candidates",
                side_effect=AssertionError("commitment_options_for_candidates called"),
            ),
            patch(
                "ow_planner.actions.mission_candidate_to_actions",
                side_effect=AssertionError("mission_candidate_to_actions called"),
            ),
            patch(
                "ow_planner.actions.mission_candidate_to_orders",
                side_effect=AssertionError("mission_candidate_to_orders called"),
            ),
            patch(
                "ow_sim.timeline.simulate_ticks",
                side_effect=AssertionError("simulate_ticks called"),
            ),
            patch(
                "ow_sim.whatif.simulate_launch_orders",
                side_effect=AssertionError("simulate_launch_orders called"),
            ),
        ):
            facts = four_player_board_facts(
                sample_four_player_state(),
                strategy_mode_facts=four_player_mode_facts(),
            )

        self.assertTrue(facts.is_four_player_mode)


if __name__ == "__main__":
    unittest.main()
