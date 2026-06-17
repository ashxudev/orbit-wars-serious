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
    ResponseConfig,
    ResponseEvaluationStatus,
    SourceCounterattackFacts,
    TargetRaceFacts,
    TargetReinforcementFacts,
    evaluate_responses,
    source_counterattack_facts,
    target_race_facts,
    target_reinforcement_facts,
)
from ow_sim.state import GameState, Planet


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
    is_comet: bool = False,
) -> Planet:
    return Planet(
        planet_id=planet_id,
        owner=owner,
        x=x,
        y=y,
        radius=1.0,
        ships=ships,
        production=0,
        is_comet=is_comet,
        raw=(planet_id, owner, x, y, 1.0, ships, 0),
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
        self.assertIs(SourceCounterattackFacts, SourceCounterattackFacts)
        self.assertIs(TargetRaceFacts, TargetRaceFacts)
        self.assertIs(TargetReinforcementFacts, TargetReinforcementFacts)
        self.assertIsNotNone(evaluate_responses)
        self.assertIsNotNone(source_counterattack_facts)
        self.assertIsNotNone(target_race_facts)
        self.assertIsNotNone(target_reinforcement_facts)

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
        self.assertEqual(response.facts.response_labels, ())
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
