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
    capture_and_hold_commitment_option,
    commitment_options_for_candidates,
    minimum_capture_commitment_option,
    no_attack_commitment_option,
)
from ow_sim.state import GameState, Planet


def state_with_planet(
    *,
    planet_id: int = 1,
    owner: int = 0,
    ships: int = 12,
    player_id: int | None = 0,
) -> GameState:
    planet = Planet(
        planet_id=planet_id,
        owner=owner,
        x=10.0,
        y=20.0,
        radius=2.0,
        ships=ships,
        production=1,
        raw=(planet_id, owner, 10.0, 20.0, 2.0, ships, 1),
    )
    return GameState(
        tick=5,
        player_id=player_id,
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


def multi_launch_mission_candidate() -> MissionCandidate:
    first = LaunchCandidate(
        source_planet_id=2,
        angle=0.5,
        ships=4,
        player_id=0,
    )
    second = LaunchCandidate(
        source_planet_id=1,
        angle=0.25,
        ships=6,
        player_id=0,
    )
    return MissionCandidate(
        mission_type=MissionType.ATTACK_ENEMY,
        target_planet_id=4,
        source_planet_ids=(2, 1),
        launches=(first, second),
    )


def no_launch_mission_candidate() -> MissionCandidate:
    return MissionCandidate(
        mission_type=MissionType.CAPTURE_NEUTRAL,
        target_planet_id=2,
    )


def repeated_source_mission_candidate() -> MissionCandidate:
    first = LaunchCandidate(
        source_planet_id=1,
        angle=0.25,
        ships=2,
        player_id=0,
    )
    second = LaunchCandidate(
        source_planet_id=1,
        angle=0.75,
        ships=3,
        player_id=0,
    )
    return MissionCandidate(
        mission_type=MissionType.CAPTURE_NEUTRAL,
        target_planet_id=2,
        source_planet_ids=(1, 1),
        launches=(first, second),
    )


class PlannerCommitmentTests(unittest.TestCase):
    def test_commitment_module_imports_and_exports_are_available(self) -> None:
        importlib.import_module("ow_planner.commitment")

        self.assertIs(CandidateCommitmentOptions, CandidateCommitmentOptions)
        self.assertIs(CommitmentOption, CommitmentOption)
        self.assertIs(CommitmentOptionStatus, CommitmentOptionStatus)
        self.assertIs(CommitmentOptionType, CommitmentOptionType)
        self.assertIs(CommitmentPolicyConfig, CommitmentPolicyConfig)
        self.assertIsNotNone(capture_and_hold_commitment_option)
        self.assertIsNotNone(commitment_options_for_candidates)
        self.assertIsNotNone(minimum_capture_commitment_option)
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
        self.assertEqual(config.capture_hold_buffer_ships, 5)
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

    def test_config_rejects_invalid_capture_hold_buffer_ships(self) -> None:
        for value in (-1, True, 1.5, "5", None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    CommitmentPolicyConfig(capture_hold_buffer_ships=value)

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

    def test_minimum_capture_commitment_option_fields_are_stable(self) -> None:
        candidate = multi_launch_mission_candidate()

        option = minimum_capture_commitment_option(candidate)

        self.assertEqual(option.option_type, CommitmentOptionType.MINIMUM_CAPTURE)
        self.assertIs(option.candidate, candidate)
        self.assertIs(option.launches, candidate.launches)
        self.assertEqual(option.source_planet_ids, (2, 1))
        self.assertEqual(option.ships_committed, 10)
        self.assertEqual(option.status, CommitmentOptionStatus.VALIDATED)
        self.assertEqual(option.note, "minimum capture")

    def test_minimum_capture_commitment_option_rejects_no_launch_candidate(self) -> None:
        candidate = no_launch_mission_candidate()

        option = minimum_capture_commitment_option(candidate)

        self.assertEqual(option.option_type, CommitmentOptionType.MINIMUM_CAPTURE)
        self.assertIs(option.candidate, candidate)
        self.assertEqual(option.launches, ())
        self.assertEqual(option.source_planet_ids, ())
        self.assertEqual(option.ships_committed, 0)
        self.assertEqual(option.status, CommitmentOptionStatus.REJECTED)
        self.assertEqual(option.note, "candidate has no launches")

    def test_capture_and_hold_commitment_option_adds_default_buffer(self) -> None:
        candidate = mission_candidate()

        option = capture_and_hold_commitment_option(
            state_with_planet(ships=12),
            candidate,
        )

        self.assertEqual(option.option_type, CommitmentOptionType.CAPTURE_AND_HOLD)
        self.assertIs(option.candidate, candidate)
        self.assertEqual(option.source_planet_ids, (1,))
        self.assertEqual(option.ships_committed, 8)
        self.assertEqual(option.status, CommitmentOptionStatus.VALIDATED)
        self.assertEqual(option.note, "capture and hold")
        self.assertEqual(len(option.launches), 1)
        self.assertEqual(option.launches[0].source_planet_id, 1)
        self.assertEqual(option.launches[0].angle, 0.25)
        self.assertEqual(option.launches[0].ships, 8)
        self.assertEqual(option.launches[0].player_id, 0)

    def test_capture_and_hold_zero_buffer_mirrors_candidate_launches(self) -> None:
        candidate = mission_candidate()

        option = capture_and_hold_commitment_option(
            state_with_planet(ships=3),
            candidate,
            CommitmentPolicyConfig(capture_hold_buffer_ships=0),
        )

        self.assertEqual(option.option_type, CommitmentOptionType.CAPTURE_AND_HOLD)
        self.assertIs(option.candidate, candidate)
        self.assertIs(option.launches, candidate.launches)
        self.assertEqual(option.source_planet_ids, (1,))
        self.assertEqual(option.ships_committed, 3)
        self.assertEqual(option.status, CommitmentOptionStatus.VALIDATED)
        self.assertEqual(option.note, "capture and hold")

    def test_capture_and_hold_accounts_for_repeated_source_launches(self) -> None:
        candidate = repeated_source_mission_candidate()

        option = capture_and_hold_commitment_option(
            state_with_planet(ships=7),
            candidate,
            CommitmentPolicyConfig(capture_hold_buffer_ships=2),
        )

        self.assertEqual(option.status, CommitmentOptionStatus.VALIDATED)
        self.assertEqual(tuple(launch.ships for launch in option.launches), (4, 3))
        self.assertEqual(option.source_planet_ids, (1, 1))
        self.assertEqual(option.ships_committed, 7)

    def test_capture_and_hold_rejects_no_launch_candidate(self) -> None:
        candidate = no_launch_mission_candidate()

        option = capture_and_hold_commitment_option(state_with_planet(), candidate)

        self.assertEqual(option.option_type, CommitmentOptionType.CAPTURE_AND_HOLD)
        self.assertIs(option.candidate, candidate)
        self.assertEqual(option.launches, ())
        self.assertEqual(option.source_planet_ids, ())
        self.assertEqual(option.ships_committed, 0)
        self.assertEqual(option.status, CommitmentOptionStatus.REJECTED)
        self.assertEqual(option.note, "candidate has no launches")

    def test_capture_and_hold_rejects_insufficient_source_ships(self) -> None:
        candidate = mission_candidate()

        option = capture_and_hold_commitment_option(
            state_with_planet(ships=6),
            candidate,
        )

        self.assertEqual(option.option_type, CommitmentOptionType.CAPTURE_AND_HOLD)
        self.assertEqual(option.launches, ())
        self.assertEqual(option.source_planet_ids, ())
        self.assertEqual(option.ships_committed, 0)
        self.assertEqual(option.status, CommitmentOptionStatus.REJECTED)
        self.assertEqual(option.note, "insufficient source ships for hold buffer")

    def test_capture_and_hold_rejects_missing_source_planet(self) -> None:
        candidate = mission_candidate()

        option = capture_and_hold_commitment_option(
            state_with_planet(planet_id=9),
            candidate,
        )

        self.assertEqual(option.status, CommitmentOptionStatus.REJECTED)
        self.assertEqual(option.note, "missing source planet")

    def test_capture_and_hold_rejects_non_player_owned_source(self) -> None:
        candidate = mission_candidate()

        option = capture_and_hold_commitment_option(
            state_with_planet(owner=1),
            candidate,
        )

        self.assertEqual(option.status, CommitmentOptionStatus.REJECTED)
        self.assertEqual(option.note, "source planet not owned by player")

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
            tuple(option.option_type for option in wrappers[0].options),
            (
                CommitmentOptionType.NO_ATTACK,
                CommitmentOptionType.MINIMUM_CAPTURE,
                CommitmentOptionType.CAPTURE_AND_HOLD,
            ),
        )
        self.assertIs(wrappers[0].options[0].candidate, first)
        self.assertIs(wrappers[0].options[1].candidate, first)
        self.assertIs(wrappers[0].options[2].candidate, first)
        self.assertIs(wrappers[1].options[0].candidate, second)
        self.assertIs(wrappers[1].options[1].candidate, second)
        self.assertIs(wrappers[1].options[2].candidate, second)
        self.assertEqual(tuple(wrapper.notes for wrapper in wrappers), ((), ()))

    def test_commitment_options_put_options_in_stable_order(self) -> None:
        (wrapper,) = commitment_options_for_candidates(
            state_with_planet(),
            (mission_candidate(),),
        )

        self.assertEqual(wrapper.options[0].option_type, CommitmentOptionType.NO_ATTACK)
        self.assertEqual(
            wrapper.options[1].option_type,
            CommitmentOptionType.MINIMUM_CAPTURE,
        )
        self.assertEqual(
            wrapper.options[2].option_type,
            CommitmentOptionType.CAPTURE_AND_HOLD,
        )

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

    def test_commitment_options_limit_two_includes_minimum_capture_option(self) -> None:
        (wrapper,) = commitment_options_for_candidates(
            state_with_planet(),
            (mission_candidate(),),
            CommitmentPolicyConfig(max_options_per_candidate=2),
        )

        self.assertEqual(
            tuple(option.option_type for option in wrapper.options),
            (
                CommitmentOptionType.NO_ATTACK,
                CommitmentOptionType.MINIMUM_CAPTURE,
            ),
        )

    def test_commitment_options_unlimited_includes_minimum_capture_option(self) -> None:
        (wrapper,) = commitment_options_for_candidates(
            state_with_planet(),
            (mission_candidate(),),
            CommitmentPolicyConfig(max_options_per_candidate=None),
        )

        self.assertEqual(
            tuple(option.option_type for option in wrapper.options),
            (
                CommitmentOptionType.NO_ATTACK,
                CommitmentOptionType.MINIMUM_CAPTURE,
                CommitmentOptionType.CAPTURE_AND_HOLD,
            ),
        )

    def test_commitment_options_limit_three_includes_capture_and_hold_option(self) -> None:
        (wrapper,) = commitment_options_for_candidates(
            state_with_planet(),
            (mission_candidate(),),
            CommitmentPolicyConfig(max_options_per_candidate=3),
        )

        self.assertEqual(
            tuple(option.option_type for option in wrapper.options),
            (
                CommitmentOptionType.NO_ATTACK,
                CommitmentOptionType.MINIMUM_CAPTURE,
                CommitmentOptionType.CAPTURE_AND_HOLD,
            ),
        )

    def test_commitment_options_attaches_rejected_minimum_capture_for_no_launch_candidate(
        self,
    ) -> None:
        (wrapper,) = commitment_options_for_candidates(
            state_with_planet(),
            (no_launch_mission_candidate(),),
        )

        self.assertEqual(wrapper.options[0].option_type, CommitmentOptionType.NO_ATTACK)
        self.assertEqual(
            wrapper.options[1].option_type,
            CommitmentOptionType.MINIMUM_CAPTURE,
        )
        self.assertEqual(wrapper.options[1].status, CommitmentOptionStatus.REJECTED)
        self.assertEqual(wrapper.options[1].note, "candidate has no launches")
        self.assertEqual(
            wrapper.options[2].option_type,
            CommitmentOptionType.CAPTURE_AND_HOLD,
        )
        self.assertEqual(wrapper.options[2].status, CommitmentOptionStatus.REJECTED)
        self.assertEqual(wrapper.options[2].note, "candidate has no launches")

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
            patch("ow_planner.actions.mission_candidate_to_orders") as orders,
            patch("ow_planner.actions.mission_candidate_to_actions") as actions,
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
        orders.assert_not_called()
        actions.assert_not_called()
        simulate_ticks.assert_not_called()
        simulate_launch_orders.assert_not_called()


if __name__ == "__main__":
    unittest.main()
