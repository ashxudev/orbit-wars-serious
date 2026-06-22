"""Tests for Mission Generation Cycle 6 public candidate generation."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from agents.runtime_state import observation_to_game_state
from ow_planner import (
    CandidateGenerationConfig,
    CandidateOutcome,
    MissionType,
    generate_candidates,
)
from ow_sim.state import GameState, Planet


def planet_at(
    planet_id: int,
    owner: int,
    x: float,
    y: float,
    ships: int,
    production: int = 0,
    radius: float = 0.0,
) -> Planet:
    return Planet(
        planet_id=planet_id,
        owner=owner,
        x=x,
        y=y,
        radius=radius,
        ships=ships,
        production=production,
        raw=(planet_id, owner, x, y, radius, ships, production),
    )


def generation_state(
    *,
    source_ships: int = 10,
    include_neutral: bool = True,
    include_enemy: bool = True,
    next_fleet_id: int | None = 100,
) -> GameState:
    source = planet_at(1, 0, 0.0, 0.0, source_ships)
    planets = [source]
    if include_neutral:
        planets.append(planet_at(2, -1, 1.0, 0.0, 0, radius=0.5))
    if include_enemy:
        planets.append(planet_at(3, 1, 0.0, 1.0, 0, radius=0.5))
    planet_tuple = tuple(planets)
    return GameState(
        tick=0,
        player_id=0,
        planets=planet_tuple,
        initial_planets=planet_tuple,
        next_fleet_id=next_fleet_id,
        raw_observation={
            "step": 0,
            "player": 0,
            "planets": [list(planet.raw) for planet in planet_tuple],
            "fleets": [],
            "next_fleet_id": next_fleet_id,
        },
    )


class PlannerGenerationTests(unittest.TestCase):
    def test_generate_candidates_returns_neutral_capture_and_enemy_attack(self) -> None:
        candidates = generate_candidates(generation_state())

        self.assertEqual(
            tuple(candidate.mission_type for candidate in candidates),
            (MissionType.CAPTURE_NEUTRAL, MissionType.ATTACK_ENEMY),
        )
        self.assertEqual(
            tuple(candidate.target_planet_id for candidate in candidates),
            (2, 3),
        )
        self.assertEqual(
            tuple(candidate.source_planet_ids for candidate in candidates),
            ((1,), (1,)),
        )
        self.assertEqual(
            tuple(candidate.outcome for candidate in candidates),
            (CandidateOutcome.VALIDATED, CandidateOutcome.VALIDATED),
        )
        self.assertEqual(
            tuple(candidate.launches[0].source_planet_id for candidate in candidates),
            (1, 1),
        )
        self.assertEqual(
            tuple(candidate.launches[0].ships for candidate in candidates),
            (1, 1),
        )

    def test_generate_candidates_recovers_owned_target_reinforcement(self) -> None:
        source = planet_at(1, 0, 0.0, 0.0, 10)
        held_target = planet_at(2, 0, 3.0, 4.0, 50, production=3)
        planets = (source, held_target)
        state = GameState(
            tick=0,
            player_id=0,
            planets=planets,
            initial_planets=planets,
            next_fleet_id=100,
        )

        candidates = generate_candidates(state)

        self.assertEqual(len(candidates), 2)
        self.assertEqual(
            tuple(candidate.mission_type for candidate in candidates),
            (MissionType.REINFORCE, MissionType.REINFORCE),
        )
        self.assertEqual(
            tuple(candidate.target_planet_id for candidate in candidates),
            (1, 2),
        )
        self.assertEqual(
            tuple(candidate.source_planet_ids for candidate in candidates),
            ((2,), (1,)),
        )
        self.assertEqual(
            tuple(candidate.launches[0].ships for candidate in candidates),
            (1, 1),
        )

    def test_four_player_continuation_prioritizes_owned_retention_under_tight_cap(
        self,
    ) -> None:
        planets = (
            planet_at(1, 0, 0.0, 0.0, 20, production=6),
            planet_at(2, 0, 1.0, 0.0, 10, production=6),
            planet_at(3, -1, 0.0, 1.0, 0, production=1, radius=0.5),
            planet_at(4, 1, 10.0, 0.0, 5, production=1),
            planet_at(5, 2, 12.0, 0.0, 5, production=1),
            planet_at(6, 3, 14.0, 0.0, 5, production=1),
        )
        state = GameState(
            tick=0,
            player_id=0,
            planets=planets,
            initial_planets=planets,
            next_fleet_id=100,
        )

        candidates = generate_candidates(
            state,
            CandidateGenerationConfig(max_candidates=1, max_validation_attempts=1),
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].mission_type, MissionType.REINFORCE)
        self.assertEqual(candidates[0].outcome, CandidateOutcome.VALIDATED)

    def test_launch_payloads_are_same_factual_launches_validated_by_outcome_boundary(self) -> None:
        candidates = generate_candidates(generation_state(include_enemy=False))

        self.assertEqual(len(candidates), 1)
        launch = candidates[0].launches[0]
        self.assertEqual(launch.source_planet_id, 1)
        self.assertEqual(launch.angle, 0.0)
        self.assertEqual(launch.ships, 1)
        self.assertIsNone(launch.player_id)

    def test_no_owned_sources_returns_empty_tuple(self) -> None:
        neutral = planet_at(2, -1, 1.0, 0.0, 0, radius=0.5)
        state = GameState(
            tick=0,
            player_id=0,
            planets=(neutral,),
            initial_planets=(neutral,),
            next_fleet_id=100,
        )

        self.assertEqual(generate_candidates(state), ())

    def test_no_affordable_candidates_returns_empty_tuple(self) -> None:
        self.assertEqual(generate_candidates(generation_state(source_ships=0)), ())

    def test_simulator_validation_rejects_all_candidates_returns_empty_tuple(self) -> None:
        self.assertEqual(generate_candidates(generation_state(next_fleet_id=None)), ())

    def test_deterministic_ordering_is_preserved(self) -> None:
        first = generate_candidates(generation_state())
        second = generate_candidates(generation_state())

        self.assertEqual(first, second)
        self.assertEqual(
            tuple((candidate.mission_type, candidate.target_planet_id) for candidate in first),
            (
                (MissionType.CAPTURE_NEUTRAL, 2),
                (MissionType.ATTACK_ENEMY, 3),
            ),
        )

    def test_candidate_limit_none_zero_and_positive_values(self) -> None:
        state = generation_state()

        self.assertEqual(
            len(generate_candidates(state, CandidateGenerationConfig(max_candidates=None))),
            2,
        )
        self.assertEqual(
            generate_candidates(state, CandidateGenerationConfig(max_candidates=0)),
            (),
        )
        self.assertEqual(
            len(generate_candidates(state, CandidateGenerationConfig(max_candidates=1))),
            1,
        )
        self.assertEqual(
            generate_candidates(state, CandidateGenerationConfig(max_candidates=1))[0].target_planet_id,
            2,
        )

    def test_candidate_limit_skips_unaffordable_pairs_before_counting_candidates(self) -> None:
        source = planet_at(1, 0, 0.0, 0.0, 5)
        close_unaffordable = planet_at(2, -1, 0.0, 1.0, 20, radius=0.5)
        later_affordable = planet_at(3, -1, 2.0, 0.0, 0, radius=0.5)
        planets = (source, close_unaffordable, later_affordable)
        state = GameState(
            tick=0,
            player_id=0,
            planets=planets,
            initial_planets=planets,
            next_fleet_id=100,
        )

        candidates = generate_candidates(
            state,
            CandidateGenerationConfig(max_candidates=1),
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].target_planet_id, 3)

    def test_generate_candidates_recovers_low_owned_two_player_pressure_candidate(
        self,
    ) -> None:
        source = planet_at(1, 0, 0.0, 0.0, 5)
        tough_neutral = planet_at(2, -1, 1.0, 0.0, 6, production=1, radius=0.5)
        planets = (source, tough_neutral)
        state = GameState(
            tick=0,
            player_id=0,
            planets=planets,
            initial_planets=planets,
            next_fleet_id=100,
        )

        candidates = generate_candidates(
            state,
            CandidateGenerationConfig(max_candidates=1, max_validation_attempts=1),
        )

        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate.mission_type, MissionType.CAPTURE_NEUTRAL)
        self.assertEqual(candidate.target_planet_id, 2)
        self.assertEqual(candidate.outcome, CandidateOutcome.VALIDATED)
        self.assertEqual(candidate.note, "early two-player pressure recovery")
        self.assertEqual(candidate.launches[0].ships, 4)

    def test_generate_candidates_keeps_pressure_recovery_bounded(self) -> None:
        source = planet_at(1, 0, 0.0, 0.0, 5)
        first_neutral = planet_at(2, -1, 1.0, 0.0, 6, production=1, radius=0.5)
        second_neutral = planet_at(3, -1, 2.0, 0.0, 6, production=1, radius=0.5)
        planets = (source, first_neutral, second_neutral)
        state = GameState(
            tick=0,
            player_id=0,
            planets=planets,
            initial_planets=planets,
            next_fleet_id=100,
        )

        self.assertEqual(
            generate_candidates(
                state,
                CandidateGenerationConfig(max_candidates=1, max_validation_attempts=0),
            ),
            (),
        )
        self.assertEqual(
            len(
                generate_candidates(
                    state,
                    CandidateGenerationConfig(
                        max_candidates=1,
                        max_validation_attempts=1,
                    ),
                )
            ),
            1,
        )

    def test_historical_two_player_collapse_fixtures_recover_candidates(self) -> None:
        fixture_dir = (
            Path(__file__).resolve().parent
            / "fixtures"
            / "historical_gauntlet_leaks"
        )
        for fixture_name in (
            "two_p_collapse_claude_v31_t002_p1.json",
            "two_p_collapse_claude_v9_t001_p1.json",
        ):
            with self.subTest(fixture_name=fixture_name):
                payload = json.loads(
                    (fixture_dir / fixture_name).read_text(encoding="utf-8")
                )
                state = observation_to_game_state(payload["observation"])

                candidates = generate_candidates(
                    state,
                    CandidateGenerationConfig(
                        max_candidates=8,
                        max_validation_attempts=8,
                    ),
                )

                self.assertGreater(len(candidates), 0)
                self.assertLessEqual(len(candidates), 8)
                self.assertTrue(
                    any(
                        candidate.note == "early two-player pressure recovery"
                        for candidate in candidates
                    )
                )

    def test_historical_reduced_owner_pressure_fixture_recovers_candidates(self) -> None:
        fixture_dir = (
            Path(__file__).resolve().parent
            / "fixtures"
            / "historical_gauntlet_leaks"
        )
        payload = json.loads(
            (
                fixture_dir / "four_p_ow2_reference_strategy_pressure_t189_p0.json"
            ).read_text(encoding="utf-8")
        )
        state = observation_to_game_state(payload["observation"])

        candidates = generate_candidates(
            state,
            CandidateGenerationConfig(max_candidates=8, max_validation_attempts=8),
        )

        self.assertGreater(len(candidates), 0)
        self.assertLessEqual(len(candidates), 8)
        self.assertTrue(
            any(
                candidate.note == "reduced-owner pressure recovery"
                for candidate in candidates
            )
        )

    def test_candidate_limit_zero_skips_validation_work(self) -> None:
        from ow_planner.outcomes import validate_estimated_pair_outcomes

        with patch(
            "ow_planner.outcomes.validate_estimated_pair_outcomes",
            wraps=validate_estimated_pair_outcomes,
        ) as validate:
            candidates = generate_candidates(
                generation_state(),
                CandidateGenerationConfig(max_candidates=0),
            )

        self.assertEqual(candidates, ())
        validate.assert_not_called()

    def test_candidate_limit_bounds_validation_work(self) -> None:
        from ow_planner.outcomes import validate_estimated_pair_outcomes

        with patch(
            "ow_planner.outcomes.validate_estimated_pair_outcomes",
            wraps=validate_estimated_pair_outcomes,
        ) as validate:
            candidates = generate_candidates(
                generation_state(),
                CandidateGenerationConfig(max_candidates=1),
            )

        self.assertEqual(len(candidates), 1)
        validate.assert_called_once()
        self.assertEqual(len(validate.call_args.args[1]), 1)

    def test_validation_attempt_limit_bounds_affordable_validation_work(self) -> None:
        from ow_planner.outcomes import validate_estimated_pair_outcomes

        with patch(
            "ow_planner.outcomes.validate_estimated_pair_outcomes",
            wraps=validate_estimated_pair_outcomes,
        ) as validate:
            candidates = generate_candidates(
                generation_state(),
                CandidateGenerationConfig(
                    max_candidates=None,
                    max_validation_attempts=1,
                ),
            )

        self.assertEqual(len(candidates), 1)
        validate.assert_called_once()
        self.assertEqual(len(validate.call_args.args[1]), 1)

    def test_config_rejects_invalid_candidate_limits(self) -> None:
        for field_name in ("max_candidates", "max_validation_attempts"):
            for value in (-1, True, 1.5, "1"):
                kwargs = {field_name: value}
                with self.subTest(field_name=field_name, value=value):
                    with self.assertRaises(ValueError):
                        CandidateGenerationConfig(**kwargs)

    def test_validation_attempt_limit_zero_skips_validation_work(self) -> None:
        from ow_planner.outcomes import validate_estimated_pair_outcomes

        with patch(
            "ow_planner.outcomes.validate_estimated_pair_outcomes",
            wraps=validate_estimated_pair_outcomes,
        ) as validate:
            candidates = generate_candidates(
                generation_state(),
                CandidateGenerationConfig(max_validation_attempts=0),
            )

        self.assertEqual(candidates, ())
        validate.assert_not_called()

    def test_config_accepts_uncapped_validation_attempts(self) -> None:
        config = CandidateGenerationConfig(max_validation_attempts=None)

        self.assertIsNone(config.max_validation_attempts)

    def test_config_accepts_zero_validation_attempts(self) -> None:
        config = CandidateGenerationConfig(max_validation_attempts=0)

        self.assertEqual(config.max_validation_attempts, 0)

    def test_generation_does_not_mutate_input_state(self) -> None:
        state = generation_state()
        before = copy.deepcopy(state)

        generate_candidates(state)

        self.assertEqual(state, before)
        self.assertEqual(state.raw_observation, before.raw_observation)

    def test_candidates_do_not_include_scoring_or_selection_fields(self) -> None:
        candidates = generate_candidates(generation_state())

        self.assertTrue(candidates)
        for candidate in candidates:
            self.assertFalse(hasattr(candidate, "score"))
            self.assertFalse(hasattr(candidate, "rank"))
            self.assertFalse(hasattr(candidate, "selected"))


if __name__ == "__main__":
    unittest.main()
