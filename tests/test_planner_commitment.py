"""Tests for Commitment Policy Cycle 0 structural API boundary."""

from __future__ import annotations

import copy
import importlib
import unittest
from dataclasses import FrozenInstanceError
from unittest.mock import patch

from ow_planner import (
    CandidateCommitmentOptions,
    CommitmentOption,
    CommitmentOptionStatus,
    CommitmentOptionType,
    CommitmentPolicyConfig,
    LaunchCandidate,
    MissionCandidate,
    MissionType,
    commitment_options_for_candidates,
    no_attack_commitment_option,
)
from ow_sim.state import GameState, Planet


def state_with_planet() -> GameState:
    planet = Planet(
        planet_id=1,
        owner=0,
        x=10.0,
        y=20.0,
        radius=2.0,
        ships=12,
        production=1,
        raw=(1, 0, 10.0, 20.0, 2.0, 12, 1),
    )
    return GameState(
        tick=5,
        player_id=0,
        planets=(planet,),
        raw_observation={
            "step": 5,
            "planets": [list(planet.raw)],
        },
    )


def mission_candidate(target_planet_id: int = 2) -> MissionCandidate:
    launch = LaunchCandidate(
        source_planet_id=1,
        angle=0.25,
        ships=3,
        player_id=0,
    )
    return MissionCandidate(
        mission_type=MissionType.CAPTURE_NEUTRAL,
        target_planet_id=target_planet_id,
        source_planet_ids=(1,),
        launches=(launch,),
    )


class PlannerCommitmentTests(unittest.TestCase):
    def test_commitment_module_imports_and_exports_are_available(self) -> None:
        importlib.import_module("ow_planner.commitment")

        self.assertIs(CandidateCommitmentOptions, CandidateCommitmentOptions)
        self.assertIs(CommitmentOption, CommitmentOption)
        self.assertIs(CommitmentOptionStatus, CommitmentOptionStatus)
        self.assertIs(CommitmentOptionType, CommitmentOptionType)
        self.assertIs(CommitmentPolicyConfig, CommitmentPolicyConfig)
        self.assertIsNotNone(commitment_options_for_candidates)
        self.assertIsNotNone(no_attack_commitment_option)

    def test_commitment_option_type_values_are_stable(self) -> None:
        self.assertEqual(CommitmentOptionType.NO_ATTACK.value, "no_attack")
        self.assertEqual(
            CommitmentOptionType.MINIMUM_CAPTURE.value,
            "minimum_capture",
        )
        self.assertEqual(
            CommitmentOptionType.CAPTURE_AND_HOLD.value,
            "capture_and_hold",
        )
        self.assertEqual(
            CommitmentOptionType.RESERVE_PRESERVING.value,
            "reserve_preserving",
        )
        self.assertEqual(CommitmentOptionType.FULL_SOURCE.value, "full_source")
        self.assertEqual(
            CommitmentOptionType.COORDINATED_MULTI_SOURCE.value,
            "coordinated_multi_source",
        )

    def test_commitment_option_status_values_are_stable(self) -> None:
        self.assertEqual(CommitmentOptionStatus.UNTESTED.value, "untested")
        self.assertEqual(CommitmentOptionStatus.VALIDATED.value, "validated")
        self.assertEqual(CommitmentOptionStatus.REJECTED.value, "rejected")

    def test_commitment_dataclasses_are_constructible_frozen_and_slotted(self) -> None:
        candidate = mission_candidate()
        option = CommitmentOption(
            option_type=CommitmentOptionType.MINIMUM_CAPTURE,
            candidate=candidate,
            launches=candidate.launches,
            source_planet_ids=candidate.source_planet_ids,
            ships_committed=3,
            note="structural",
        )
        wrapper = CandidateCommitmentOptions(
            candidate=candidate,
            options=(option,),
            notes=("placeholder",),
        )
        config = CommitmentPolicyConfig(max_options_per_candidate=2)

        self.assertEqual(option.status, CommitmentOptionStatus.UNTESTED)
        self.assertEqual(option.ships_committed, 3)
        self.assertEqual(wrapper.options, (option,))
        self.assertEqual(config.max_options_per_candidate, 2)
        self.assertTrue(hasattr(CommitmentOption, "__slots__"))
        self.assertTrue(hasattr(CandidateCommitmentOptions, "__slots__"))
        self.assertTrue(hasattr(CommitmentPolicyConfig, "__slots__"))
        with self.assertRaises(FrozenInstanceError):
            option.note = None
        with self.assertRaises(FrozenInstanceError):
            wrapper.notes = ()
        with self.assertRaises(FrozenInstanceError):
            config.max_options_per_candidate = 1

    def test_config_rejects_invalid_max_options_per_candidate(self) -> None:
        for value in (-1, True, 1.5, "3", None):
            with self.subTest(value=value):
                if value is None:
                    self.assertIsNone(
                        CommitmentPolicyConfig(
                            max_options_per_candidate=value,
                        ).max_options_per_candidate
                    )
                else:
                    with self.assertRaises(ValueError):
                        CommitmentPolicyConfig(max_options_per_candidate=value)

    def test_commitment_options_returns_empty_tuple_for_empty_candidates(self) -> None:
        self.assertEqual(commitment_options_for_candidates(state_with_planet(), ()), ())

    def test_no_attack_commitment_option_fields_are_stable(self) -> None:
        candidate = mission_candidate()

        option = no_attack_commitment_option(candidate)

        self.assertEqual(option.option_type, CommitmentOptionType.NO_ATTACK)
        self.assertIs(option.candidate, candidate)
        self.assertEqual(option.launches, ())
        self.assertEqual(option.source_planet_ids, ())
        self.assertEqual(option.ships_committed, 0)
        self.assertEqual(option.status, CommitmentOptionStatus.VALIDATED)
        self.assertEqual(option.note, "no attack")

    def test_no_attack_commitment_option_accepts_no_candidate(self) -> None:
        option = no_attack_commitment_option()

        self.assertEqual(option.option_type, CommitmentOptionType.NO_ATTACK)
        self.assertIsNone(option.candidate)
        self.assertEqual(option.status, CommitmentOptionStatus.VALIDATED)

    def test_commitment_options_preserves_candidate_order_and_identity(self) -> None:
        first = mission_candidate(2)
        second = mission_candidate(3)

        wrappers = commitment_options_for_candidates(
            state_with_planet(),
            (first, second),
        )

        self.assertEqual(tuple(wrapper.candidate for wrapper in wrappers), (first, second))
        self.assertIs(wrappers[0].candidate, first)
        self.assertIs(wrappers[1].candidate, second)
        self.assertEqual(
            tuple(wrapper.options[0].option_type for wrapper in wrappers),
            (CommitmentOptionType.NO_ATTACK, CommitmentOptionType.NO_ATTACK),
        )
        self.assertIs(wrappers[0].options[0].candidate, first)
        self.assertIs(wrappers[1].options[0].candidate, second)
        self.assertEqual(tuple(wrapper.notes for wrapper in wrappers), ((), ()))

    def test_commitment_options_put_no_attack_first(self) -> None:
        (wrapper,) = commitment_options_for_candidates(
            state_with_planet(),
            (mission_candidate(),),
        )

        self.assertEqual(wrapper.options[0].option_type, CommitmentOptionType.NO_ATTACK)

    def test_commitment_options_respects_zero_limit_without_inventing_options(self) -> None:
        (wrapper,) = commitment_options_for_candidates(
            state_with_planet(),
            (mission_candidate(),),
            CommitmentPolicyConfig(max_options_per_candidate=0),
        )

        self.assertEqual(wrapper.options, ())

    def test_commitment_options_positive_limit_includes_no_attack_option(self) -> None:
        (wrapper,) = commitment_options_for_candidates(
            state_with_planet(),
            (mission_candidate(),),
            CommitmentPolicyConfig(max_options_per_candidate=1),
        )

        self.assertEqual(len(wrapper.options), 1)
        self.assertEqual(wrapper.options[0].option_type, CommitmentOptionType.NO_ATTACK)

    def test_commitment_options_does_not_mutate_state_or_candidates(self) -> None:
        state = state_with_planet()
        candidates = (mission_candidate(),)
        state_before = copy.deepcopy(state)
        candidates_before = copy.deepcopy(candidates)

        commitment_options_for_candidates(
            state,
            candidates,
            CommitmentPolicyConfig(max_options_per_candidate=3),
        )

        self.assertEqual(state, state_before)
        self.assertEqual(candidates, candidates_before)

    def test_commitment_boundary_does_not_call_deferred_logic(self) -> None:
        with (
            patch("ow_planner.candidates.generate_candidates") as generate,
            patch("ow_planner.evaluation.evaluate_candidates") as evaluate,
            patch("ow_planner.scoring.score_evaluations") as score,
            patch("ow_planner.response.evaluate_responses") as responses,
            patch("ow_sim.timeline.simulate_ticks") as simulate_ticks,
            patch("ow_sim.whatif.simulate_launch_orders") as simulate_launch_orders,
        ):
            commitment_options_for_candidates(
                state_with_planet(),
                (mission_candidate(),),
            )

        generate.assert_not_called()
        evaluate.assert_not_called()
        score.assert_not_called()
        responses.assert_not_called()
        simulate_ticks.assert_not_called()
        simulate_launch_orders.assert_not_called()


if __name__ == "__main__":
    unittest.main()
