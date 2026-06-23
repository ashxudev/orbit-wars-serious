"""Tests for Planner V2 board diagnosis."""

from __future__ import annotations

import json
import unittest
from dataclasses import FrozenInstanceError

from ow_planner_v2 import BoardDiagnosis, PlannerV2Mode, diagnose_board
from ow_sim.state import Fleet, GameState, Planet


def planet(
    planet_id: int,
    owner: int,
    x: float,
    y: float,
    ships: int,
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
    from_planet_id: int = 1,
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


class PlannerV2DiagnosisTests(unittest.TestCase):
    def test_two_player_pressure_diagnosis_is_json_safe(self) -> None:
        state = GameState(
            tick=20,
            player_id=0,
            planets=(
                planet(1, 0, 0.0, 0.0, 4, production=3),
                planet(2, 1, 20.0, 0.0, 30, production=4),
                planet(3, -1, 8.0, 0.0, 0, production=2),
            ),
            fleets=(fleet(10, 1, -8.0, 0.0, 0.0, 10),),
        )

        diagnosis = diagnose_board(state)

        self.assertIsInstance(diagnosis, BoardDiagnosis)
        self.assertEqual(diagnosis.mode, PlannerV2Mode.TWO_PLAYER)
        self.assertEqual(diagnosis.owned_planet_count, 1)
        self.assertEqual(diagnosis.owned_production, 3)
        self.assertIn(1, diagnosis.vulnerable_owned_planet_ids)
        self.assertIn("pressure_visible", diagnosis.labels)
        decoded = json.loads(json.dumps(diagnosis.to_dict(), sort_keys=True))
        self.assertEqual(decoded["mode"], "two_player")

    def test_four_player_rank_and_plateau_context_is_visible(self) -> None:
        state = GameState(
            tick=90,
            player_id=0,
            planets=(
                planet(1, 0, 0.0, 0.0, 20, production=2),
                planet(2, 1, 20.0, 0.0, 40, production=6),
                planet(3, 2, 0.0, 20.0, 30, production=4),
                planet(4, 3, 20.0, 20.0, 25, production=3),
                planet(5, -1, 5.0, 0.0, 5, production=3),
            ),
        )

        diagnosis = diagnose_board(state)

        self.assertEqual(diagnosis.mode, PlannerV2Mode.FOUR_PLAYER)
        self.assertIn("rank_context_visible", diagnosis.labels)
        self.assertIn("four_player_plateau_context_visible", diagnosis.labels)
        self.assertGreater(len(diagnosis.high_value_target_ids), 0)

    def test_no_owned_planets_is_classified_as_endgame_source_less(self) -> None:
        state = GameState(
            tick=200,
            player_id=0,
            planets=(
                planet(1, 1, 0.0, 0.0, 20, production=2),
                planet(2, 2, 10.0, 0.0, 20, production=2),
            ),
        )

        diagnosis = diagnose_board(state)

        self.assertEqual(diagnosis.mode, PlannerV2Mode.ENDGAME)
        self.assertIn("source_less_no_owned_planets", diagnosis.labels)

    def test_report_is_frozen(self) -> None:
        diagnosis = diagnose_board(
            GameState(
                tick=0,
                player_id=0,
                planets=(planet(1, 0, 0.0, 0.0, 10, production=1),),
            )
        )

        with self.assertRaises(FrozenInstanceError):
            diagnosis.owned_planet_count = 99  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
