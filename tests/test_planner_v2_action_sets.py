"""Tests for Planner V2 action-set construction."""

from __future__ import annotations

import unittest

from ow_planner import (
    CandidateCommitmentOptions,
    CandidateOutcome,
    CommitmentOption,
    CommitmentOptionStatus,
    CommitmentOptionType,
    LaunchCandidate,
    MissionCandidate,
    MissionType,
)
from ow_planner_v2 import MissionFamily, MissionPlan, PlannerV2Config, build_action_set_plans


def candidate(source: int = 1, target: int = 2) -> MissionCandidate:
    launch = LaunchCandidate(source_planet_id=source, angle=0.0, ships=4, player_id=0)
    return MissionCandidate(
        mission_type=MissionType.CAPTURE_NEUTRAL,
        target_planet_id=target,
        source_planet_ids=(source,),
        launches=(launch,),
        outcome=CandidateOutcome.VALIDATED,
    )


class PlannerV2ActionSetTests(unittest.TestCase):
    def test_builds_action_set_from_validated_commitment(self) -> None:
        mission_candidate = candidate()
        option = CommitmentOption(
            option_type=CommitmentOptionType.RESERVE_PRESERVING,
            candidate=mission_candidate,
            launches=mission_candidate.launches,
            source_planet_ids=(1,),
            ships_committed=4,
            status=CommitmentOptionStatus.VALIDATED,
        )
        mission = MissionPlan(
            mission_id="mission-0000",
            family=MissionFamily.SAFE_EXPAND,
            candidate=mission_candidate,
        )

        action_sets = build_action_set_plans(
            (mission,),
            (CandidateCommitmentOptions(candidate=mission_candidate, options=(option,)),),
        )

        self.assertEqual(len(action_sets), 1)
        self.assertEqual(action_sets[0].launches, mission_candidate.launches)
        self.assertIn("reserve_preserving", action_sets[0].labels)

    def test_respects_action_set_cap(self) -> None:
        mission_candidate = candidate()
        option = CommitmentOption(
            option_type=CommitmentOptionType.MINIMUM_CAPTURE,
            candidate=mission_candidate,
            launches=mission_candidate.launches,
            source_planet_ids=(1,),
            ships_committed=4,
            status=CommitmentOptionStatus.VALIDATED,
        )
        mission = MissionPlan(
            mission_id="mission-0000",
            family=MissionFamily.HOLD_CAPTURE,
            candidate=mission_candidate,
        )

        self.assertEqual(
            build_action_set_plans(
                (mission,),
                (CandidateCommitmentOptions(candidate=mission_candidate, options=(option,)),),
                PlannerV2Config(max_action_sets=0),
            ),
            (),
        )

    def test_builds_bounded_defense_plus_expansion_action_set(self) -> None:
        defend_candidate = candidate(source=1, target=1)
        expand_candidate = candidate(source=2, target=3)
        defend_option = CommitmentOption(
            option_type=CommitmentOptionType.RESERVE_PRESERVING,
            candidate=defend_candidate,
            launches=defend_candidate.launches,
            source_planet_ids=(1,),
            ships_committed=4,
            status=CommitmentOptionStatus.VALIDATED,
        )
        expand_option = CommitmentOption(
            option_type=CommitmentOptionType.RESERVE_PRESERVING,
            candidate=expand_candidate,
            launches=expand_candidate.launches,
            source_planet_ids=(2,),
            ships_committed=4,
            status=CommitmentOptionStatus.VALIDATED,
        )

        action_sets = build_action_set_plans(
            (
                MissionPlan(
                    mission_id="mission-0000",
                    family=MissionFamily.URGENT_DEFEND,
                    candidate=defend_candidate,
                ),
                MissionPlan(
                    mission_id="mission-0001",
                    family=MissionFamily.SAFE_EXPAND,
                    candidate=expand_candidate,
                ),
            ),
            (
                CandidateCommitmentOptions(
                    candidate=defend_candidate,
                    options=(defend_option,),
                ),
                CandidateCommitmentOptions(
                    candidate=expand_candidate,
                    options=(expand_option,),
                ),
            ),
            PlannerV2Config(max_action_sets=3),
        )

        self.assertEqual(len(action_sets), 3)
        self.assertIn("coordinated_action_set", action_sets[2].labels)
        self.assertEqual(len(action_sets[2].launches), 2)


if __name__ == "__main__":
    unittest.main()
