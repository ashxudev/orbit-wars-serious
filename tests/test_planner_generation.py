"""Tests for Mission Generation Cycle 6 public candidate generation."""

from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

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
