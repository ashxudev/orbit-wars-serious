"""Tests for Strategy Modes Cycle 0 detection boundary."""

from __future__ import annotations

import copy
import importlib
import unittest
from dataclasses import FrozenInstanceError
from unittest.mock import patch

from ow_planner import (
    StrategyMode,
    StrategyModeFacts,
    detect_strategy_mode,
    strategy_mode_facts,
)
from ow_sim.state import Fleet, GameState, Planet


def planet(planet_id: int, owner: int) -> Planet:
    return Planet(
        planet_id=planet_id,
        owner=owner,
        x=float(planet_id),
        y=20.0,
        radius=2.0,
        ships=5,
        production=1,
        raw=(planet_id, owner, float(planet_id), 20.0, 2.0, 5, 1),
    )


def fleet(fleet_id: int, owner: int) -> Fleet:
    return Fleet(
        fleet_id=fleet_id,
        owner=owner,
        x=float(fleet_id),
        y=30.0,
        angle=0.0,
        from_planet_id=1,
        ships=3,
        raw=(fleet_id, owner, float(fleet_id), 30.0, 0.0, 1, 3),
    )


def state(
    *,
    player_id: int | None = 0,
    planets: tuple[Planet, ...] = (),
    fleets: tuple[Fleet, ...] = (),
) -> GameState:
    return GameState(
        tick=10,
        player_id=player_id,
        planets=planets,
        fleets=fleets,
        raw_observation={
            "step": 10,
            "player": player_id,
            "planets": [list(item.raw) for item in planets],
            "fleets": [list(item.raw) for item in fleets],
        },
    )


class PlannerStrategyModeTests(unittest.TestCase):
    def test_strategy_mode_module_imports_and_exports_are_available(self) -> None:
        importlib.import_module("ow_planner.strategy_modes")

        self.assertIs(StrategyMode, StrategyMode)
        self.assertIs(StrategyModeFacts, StrategyModeFacts)
        self.assertIsNotNone(detect_strategy_mode)
        self.assertIsNotNone(strategy_mode_facts)

    def test_strategy_mode_values_are_stable(self) -> None:
        self.assertEqual(StrategyMode.TWO_PLAYER.value, "two_player")
        self.assertEqual(StrategyMode.FOUR_PLAYER.value, "four_player")
        self.assertEqual(StrategyMode.UNKNOWN.value, "unknown")

    def test_strategy_mode_facts_are_constructible_frozen_and_slotted(self) -> None:
        facts = StrategyModeFacts(
            mode=StrategyMode.TWO_PLAYER,
            player_id=0,
            active_player_ids=(0, 1),
            opponent_player_ids=(1,),
            player_count=2,
        )

        self.assertEqual(facts.mode, StrategyMode.TWO_PLAYER)
        self.assertEqual(facts.note, None)
        self.assertTrue(hasattr(StrategyModeFacts, "__slots__"))
        with self.assertRaises(FrozenInstanceError):
            facts.note = "changed"

    def test_detects_two_player_mode_from_planets(self) -> None:
        facts = strategy_mode_facts(
            state(
                player_id=0,
                planets=(planet(2, 1), planet(1, 0)),
            )
        )

        self.assertEqual(facts.mode, StrategyMode.TWO_PLAYER)
        self.assertEqual(facts.player_id, 0)
        self.assertEqual(facts.active_player_ids, (0, 1))
        self.assertEqual(facts.opponent_player_ids, (1,))
        self.assertEqual(facts.player_count, 2)
        self.assertIsNone(facts.note)
        self.assertEqual(
            detect_strategy_mode(
                state(player_id=0, planets=(planet(1, 0), planet(2, 1)))
            ),
            StrategyMode.TWO_PLAYER,
        )

    def test_detects_four_player_mode_from_planets_and_fleets(self) -> None:
        facts = strategy_mode_facts(
            state(
                player_id=0,
                planets=(planet(3, 3), planet(1, 1), planet(5, -1)),
                fleets=(fleet(2, 2),),
            )
        )

        self.assertEqual(facts.mode, StrategyMode.FOUR_PLAYER)
        self.assertEqual(facts.active_player_ids, (0, 1, 2, 3))
        self.assertEqual(facts.opponent_player_ids, (1, 2, 3))
        self.assertEqual(facts.player_count, 4)
        self.assertIsNone(facts.note)

    def test_unknown_mode_for_ambiguous_player_count(self) -> None:
        facts = strategy_mode_facts(
            state(
                player_id=0,
                planets=(planet(1, 0), planet(2, 1), planet(3, 2)),
            )
        )

        self.assertEqual(facts.mode, StrategyMode.UNKNOWN)
        self.assertEqual(facts.active_player_ids, (0, 1, 2))
        self.assertEqual(facts.opponent_player_ids, (1, 2))
        self.assertEqual(facts.player_count, 3)
        self.assertEqual(facts.note, "unknown player count")

    def test_negative_owners_are_excluded_from_active_players(self) -> None:
        facts = strategy_mode_facts(
            state(
                player_id=0,
                planets=(planet(1, -1), planet(2, -2), planet(3, 1)),
                fleets=(fleet(1, -1),),
            )
        )

        self.assertEqual(facts.mode, StrategyMode.TWO_PLAYER)
        self.assertEqual(facts.active_player_ids, (0, 1))
        self.assertEqual(facts.opponent_player_ids, (1,))

    def test_fleets_count_toward_active_player_ids(self) -> None:
        facts = strategy_mode_facts(
            state(
                player_id=0,
                planets=(planet(1, 0),),
                fleets=(fleet(1, 1),),
            )
        )

        self.assertEqual(facts.mode, StrategyMode.TWO_PLAYER)
        self.assertEqual(facts.active_player_ids, (0, 1))
        self.assertEqual(facts.opponent_player_ids, (1,))

    def test_valid_state_player_id_is_included_when_absent_from_ownership(self) -> None:
        facts = strategy_mode_facts(
            state(
                player_id=0,
                planets=(planet(1, 1),),
                fleets=(),
            )
        )

        self.assertEqual(facts.mode, StrategyMode.TWO_PLAYER)
        self.assertEqual(facts.active_player_ids, (0, 1))
        self.assertEqual(facts.opponent_player_ids, (1,))

    def test_missing_player_id_uses_empty_opponent_tuple(self) -> None:
        facts = strategy_mode_facts(
            state(
                player_id=None,
                planets=(planet(1, 0), planet(2, 1)),
            )
        )

        self.assertEqual(facts.mode, StrategyMode.TWO_PLAYER)
        self.assertEqual(facts.player_id, None)
        self.assertEqual(facts.active_player_ids, (0, 1))
        self.assertEqual(facts.opponent_player_ids, ())
        self.assertEqual(facts.player_count, 2)

    def test_negative_state_player_id_is_not_included(self) -> None:
        facts = strategy_mode_facts(
            state(
                player_id=-1,
                planets=(planet(1, 1),),
            )
        )

        self.assertEqual(facts.mode, StrategyMode.UNKNOWN)
        self.assertEqual(facts.active_player_ids, (1,))
        self.assertEqual(facts.opponent_player_ids, (1,))
        self.assertEqual(facts.note, "unknown player count")

    def test_strategy_mode_detection_does_not_mutate_state(self) -> None:
        original = state(
            player_id=0,
            planets=(planet(1, 0), planet(2, 1)),
            fleets=(fleet(1, 1),),
        )
        before = copy.deepcopy(original)

        strategy_mode_facts(original)
        detect_strategy_mode(original)

        self.assertEqual(original, before)

    def test_strategy_mode_boundary_does_not_call_deferred_logic(self) -> None:
        with (
            patch("ow_planner.candidates.generate_candidates") as generate,
            patch("ow_planner.evaluation.evaluate_candidates") as evaluate,
            patch("ow_planner.scoring.score_evaluations") as score,
            patch("ow_planner.response.evaluate_responses") as responses,
            patch("ow_planner.commitment.commitment_options_for_candidates") as commitments,
            patch("ow_planner.actions.mission_candidate_to_actions") as actions,
            patch("ow_sim.timeline.simulate_ticks") as simulate_ticks,
            patch("ow_sim.whatif.simulate_launch_orders") as simulate_launch_orders,
        ):
            strategy_mode_facts(
                state(
                    player_id=0,
                    planets=(planet(1, 0), planet(2, 1)),
                )
            )

        generate.assert_not_called()
        evaluate.assert_not_called()
        score.assert_not_called()
        responses.assert_not_called()
        commitments.assert_not_called()
        actions.assert_not_called()
        simulate_ticks.assert_not_called()
        simulate_launch_orders.assert_not_called()


if __name__ == "__main__":
    unittest.main()
