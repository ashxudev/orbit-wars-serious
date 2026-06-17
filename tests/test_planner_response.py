"""Tests for the planner opponent-response API boundary."""

from __future__ import annotations

import copy
import importlib
import unittest
from dataclasses import FrozenInstanceError
from unittest.mock import patch

from ow_planner import (
    CandidateOutcome,
    CounterattackSourceFacts,
    MissionCandidate,
    MissionEvaluation,
    MissionEvaluationFacts,
    MissionEvaluationStatus,
    MissionFutureDeltaFacts,
    MissionResponseEvaluation,
    MissionResponseFacts,
    MissionTimingFacts,
    MissionType,
    PlanetEvaluationFacts,
    PlanetFutureDeltaFacts,
    RaceSourceFacts,
    ReinforcementSourceFacts,
    RespondingSourcePressureFacts,
    ResponseConfig,
    ResponseEvaluationStatus,
    ResponseSourcePressureFacts,
    ResponseSummaryFacts,
    SourceCounterattackFacts,
    TargetRaceFacts,
    TargetReinforcementFacts,
    ThirdPartyBenefitFacts,
    ThirdPartyOwnerFacts,
    evaluate_responses,
    response_source_pressure_facts,
    response_summary_facts,
    source_counterattack_facts,
    target_race_facts,
    target_reinforcement_facts,
    third_party_benefit_facts,
)
from ow_sim.state import Fleet, GameState, Planet


def response_state() -> GameState:
    return GameState(
        tick=7,
        player_id=0,
        raw_observation={"step": 7, "player": 0},
    )


def planet(
    planet_id: int,
    owner: int,
    x: float,
    y: float,
    ships: int,
    *,
    production: int = 0,
    is_comet: bool = False,
) -> Planet:
    return Planet(
        planet_id=planet_id,
        owner=owner,
        x=x,
        y=y,
        radius=1.0,
        ships=ships,
        production=production,
        is_comet=is_comet,
        raw=(planet_id, owner, x, y, 1.0, ships, production),
    )


def fleet(
    fleet_id: int,
    owner: int,
    x: float,
    y: float,
    angle: float,
    ships: int,
) -> Fleet:
    return Fleet(
        fleet_id=fleet_id,
        owner=owner,
        x=x,
        y=y,
        angle=angle,
        from_planet_id=99,
        ships=ships,
        raw=(fleet_id, owner, x, y, angle, 99, ships),
    )


def reinforcement_state() -> GameState:
    return GameState(
        tick=7,
        player_id=0,
        planets=(
            planet(2, -1, 0.0, 0.0, 0),
            planet(3, 1, 3.0, 0.0, 1),
            planet(4, 1, 10.0, 0.0, 1),
            planet(5, -1, 1.0, 1.0, 10),
            planet(6, 0, 2.0, 2.0, 10),
            planet(7, 2, 2.0, 0.0, 10, is_comet=True),
            planet(8, 2, 1.0, 0.0, 0),
        ),
        raw_observation={"step": 7, "player": 0},
    )


def no_reinforcement_state() -> GameState:
    return GameState(
        tick=7,
        player_id=0,
        planets=(
            planet(2, -1, 0.0, 0.0, 0),
            planet(5, -1, 1.0, 1.0, 10),
            planet(6, 0, 2.0, 2.0, 10),
            planet(7, 2, 2.0, 0.0, 10, is_comet=True),
        ),
        raw_observation={"step": 7, "player": 0},
    )


def counterattack_state() -> GameState:
    return GameState(
        tick=7,
        player_id=0,
        planets=(
            planet(1, 0, 0.0, 0.0, 10),
            planet(2, -1, 8.0, 0.0, 0),
            planet(3, 1, 3.0, 0.0, 6),
            planet(4, 2, 10.0, 0.0, 4),
            planet(5, -1, 1.0, 1.0, 10),
            planet(6, 0, 2.0, 2.0, 10),
            planet(7, 2, 2.0, 0.0, 10, is_comet=True),
            planet(8, 1, 1.0, 0.0, 0),
        ),
        raw_observation={"step": 7, "player": 0},
    )


def no_counterattack_state() -> GameState:
    return GameState(
        tick=7,
        player_id=0,
        planets=(
            planet(1, 0, 0.0, 0.0, 10),
            planet(2, -1, 8.0, 0.0, 0),
            planet(5, -1, 1.0, 1.0, 10),
            planet(6, 0, 2.0, 2.0, 10),
            planet(7, 2, 2.0, 0.0, 10, is_comet=True),
        ),
        raw_observation={"step": 7, "player": 0},
    )


def ffa_state() -> GameState:
    return GameState(
        tick=7,
        player_id=0,
        planets=(
            planet(1, 0, 0.0, 0.0, 10, production=2),
            planet(2, 1, 8.0, 0.0, 5, production=5),
            planet(3, 1, 9.0, 0.0, 6, production=1),
            planet(4, 2, 10.0, 0.0, 4, production=3),
            planet(5, 2, 11.0, 0.0, 7, production=2),
            planet(6, 3, 12.0, 0.0, 8, production=4),
            planet(7, -1, 13.0, 0.0, 9, production=5),
            planet(8, 3, 14.0, 0.0, 9, production=6, is_comet=True),
        ),
        raw_observation={"step": 7, "player": 0},
    )


def two_player_state() -> GameState:
    return GameState(
        tick=7,
        player_id=0,
        planets=(
            planet(1, 0, 0.0, 0.0, 10, production=2),
            planet(2, 1, 8.0, 0.0, 5, production=5),
            planet(3, 1, 9.0, 0.0, 6, production=1),
        ),
        raw_observation={"step": 7, "player": 0},
    )


def pressure_state(
    *,
    fleets: tuple[Fleet, ...] = (),
    player_planet_ships: int = 0,
) -> GameState:
    player_planets = (
        (planet(9, 0, 2.0, 0.0, player_planet_ships),)
        if player_planet_ships > 0
        else ()
    )
    return GameState(
        tick=7,
        player_id=0,
        planets=(
            planet(2, -1, 0.0, 0.0, 0),
            planet(3, 1, 3.0, 0.0, 5),
            planet(4, 1, 10.0, 0.0, 5),
            *player_planets,
        ),
        fleets=fleets,
        raw_observation={"step": 7, "player": 0},
    )


def pressure_response_facts() -> MissionResponseFacts:
    return MissionResponseFacts(
        target_reinforcement=TargetReinforcementFacts(
            source_facts=(
                ReinforcementSourceFacts(
                    planet_id=3,
                    owner=1,
                    ships=5,
                    distance_to_target=3.0,
                    travel_ticks=3,
                    arrives_by_window=True,
                ),
                ReinforcementSourceFacts(
                    planet_id=4,
                    owner=1,
                    ships=5,
                    distance_to_target=10.0,
                    travel_ticks=7,
                    arrives_by_window=False,
                ),
            ),
            feasible_source_count=1,
        ),
    )


def mission_candidate(target_planet_id: int = 2) -> MissionCandidate:
    return MissionCandidate(
        mission_type=MissionType.CAPTURE_NEUTRAL,
        target_planet_id=target_planet_id,
        source_planet_ids=(1,),
        outcome=CandidateOutcome.UNTESTED,
    )


def mission_evaluation(
    target_planet_id: int = 2,
    timing_facts: MissionTimingFacts | None = None,
) -> MissionEvaluation:
    candidate = mission_candidate(target_planet_id)
    if timing_facts is None:
        timing_facts = MissionTimingFacts(
            launch_arrival_ticks=(5,),
            min_arrival_ticks=5,
            max_arrival_ticks=5,
            timing_complete=True,
        )
    facts = MissionEvaluationFacts(
        mission_type=candidate.mission_type,
        target_planet_id=candidate.target_planet_id,
        source_planet_ids=candidate.source_planet_ids,
        launch_count=0,
        ships_spent=0,
        launch_angles=(),
        candidate_outcome=candidate.outcome,
        timing_facts=timing_facts,
    )
    return MissionEvaluation(
        candidate=candidate,
        status=MissionEvaluationStatus.EVALUATED,
        facts=facts,
    )


def source_mission_evaluation(
    *,
    source_planet_ids: tuple[int, ...] = (1,),
    source_before: int | None = 10,
    source_after: int | None = 4,
    include_delta: bool = True,
) -> MissionEvaluation:
    candidate = mission_candidate()
    candidate = MissionCandidate(
        mission_type=candidate.mission_type,
        target_planet_id=candidate.target_planet_id,
        source_planet_ids=source_planet_ids,
        outcome=candidate.outcome,
    )
    sources_before = (
        tuple(
            PlanetEvaluationFacts(
                planet_id=source_id,
                owner=0,
                ships=source_before,
                production=0,
            )
            for source_id in source_planet_ids
        )
        if source_before is not None
        else ()
    )
    sources_mission = (
        tuple(
            PlanetEvaluationFacts(
                planet_id=source_id,
                owner=0,
                ships=source_after,
                production=0,
            )
            for source_id in source_planet_ids
        )
        if source_after is not None
        else ()
    )
    source_delta = (
        source_after - source_before
        if source_before is not None and source_after is not None
        else None
    )
    future_delta = MissionFutureDeltaFacts(
        sources=(
            tuple(
                PlanetFutureDeltaFacts(
                    planet_id=source_id,
                    before_owner=0 if source_before is not None else None,
                    mission_owner=0 if source_after is not None else None,
                    before_ships=source_before,
                    mission_ships=source_after,
                    mission_ship_delta_vs_before=source_delta,
                )
                for source_id in source_planet_ids
            )
            if include_delta
            else ()
        ),
        total_source_ship_delta_vs_before=source_delta,
    )
    facts = MissionEvaluationFacts(
        mission_type=candidate.mission_type,
        target_planet_id=candidate.target_planet_id,
        source_planet_ids=candidate.source_planet_ids,
        launch_count=0,
        ships_spent=0,
        launch_angles=(),
        candidate_outcome=candidate.outcome,
        sources_before=sources_before,
        sources_mission=sources_mission,
        future_delta=future_delta,
        timing_facts=MissionTimingFacts(
            launch_arrival_ticks=(5,),
            min_arrival_ticks=5,
            max_arrival_ticks=5,
            timing_complete=True,
        ),
    )
    return MissionEvaluation(
        candidate=candidate,
        status=MissionEvaluationStatus.EVALUATED,
        facts=facts,
    )


def third_party_mission_evaluation(
    *,
    target_planet_id: int = 2,
    target_before_owner: int | None = 1,
    target_baseline_owner: int | None = 1,
    target_mission_owner: int | None = 0,
    include_target_before: bool = True,
    include_target_baseline: bool = True,
    include_target_mission: bool = True,
) -> MissionEvaluation:
    candidate = mission_candidate(target_planet_id)
    target_before = (
        PlanetEvaluationFacts(
            planet_id=target_planet_id,
            owner=target_before_owner,
            ships=5,
            production=5,
        )
        if include_target_before and target_before_owner is not None
        else None
    )
    target_baseline = (
        PlanetEvaluationFacts(
            planet_id=target_planet_id,
            owner=target_baseline_owner,
            ships=6,
            production=5,
        )
        if include_target_baseline and target_baseline_owner is not None
        else None
    )
    target_mission = (
        PlanetEvaluationFacts(
            planet_id=target_planet_id,
            owner=target_mission_owner,
            ships=3,
            production=5,
        )
        if include_target_mission and target_mission_owner is not None
        else None
    )
    facts = MissionEvaluationFacts(
        mission_type=candidate.mission_type,
        target_planet_id=candidate.target_planet_id,
        source_planet_ids=candidate.source_planet_ids,
        launch_count=0,
        ships_spent=0,
        launch_angles=(),
        candidate_outcome=candidate.outcome,
        target_before=target_before,
        target_baseline=target_baseline,
        target_mission=target_mission,
        timing_facts=MissionTimingFacts(
            launch_arrival_ticks=(5,),
            min_arrival_ticks=5,
            max_arrival_ticks=5,
            timing_complete=True,
        ),
    )
    return MissionEvaluation(
        candidate=candidate,
        status=MissionEvaluationStatus.EVALUATED,
        facts=facts,
    )


class PlannerResponseTests(unittest.TestCase):
    def test_response_module_imports_and_exports_are_available(self) -> None:
        importlib.import_module("ow_planner.response")

        self.assertIs(ResponseConfig, ResponseConfig)
        self.assertIs(ResponseEvaluationStatus, ResponseEvaluationStatus)
        self.assertIs(CounterattackSourceFacts, CounterattackSourceFacts)
        self.assertIs(MissionResponseFacts, MissionResponseFacts)
        self.assertIs(MissionResponseEvaluation, MissionResponseEvaluation)
        self.assertIs(RaceSourceFacts, RaceSourceFacts)
        self.assertIs(ReinforcementSourceFacts, ReinforcementSourceFacts)
        self.assertIs(RespondingSourcePressureFacts, RespondingSourcePressureFacts)
        self.assertIs(ResponseSummaryFacts, ResponseSummaryFacts)
        self.assertIs(ResponseSourcePressureFacts, ResponseSourcePressureFacts)
        self.assertIs(SourceCounterattackFacts, SourceCounterattackFacts)
        self.assertIs(TargetRaceFacts, TargetRaceFacts)
        self.assertIs(TargetReinforcementFacts, TargetReinforcementFacts)
        self.assertIs(ThirdPartyBenefitFacts, ThirdPartyBenefitFacts)
        self.assertIs(ThirdPartyOwnerFacts, ThirdPartyOwnerFacts)
        self.assertIsNotNone(evaluate_responses)
        self.assertIsNotNone(response_source_pressure_facts)
        self.assertIsNotNone(response_summary_facts)
        self.assertIsNotNone(source_counterattack_facts)
        self.assertIsNotNone(target_race_facts)
        self.assertIsNotNone(target_reinforcement_facts)
        self.assertIsNotNone(third_party_benefit_facts)

    def test_response_status_enum_values_are_stable(self) -> None:
        self.assertEqual(ResponseEvaluationStatus.UNEVALUATED.value, "unevaluated")
        self.assertEqual(ResponseEvaluationStatus.EVALUATED.value, "evaluated")
        self.assertEqual(ResponseEvaluationStatus.INCOMPLETE.value, "incomplete")

    def test_response_dataclasses_are_constructible_and_frozen(self) -> None:
        evaluation = mission_evaluation()
        config = ResponseConfig(response_window_ticks=3)
        facts = MissionResponseFacts(
            response_labels=("placeholder",),
            target_reinforcement=TargetReinforcementFacts(
                target_planet_id=2,
                arrival_window_ticks=5,
                timing_complete=True,
                source_facts=(
                    ReinforcementSourceFacts(
                        planet_id=3,
                        owner=1,
                        ships=4,
                        distance_to_target=3.0,
                        travel_ticks=2,
                        arrives_by_window=True,
                    ),
                ),
                feasible_source_count=1,
            ),
            target_race=TargetRaceFacts(
                target_planet_id=2,
                min_arrival_ticks=3,
                max_arrival_ticks=5,
                timing_complete=True,
                target_ships_before=1,
                source_facts=(
                    RaceSourceFacts(
                        planet_id=3,
                        owner=1,
                        ships=4,
                        distance_to_target=3.0,
                        travel_ticks=2,
                        can_arrive_before_earliest=True,
                        can_arrive_by_earliest=True,
                        can_arrive_by_latest=True,
                        target_ships_before=1,
                        source_has_more_ships_than_target_before=True,
                    ),
                ),
            ),
            source_counterattacks=(
                SourceCounterattackFacts(
                    source_planet_id=1,
                    source_owner_before=0,
                    source_ships_before=10,
                    source_ships_after_mission=4,
                    source_ship_delta_vs_before=-6,
                    ships_drained=6,
                    source_after_mission_is_depleted=False,
                    response_window_ticks=3,
                    counterattack_sources=(
                        CounterattackSourceFacts(
                            planet_id=3,
                            owner=1,
                            ships=6,
                            distance_to_source=3.0,
                            travel_ticks=3,
                            arrives_by_response_window=True,
                            source_ships_after_mission=4,
                            source_has_more_ships_than_source_after_mission=True,
                        ),
                    ),
                ),
            ),
            third_party_benefit=ThirdPartyBenefitFacts(
                player_id=0,
                target_planet_id=2,
                target_owner_before=1,
                target_owner_baseline=1,
                target_owner_mission=0,
                target_production_before=5,
                target_owner_is_non_player=True,
                target_owner_damaged_by_mission=True,
                target_owner_loses_control_by_mission=True,
                third_party_owner_facts=(
                    ThirdPartyOwnerFacts(
                        owner=2,
                        current_planet_count=1,
                        current_production=3,
                        current_ships=4,
                        unaffected_by_target_ownership_change=True,
                    ),
                ),
                unaffected_non_player_owner_count=1,
            ),
            source_pressure=ResponseSourcePressureFacts(
                source_facts=(
                    RespondingSourcePressureFacts(
                        source_planet_id=3,
                        owner=1,
                        ships=5,
                        response_window_ticks=3,
                        inbound_player_fleet_count=1,
                        inbound_player_fleet_ships=5,
                        spare_ships_after_inbound_pressure=0,
                        pinned_by_inbound_fleets=True,
                        threatened_by_inbound_fleets=True,
                        pinned=True,
                        threatened=True,
                        free_to_respond=False,
                    ),
                ),
                pinned_source_count=1,
                threatened_source_count=1,
            ),
            response_summary=ResponseSummaryFacts(
                labels=("target_reinforcement_feasible",),
                target_reinforcement_feasible=True,
                reinforcement_feasible_source_count=1,
            ),
            notes=("structural",),
        )
        response = MissionResponseEvaluation(
            evaluation=evaluation,
            status=ResponseEvaluationStatus.EVALUATED,
            facts=facts,
            note="ok",
        )

        self.assertEqual(config.response_window_ticks, 3)
        self.assertEqual(facts.response_labels, ("placeholder",))
        self.assertEqual(facts.target_reinforcement.feasible_source_count, 1)
        self.assertEqual(facts.target_race.target_ships_before, 1)
        self.assertEqual(facts.source_counterattacks[0].ships_drained, 6)
        self.assertEqual(facts.third_party_benefit.unaffected_non_player_owner_count, 1)
        self.assertEqual(facts.source_pressure.pinned_source_count, 1)
        self.assertEqual(facts.response_summary.labels, ("target_reinforcement_feasible",))
        self.assertIs(response.evaluation, evaluation)
        with self.assertRaises(FrozenInstanceError):
            config.response_window_ticks = 1
        with self.assertRaises(FrozenInstanceError):
            facts.notes = ()
        with self.assertRaises(FrozenInstanceError):
            facts.target_reinforcement.feasible_source_count = 2
        with self.assertRaises(FrozenInstanceError):
            facts.target_race.target_ships_before = 2
        with self.assertRaises(FrozenInstanceError):
            facts.source_counterattacks[0].ships_drained = 7
        with self.assertRaises(FrozenInstanceError):
            facts.third_party_benefit.unaffected_non_player_owner_count = 2
        with self.assertRaises(FrozenInstanceError):
            facts.source_pressure.pinned_source_count = 2
        with self.assertRaises(FrozenInstanceError):
            facts.response_summary.labels = ()
        with self.assertRaises(FrozenInstanceError):
            response.note = None

    def test_response_config_rejects_invalid_window_ticks(self) -> None:
        for response_window_ticks in (-1, True, 1.5, "3", None):
            with self.subTest(response_window_ticks=response_window_ticks):
                with self.assertRaises(ValueError):
                    ResponseConfig(response_window_ticks=response_window_ticks)

    def test_evaluate_responses_returns_empty_tuple_for_empty_input(self) -> None:
        self.assertEqual(evaluate_responses(response_state(), ()), ())

    def test_evaluate_responses_preserves_order_and_wraps_original_evaluations(self) -> None:
        first = mission_evaluation(2)
        second = mission_evaluation(3)

        responses = evaluate_responses(reinforcement_state(), (first, second))

        self.assertEqual(
            tuple(response.evaluation for response in responses),
            (first, second),
        )
        self.assertIs(responses[0].evaluation, first)
        self.assertIs(responses[1].evaluation, second)
        self.assertEqual(
            tuple(response.status for response in responses),
            (
                ResponseEvaluationStatus.EVALUATED,
                ResponseEvaluationStatus.EVALUATED,
            ),
        )
        self.assertEqual(tuple(response.note for response in responses), (None, None))
        self.assertEqual(responses[0].facts.target_reinforcement.target_planet_id, 2)
        self.assertEqual(responses[1].facts.target_reinforcement.target_planet_id, 3)
        self.assertEqual(responses[0].facts.target_race.target_planet_id, 2)
        self.assertEqual(responses[1].facts.target_race.target_planet_id, 3)

    def test_evaluate_responses_marks_missing_facts_incomplete(self) -> None:
        evaluation = MissionEvaluation(candidate=mission_candidate(), facts=None)

        (response,) = evaluate_responses(response_state(), (evaluation,))

        self.assertIs(response.evaluation, evaluation)
        self.assertEqual(response.status, ResponseEvaluationStatus.INCOMPLETE)
        self.assertEqual(
            response.facts,
            MissionResponseFacts(notes=("mission facts are missing",)),
        )
        self.assertEqual(response.note, "mission facts are missing")

    def test_target_reinforcement_facts_identify_candidate_enemy_sources(self) -> None:
        facts = target_reinforcement_facts(
            reinforcement_state(),
            mission_evaluation(),
        )

        self.assertEqual(facts.target_planet_id, 2)
        self.assertEqual(facts.arrival_window_ticks, 5)
        self.assertIs(facts.timing_complete, True)
        self.assertEqual(
            facts.source_facts,
            (
                ReinforcementSourceFacts(
                    planet_id=3,
                    owner=1,
                    ships=1,
                    distance_to_target=3.0,
                    travel_ticks=3,
                    arrives_by_window=True,
                ),
                ReinforcementSourceFacts(
                    planet_id=4,
                    owner=1,
                    ships=1,
                    distance_to_target=10.0,
                    travel_ticks=10,
                    arrives_by_window=False,
                ),
            ),
        )
        self.assertEqual(facts.feasible_source_count, 1)
        self.assertEqual(facts.notes, ())

    def test_response_window_extends_reinforcement_feasibility(self) -> None:
        facts = target_reinforcement_facts(
            reinforcement_state(),
            mission_evaluation(),
            ResponseConfig(response_window_ticks=5),
        )

        self.assertEqual(facts.arrival_window_ticks, 10)
        self.assertEqual(
            tuple(source.arrives_by_window for source in facts.source_facts),
            (True, True),
        )
        self.assertEqual(facts.feasible_source_count, 2)

    def test_target_race_facts_identify_candidate_enemy_sources(self) -> None:
        facts = target_race_facts(
            reinforcement_state(),
            mission_evaluation(),
        )

        self.assertEqual(facts.target_planet_id, 2)
        self.assertEqual(facts.min_arrival_ticks, 5)
        self.assertEqual(facts.max_arrival_ticks, 5)
        self.assertIs(facts.timing_complete, True)
        self.assertEqual(facts.target_ships_before, 0)
        self.assertEqual(
            facts.source_facts,
            (
                RaceSourceFacts(
                    planet_id=3,
                    owner=1,
                    ships=1,
                    distance_to_target=3.0,
                    travel_ticks=3,
                    can_arrive_before_earliest=True,
                    can_arrive_by_earliest=True,
                    can_arrive_by_latest=True,
                    target_ships_before=0,
                    source_has_more_ships_than_target_before=True,
                ),
                RaceSourceFacts(
                    planet_id=4,
                    owner=1,
                    ships=1,
                    distance_to_target=10.0,
                    travel_ticks=10,
                    can_arrive_before_earliest=False,
                    can_arrive_by_earliest=False,
                    can_arrive_by_latest=False,
                    target_ships_before=0,
                    source_has_more_ships_than_target_before=True,
                ),
            ),
        )
        self.assertEqual(facts.notes, ())

    def test_target_race_facts_expose_by_latest_arrival_flags(self) -> None:
        evaluation = mission_evaluation(
            timing_facts=MissionTimingFacts(
                launch_arrival_ticks=(5, 10),
                min_arrival_ticks=5,
                max_arrival_ticks=10,
                timing_complete=True,
            )
        )

        facts = target_race_facts(reinforcement_state(), evaluation)

        self.assertEqual(
            tuple(source.can_arrive_before_earliest for source in facts.source_facts),
            (True, False),
        )
        self.assertEqual(
            tuple(source.can_arrive_by_earliest for source in facts.source_facts),
            (True, False),
        )
        self.assertEqual(
            tuple(source.can_arrive_by_latest for source in facts.source_facts),
            (True, True),
        )

    def test_evaluate_responses_attaches_race_facts(self) -> None:
        (response,) = evaluate_responses(
            reinforcement_state(),
            (mission_evaluation(),),
        )

        self.assertEqual(response.status, ResponseEvaluationStatus.EVALUATED)
        self.assertEqual(response.facts.target_race.target_planet_id, 2)
        self.assertEqual(
            tuple(source.planet_id for source in response.facts.target_race.source_facts),
            (3, 4),
        )

    def test_evaluate_responses_attaches_reinforcement_facts(self) -> None:
        (response,) = evaluate_responses(
            reinforcement_state(),
            (mission_evaluation(),),
        )

        self.assertEqual(response.status, ResponseEvaluationStatus.EVALUATED)
        self.assertEqual(
            response.facts.response_labels,
            ("target_reinforcement_feasible", "target_race_risk"),
        )
        self.assertEqual(response.facts.target_reinforcement.feasible_source_count, 1)
        self.assertEqual(
            tuple(source.planet_id for source in response.facts.target_reinforcement.source_facts),
            (3, 4),
        )

    def test_reinforcement_excludes_target_neutral_player_comet_and_zero_ship_planets(self) -> None:
        facts = target_reinforcement_facts(
            reinforcement_state(),
            mission_evaluation(),
        )

        self.assertEqual(
            tuple(source.planet_id for source in facts.source_facts),
            (3, 4),
        )

    def test_race_excludes_target_neutral_player_comet_and_zero_ship_planets(self) -> None:
        facts = target_race_facts(
            reinforcement_state(),
            mission_evaluation(),
        )

        self.assertEqual(
            tuple(source.planet_id for source in facts.source_facts),
            (3, 4),
        )

    def test_source_counterattack_facts_include_source_before_after_and_drain(self) -> None:
        facts = source_counterattack_facts(
            counterattack_state(),
            source_mission_evaluation(),
            ResponseConfig(response_window_ticks=3),
        )

        self.assertEqual(len(facts), 1)
        source_facts = facts[0]
        self.assertEqual(source_facts.source_planet_id, 1)
        self.assertEqual(source_facts.source_owner_before, 0)
        self.assertEqual(source_facts.source_ships_before, 10)
        self.assertEqual(source_facts.source_ships_after_mission, 4)
        self.assertEqual(source_facts.source_ship_delta_vs_before, -6)
        self.assertEqual(source_facts.ships_drained, 6)
        self.assertIs(source_facts.source_after_mission_is_depleted, False)
        self.assertEqual(source_facts.response_window_ticks, 3)
        self.assertEqual(source_facts.notes, ())

    def test_source_counterattack_facts_identify_candidate_enemy_sources(self) -> None:
        facts = source_counterattack_facts(
            counterattack_state(),
            source_mission_evaluation(),
            ResponseConfig(response_window_ticks=3),
        )

        self.assertEqual(
            facts[0].counterattack_sources,
            (
                CounterattackSourceFacts(
                    planet_id=3,
                    owner=1,
                    ships=6,
                    distance_to_source=3.0,
                    travel_ticks=2,
                    arrives_by_response_window=True,
                    source_ships_after_mission=4,
                    source_has_more_ships_than_source_after_mission=True,
                ),
                CounterattackSourceFacts(
                    planet_id=4,
                    owner=2,
                    ships=4,
                    distance_to_source=10.0,
                    travel_ticks=7,
                    arrives_by_response_window=False,
                    source_ships_after_mission=4,
                    source_has_more_ships_than_source_after_mission=False,
                ),
            ),
        )

    def test_source_counterattack_zero_window_reports_travel_without_arrival(self) -> None:
        facts = source_counterattack_facts(
            counterattack_state(),
            source_mission_evaluation(),
        )

        self.assertEqual(facts[0].response_window_ticks, 0)
        self.assertEqual(
            tuple(source.travel_ticks for source in facts[0].counterattack_sources),
            (2, 7),
        )
        self.assertEqual(
            tuple(
                source.arrives_by_response_window
                for source in facts[0].counterattack_sources
            ),
            (False, False),
        )

    def test_source_counterattack_facts_expose_depleted_source_context(self) -> None:
        facts = source_counterattack_facts(
            counterattack_state(),
            source_mission_evaluation(source_after=0),
            ResponseConfig(response_window_ticks=3),
        )

        self.assertIs(facts[0].source_after_mission_is_depleted, True)
        self.assertEqual(facts[0].source_ships_after_mission, 0)
        self.assertEqual(
            tuple(
                source.source_has_more_ships_than_source_after_mission
                for source in facts[0].counterattack_sources
            ),
            (True, True),
        )

    def test_source_counterattack_excludes_self_neutral_player_comet_and_zero_ship_planets(self) -> None:
        facts = source_counterattack_facts(
            counterattack_state(),
            source_mission_evaluation(),
        )

        self.assertEqual(
            tuple(source.planet_id for source in facts[0].counterattack_sources),
            (3, 4),
        )

    def test_evaluate_responses_attaches_source_counterattack_facts(self) -> None:
        (response,) = evaluate_responses(
            counterattack_state(),
            (source_mission_evaluation(),),
            ResponseConfig(response_window_ticks=3),
        )

        self.assertEqual(response.status, ResponseEvaluationStatus.EVALUATED)
        self.assertEqual(len(response.facts.source_counterattacks), 1)
        self.assertEqual(
            tuple(
                source.planet_id
                for source in response.facts.source_counterattacks[
                    0
                ].counterattack_sources
            ),
            (3, 4),
        )

    def test_source_counterattack_facts_return_empty_for_missing_mission_facts(self) -> None:
        evaluation = MissionEvaluation(candidate=mission_candidate(), facts=None)

        self.assertEqual(
            source_counterattack_facts(counterattack_state(), evaluation),
            (),
        )

    def test_source_counterattack_facts_note_missing_source_before_facts(self) -> None:
        facts = source_counterattack_facts(
            counterattack_state(),
            source_mission_evaluation(source_before=None),
        )

        self.assertIsNone(facts[0].source_owner_before)
        self.assertIsNone(facts[0].source_ships_before)
        self.assertIn("source before facts are missing", facts[0].notes)

    def test_source_counterattack_facts_note_missing_source_after_facts(self) -> None:
        facts = source_counterattack_facts(
            counterattack_state(),
            source_mission_evaluation(source_after=None),
        )

        self.assertIsNone(facts[0].source_ships_after_mission)
        self.assertIsNone(facts[0].source_after_mission_is_depleted)
        self.assertIn("source mission facts are missing", facts[0].notes)
        self.assertEqual(
            tuple(
                source.source_has_more_ships_than_source_after_mission
                for source in facts[0].counterattack_sources
            ),
            (None, None),
        )

    def test_source_counterattack_facts_note_missing_source_delta_facts(self) -> None:
        facts = source_counterattack_facts(
            counterattack_state(),
            source_mission_evaluation(include_delta=False),
        )

        self.assertIsNone(facts[0].source_ship_delta_vs_before)
        self.assertIsNone(facts[0].ships_drained)
        self.assertIn("source delta facts are missing", facts[0].notes)

    def test_source_counterattack_facts_note_when_no_candidate_sources_exist(self) -> None:
        facts = source_counterattack_facts(
            no_counterattack_state(),
            source_mission_evaluation(),
        )

        self.assertEqual(facts[0].counterattack_sources, ())
        self.assertEqual(facts[0].notes, ("no candidate counterattack sources",))

    def test_source_counterattack_facts_note_missing_source_planet(self) -> None:
        facts = source_counterattack_facts(
            counterattack_state(),
            source_mission_evaluation(source_planet_ids=(99,)),
        )

        self.assertEqual(facts[0].source_planet_id, 99)
        self.assertEqual(facts[0].counterattack_sources, ())
        self.assertIn("source planet is missing", facts[0].notes)

    def test_third_party_owner_summary_construction(self) -> None:
        facts = third_party_benefit_facts(
            ffa_state(),
            third_party_mission_evaluation(),
        )

        self.assertEqual(facts.player_id, 0)
        self.assertEqual(facts.target_planet_id, 2)
        self.assertEqual(facts.target_owner_before, 1)
        self.assertEqual(facts.target_owner_baseline, 1)
        self.assertEqual(facts.target_owner_mission, 0)
        self.assertEqual(facts.target_production_before, 5)
        self.assertEqual(
            facts.third_party_owner_facts,
            (
                ThirdPartyOwnerFacts(
                    owner=2,
                    current_planet_count=2,
                    current_production=5,
                    current_ships=11,
                    unaffected_by_target_ownership_change=True,
                ),
                ThirdPartyOwnerFacts(
                    owner=3,
                    current_planet_count=1,
                    current_production=4,
                    current_ships=8,
                    unaffected_by_target_ownership_change=True,
                ),
            ),
        )
        self.assertEqual(facts.unaffected_non_player_owner_count, 2)
        self.assertEqual(facts.notes, ())

    def test_third_party_benefit_facts_identify_ffa_unaffected_owners(self) -> None:
        facts = third_party_benefit_facts(
            ffa_state(),
            third_party_mission_evaluation(),
        )

        self.assertEqual(
            tuple(owner.owner for owner in facts.third_party_owner_facts),
            (2, 3),
        )
        self.assertEqual(
            tuple(
                owner.unaffected_by_target_ownership_change
                for owner in facts.third_party_owner_facts
            ),
            (True, True),
        )

    def test_third_party_benefit_facts_note_two_player_case(self) -> None:
        facts = third_party_benefit_facts(
            two_player_state(),
            third_party_mission_evaluation(),
        )

        self.assertEqual(facts.third_party_owner_facts, ())
        self.assertEqual(facts.unaffected_non_player_owner_count, 0)
        self.assertEqual(facts.notes, ("no third-party owners",))

    def test_third_party_benefit_facts_identify_target_owner_damage(self) -> None:
        facts = third_party_benefit_facts(
            ffa_state(),
            third_party_mission_evaluation(),
        )

        self.assertIs(facts.target_owner_is_non_player, True)
        self.assertIs(facts.target_owner_damaged_by_mission, True)

    def test_third_party_benefit_facts_identify_target_owner_control_loss(self) -> None:
        facts = third_party_benefit_facts(
            ffa_state(),
            third_party_mission_evaluation(),
        )

        self.assertIs(facts.target_owner_loses_control_by_mission, True)

    def test_evaluate_responses_attaches_third_party_benefit_facts(self) -> None:
        (response,) = evaluate_responses(
            ffa_state(),
            (third_party_mission_evaluation(),),
        )

        self.assertEqual(response.status, ResponseEvaluationStatus.EVALUATED)
        self.assertEqual(response.facts.third_party_benefit.target_planet_id, 2)
        self.assertEqual(
            tuple(
                owner.owner
                for owner in response.facts.third_party_benefit.third_party_owner_facts
            ),
            (2, 3),
        )

    def test_third_party_benefit_facts_handle_missing_mission_facts(self) -> None:
        evaluation = MissionEvaluation(candidate=mission_candidate(), facts=None)

        facts = third_party_benefit_facts(ffa_state(), evaluation)

        self.assertIsNone(facts.target_planet_id)
        self.assertEqual(facts.notes, ("mission facts are missing",))

    def test_third_party_benefit_facts_note_missing_player_id(self) -> None:
        state = GameState(
            tick=7,
            player_id=None,
            planets=ffa_state().planets,
            raw_observation={"step": 7},
        )

        facts = third_party_benefit_facts(
            state,
            third_party_mission_evaluation(),
        )

        self.assertIsNone(facts.player_id)
        self.assertEqual(facts.third_party_owner_facts, ())
        self.assertIn("player id is missing", facts.notes)

    def test_third_party_benefit_facts_note_missing_target_before(self) -> None:
        facts = third_party_benefit_facts(
            ffa_state(),
            third_party_mission_evaluation(include_target_before=False),
        )

        self.assertIsNone(facts.target_owner_before)
        self.assertIsNone(facts.target_owner_is_non_player)
        self.assertIn("target before facts are missing", facts.notes)

    def test_third_party_benefit_facts_note_missing_target_baseline(self) -> None:
        facts = third_party_benefit_facts(
            ffa_state(),
            third_party_mission_evaluation(include_target_baseline=False),
        )

        self.assertIsNone(facts.target_owner_baseline)
        self.assertIsNone(facts.target_owner_damaged_by_mission)
        self.assertIn("target baseline facts are missing", facts.notes)

    def test_third_party_benefit_facts_note_missing_target_mission(self) -> None:
        facts = third_party_benefit_facts(
            ffa_state(),
            third_party_mission_evaluation(include_target_mission=False),
        )

        self.assertIsNone(facts.target_owner_mission)
        self.assertIsNone(facts.target_owner_loses_control_by_mission)
        self.assertIn("target mission facts are missing", facts.notes)

    def test_response_summary_empty_default_has_no_labels(self) -> None:
        summary = response_summary_facts(MissionResponseFacts())

        self.assertEqual(summary, ResponseSummaryFacts())
        self.assertEqual(summary.labels, ())

    def test_response_summary_labels_reinforcement_feasible(self) -> None:
        summary = response_summary_facts(
            MissionResponseFacts(
                target_reinforcement=TargetReinforcementFacts(
                    feasible_source_count=2,
                ),
            )
        )

        self.assertEqual(summary.labels, ("target_reinforcement_feasible",))
        self.assertIs(summary.target_reinforcement_feasible, True)
        self.assertEqual(summary.reinforcement_feasible_source_count, 2)

    def test_response_summary_labels_target_race_risk(self) -> None:
        summary = response_summary_facts(
            MissionResponseFacts(
                target_race=TargetRaceFacts(
                    source_facts=(
                        RaceSourceFacts(
                            planet_id=3,
                            owner=1,
                            ships=4,
                            distance_to_target=3.0,
                            travel_ticks=2,
                            can_arrive_before_earliest=True,
                            can_arrive_by_earliest=True,
                            can_arrive_by_latest=True,
                            target_ships_before=1,
                            source_has_more_ships_than_target_before=True,
                        ),
                        RaceSourceFacts(
                            planet_id=4,
                            owner=2,
                            ships=4,
                            distance_to_target=10.0,
                            travel_ticks=7,
                            can_arrive_before_earliest=False,
                            can_arrive_by_earliest=False,
                            can_arrive_by_latest=True,
                            target_ships_before=1,
                            source_has_more_ships_than_target_before=True,
                        ),
                    ),
                ),
            )
        )

        self.assertEqual(summary.labels, ("target_race_risk",))
        self.assertIs(summary.target_race_risk, True)
        self.assertEqual(summary.race_by_earliest_source_count, 1)

    def test_response_summary_labels_source_counterattack_risk(self) -> None:
        summary = response_summary_facts(
            MissionResponseFacts(
                source_counterattacks=source_counterattack_facts(
                    counterattack_state(),
                    source_mission_evaluation(),
                    ResponseConfig(response_window_ticks=3),
                ),
            )
        )

        self.assertEqual(summary.labels, ("source_counterattack_risk",))
        self.assertIs(summary.source_counterattack_risk, True)
        self.assertEqual(summary.counterattack_arrives_by_window_count, 1)

    def test_response_summary_labels_third_party_benefit_possible(self) -> None:
        summary = response_summary_facts(
            MissionResponseFacts(
                third_party_benefit=third_party_benefit_facts(
                    ffa_state(),
                    third_party_mission_evaluation(),
                ),
            )
        )

        self.assertEqual(summary.labels, ("third_party_benefit_possible",))
        self.assertIs(summary.third_party_benefit_possible, True)
        self.assertEqual(summary.third_party_owner_count, 2)

    def test_response_summary_labels_have_stable_order(self) -> None:
        summary = response_summary_facts(
            MissionResponseFacts(
                target_reinforcement=TargetReinforcementFacts(
                    feasible_source_count=1,
                ),
                target_race=TargetRaceFacts(
                    source_facts=(
                        RaceSourceFacts(
                            planet_id=3,
                            owner=1,
                            ships=4,
                            distance_to_target=3.0,
                            travel_ticks=2,
                            can_arrive_before_earliest=True,
                            can_arrive_by_earliest=True,
                            can_arrive_by_latest=True,
                            target_ships_before=1,
                            source_has_more_ships_than_target_before=True,
                        ),
                    ),
                ),
                source_counterattacks=source_counterattack_facts(
                    counterattack_state(),
                    source_mission_evaluation(),
                    ResponseConfig(response_window_ticks=3),
                ),
                third_party_benefit=third_party_benefit_facts(
                    ffa_state(),
                    third_party_mission_evaluation(),
                ),
            )
        )

        self.assertEqual(
            summary.labels,
            (
                "target_reinforcement_feasible",
                "target_race_risk",
                "source_counterattack_risk",
                "third_party_benefit_possible",
            ),
        )

    def test_evaluate_responses_attaches_response_summary_labels(self) -> None:
        (response,) = evaluate_responses(
            ffa_state(),
            (third_party_mission_evaluation(),),
        )

        self.assertEqual(
            response.facts.response_labels,
            response.facts.response_summary.labels,
        )
        self.assertIn("third_party_benefit_possible", response.facts.response_labels)
        self.assertIs(response.facts.response_summary.third_party_benefit_possible, True)

    def test_response_source_pressure_facts_empty_has_no_sources(self) -> None:
        pressure = response_source_pressure_facts(response_state(), MissionResponseFacts())

        self.assertEqual(
            pressure,
            ResponseSourcePressureFacts(notes=("no responding sources",)),
        )

    def test_response_source_pressure_facts_no_threat_marks_sources_free(self) -> None:
        pressure = response_source_pressure_facts(
            pressure_state(),
            pressure_response_facts(),
            ResponseConfig(response_window_ticks=3),
        )

        self.assertEqual(pressure.pinned_source_count, 0)
        self.assertEqual(pressure.threatened_source_count, 0)
        self.assertEqual(pressure.free_source_count, 2)
        self.assertEqual(
            tuple(source.free_to_respond for source in pressure.source_facts),
            (True, True),
        )
        self.assertEqual(
            tuple(source.notes for source in pressure.source_facts),
            (("no player pressure detected",), ("no player pressure detected",)),
        )

    def test_response_source_pressure_facts_inbound_fleet_marks_source_pinned(self) -> None:
        pressure = response_source_pressure_facts(
            pressure_state(fleets=(fleet(1, 0, 2.0, 0.0, 0.0, 5),)),
            pressure_response_facts(),
            ResponseConfig(response_window_ticks=1),
        )

        source = pressure.source_facts[0]
        self.assertEqual(source.source_planet_id, 3)
        self.assertEqual(source.inbound_player_fleet_count, 1)
        self.assertEqual(source.inbound_player_fleet_ships, 5)
        self.assertEqual(source.spare_ships_after_inbound_pressure, 0)
        self.assertIs(source.threatened_by_inbound_fleets, True)
        self.assertIs(source.pinned_by_inbound_fleets, True)
        self.assertIs(source.threatened, True)
        self.assertIs(source.pinned, True)
        self.assertIs(source.free_to_respond, False)
        self.assertEqual(pressure.pinned_source_count, 1)

    def test_response_source_pressure_facts_nearby_player_planet_marks_source_pinned(self) -> None:
        pressure = response_source_pressure_facts(
            pressure_state(player_planet_ships=6),
            pressure_response_facts(),
            ResponseConfig(response_window_ticks=1),
        )

        source = pressure.source_facts[0]
        self.assertEqual(source.nearby_player_planet_count, 1)
        self.assertEqual(source.nearby_player_planet_ships, 6)
        self.assertIs(source.threatened_by_nearby_player_planets, True)
        self.assertIs(source.pinned_by_nearby_player_planets, True)
        self.assertIs(source.pinned, True)
        self.assertIs(source.threatened, True)

    def test_evaluate_responses_attaches_source_pressure_facts(self) -> None:
        (response,) = evaluate_responses(
            pressure_state(fleets=(fleet(1, 0, 2.0, 0.0, 0.0, 5),)),
            (mission_evaluation(),),
            ResponseConfig(response_window_ticks=1),
        )

        self.assertEqual(response.status, ResponseEvaluationStatus.EVALUATED)
        self.assertEqual(response.facts.source_pressure.pinned_source_count, 1)
        self.assertEqual(response.facts.source_pressure.threatened_source_count, 1)
        self.assertEqual(
            tuple(
                source.source_planet_id
                for source in response.facts.source_pressure.source_facts
            ),
            (3, 4),
        )

    def test_response_source_pressure_does_not_change_summary_labels(self) -> None:
        pressure = response_source_pressure_facts(
            pressure_state(fleets=(fleet(1, 0, 2.0, 0.0, 0.0, 5),)),
            pressure_response_facts(),
            ResponseConfig(response_window_ticks=1),
        )
        facts = MissionResponseFacts(
            target_reinforcement=TargetReinforcementFacts(
                feasible_source_count=1,
            ),
            source_pressure=pressure,
        )

        self.assertEqual(
            response_summary_facts(facts).labels,
            ("target_reinforcement_feasible",),
        )

    def test_reinforcement_facts_are_unavailable_when_timing_is_incomplete(self) -> None:
        evaluation = mission_evaluation(
            timing_facts=MissionTimingFacts(
                launch_arrival_ticks=(None,),
                timing_complete=False,
            )
        )

        facts = target_reinforcement_facts(reinforcement_state(), evaluation)

        self.assertEqual(facts.target_planet_id, 2)
        self.assertIsNone(facts.arrival_window_ticks)
        self.assertIs(facts.timing_complete, False)
        self.assertEqual(facts.source_facts, ())
        self.assertEqual(facts.feasible_source_count, 0)
        self.assertEqual(facts.notes, ("mission arrival timing is incomplete",))

    def test_race_facts_are_unavailable_when_timing_is_incomplete(self) -> None:
        evaluation = mission_evaluation(
            timing_facts=MissionTimingFacts(
                launch_arrival_ticks=(None,),
                timing_complete=False,
            )
        )

        facts = target_race_facts(reinforcement_state(), evaluation)

        self.assertEqual(facts.target_planet_id, 2)
        self.assertIsNone(facts.min_arrival_ticks)
        self.assertIsNone(facts.max_arrival_ticks)
        self.assertIs(facts.timing_complete, False)
        self.assertEqual(facts.source_facts, ())
        self.assertEqual(facts.notes, ("mission arrival timing is incomplete",))

    def test_reinforcement_facts_are_unavailable_when_target_is_missing(self) -> None:
        evaluation = mission_evaluation(target_planet_id=99)

        facts = target_reinforcement_facts(reinforcement_state(), evaluation)

        self.assertEqual(facts.target_planet_id, 99)
        self.assertEqual(facts.arrival_window_ticks, 5)
        self.assertIs(facts.timing_complete, True)
        self.assertEqual(facts.source_facts, ())
        self.assertEqual(facts.feasible_source_count, 0)
        self.assertEqual(facts.notes, ("target planet is missing",))

    def test_race_facts_are_unavailable_when_target_id_is_missing(self) -> None:
        evaluation = MissionEvaluation(
            candidate=mission_candidate(target_planet_id=None),
            status=MissionEvaluationStatus.EVALUATED,
            facts=MissionEvaluationFacts(
                mission_type=MissionType.REINFORCE,
                target_planet_id=None,
                source_planet_ids=(1,),
                launch_count=0,
                ships_spent=0,
                launch_angles=(),
                candidate_outcome=CandidateOutcome.UNTESTED,
                timing_facts=MissionTimingFacts(
                    launch_arrival_ticks=(5,),
                    min_arrival_ticks=5,
                    max_arrival_ticks=5,
                    timing_complete=True,
                ),
            ),
        )

        facts = target_race_facts(reinforcement_state(), evaluation)

        self.assertIsNone(facts.target_planet_id)
        self.assertEqual(facts.source_facts, ())
        self.assertEqual(facts.notes, ("target planet id is missing",))

    def test_race_facts_are_unavailable_when_target_planet_is_missing(self) -> None:
        evaluation = mission_evaluation(target_planet_id=99)

        facts = target_race_facts(reinforcement_state(), evaluation)

        self.assertEqual(facts.target_planet_id, 99)
        self.assertEqual(facts.min_arrival_ticks, 5)
        self.assertEqual(facts.max_arrival_ticks, 5)
        self.assertIs(facts.timing_complete, True)
        self.assertEqual(facts.source_facts, ())
        self.assertEqual(facts.notes, ("target planet is missing",))

    def test_reinforcement_facts_note_when_no_candidate_sources_exist(self) -> None:
        facts = target_reinforcement_facts(
            no_reinforcement_state(),
            mission_evaluation(),
        )

        self.assertEqual(facts.source_facts, ())
        self.assertEqual(facts.feasible_source_count, 0)
        self.assertEqual(facts.notes, ("no candidate reinforcing planets",))

    def test_race_facts_note_when_no_candidate_sources_exist(self) -> None:
        facts = target_race_facts(
            no_reinforcement_state(),
            mission_evaluation(),
        )

        self.assertEqual(facts.source_facts, ())
        self.assertEqual(facts.notes, ("no candidate race sources",))

    def test_evaluate_responses_does_not_mutate_state_or_evaluations(self) -> None:
        state = response_state()
        evaluation = mission_evaluation()
        state_before = copy.deepcopy(state)
        evaluation_before = copy.deepcopy(evaluation)

        evaluate_responses(
            state,
            (evaluation,),
            config=ResponseConfig(response_window_ticks=5),
        )

        self.assertEqual(state, state_before)
        self.assertEqual(evaluation, evaluation_before)

    def test_evaluate_responses_does_not_call_deferred_logic(self) -> None:
        with (
            patch("ow_planner.candidates.generate_candidates") as generate,
            patch("ow_sim.timeline.simulate_ticks") as simulate_ticks,
            patch("ow_sim.whatif.simulate_launch_orders") as simulate_launch_orders,
        ):
            evaluate_responses(response_state(), (mission_evaluation(),))

        generate.assert_not_called()
        simulate_ticks.assert_not_called()
        simulate_launch_orders.assert_not_called()

    def test_response_boundary_adds_no_ranking_or_selection_fields(self) -> None:
        (response,) = evaluate_responses(response_state(), (mission_evaluation(),))

        self.assertFalse(hasattr(response, "rank"))
        self.assertFalse(hasattr(response, "selected"))
        self.assertFalse(hasattr(response, "score_components"))
        self.assertFalse(hasattr(response, "total_score"))


if __name__ == "__main__":
    unittest.main()
