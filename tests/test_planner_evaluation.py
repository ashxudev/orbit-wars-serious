"""Tests for Mission Evaluation Cycle 0 contracts."""

from __future__ import annotations

import copy
import importlib
import unittest
from dataclasses import FrozenInstanceError
from unittest.mock import patch

from ow_planner import (
    CandidateOutcome,
    EvaluationConfig,
    LaunchCandidate,
    MissionCandidate,
    MissionEvaluation,
    MissionEvaluationFacts,
    MissionEvaluationStatus,
    MissionFutureDeltaFacts,
    MissionScoringConfig,
    MissionTimingFacts,
    MissionValueFacts,
    MissionType,
    PlanetEvaluationFacts,
    PlanetFutureDeltaFacts,
    ScoreComponent,
    baseline_state_after_horizon,
    candidate_state_after_horizon,
    evaluate_and_score_candidates,
    evaluate_candidates,
    extract_candidate_facts,
    mission_future_delta_facts,
    mission_timing_facts,
    mission_value_facts,
    planet_evaluation_facts,
    planet_future_delta_facts,
)
from ow_sim.state import GameState, Planet
from ow_sim.timeline import simulate_ticks as idle_simulate_ticks


def planet(
    planet_id: int = 1,
    owner: int = 0,
    ships: int = 5,
    production: int = 1,
    *,
    is_comet: bool = False,
) -> Planet:
    return Planet(
        planet_id=planet_id,
        owner=owner,
        x=0.0,
        y=0.0,
        radius=1.0,
        ships=ships,
        production=production,
        is_comet=is_comet,
        raw=(planet_id, owner, 0.0, 0.0, 1.0, ships, production),
    )


def state_with_planet() -> GameState:
    source = planet(1, owner=0, ships=5, production=1)
    target = planet(2, owner=-1, ships=3, production=2, is_comet=True)
    enemy = planet(3, owner=1, ships=8, production=4)
    return GameState(
        tick=3,
        player_id=0,
        planets=(source, target, enemy),
        initial_planets=(source, target, enemy),
        next_fleet_id=10,
        raw_observation={
            "step": 3,
            "player": 0,
            "planets": [list(source.raw), list(target.raw), list(enemy.raw)],
        },
    )


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


def launch_test_state(
    *,
    source_owner: int = 0,
    source_ships: int = 10,
    target_owner: int = -1,
    target_ships: int = 0,
    target_production: int = 0,
    next_fleet_id: int | None = 20,
) -> GameState:
    source = planet_at(1, source_owner, 0.0, 0.0, source_ships, production=0)
    target = planet_at(
        2,
        target_owner,
        1.0,
        0.0,
        target_ships,
        production=target_production,
        radius=0.2,
    )
    return GameState(
        tick=0,
        player_id=0,
        planets=(source, target),
        initial_planets=(source, target),
        next_fleet_id=next_fleet_id,
        raw_observation={
            "step": 0,
            "player": 0,
            "planets": [list(source.raw), list(target.raw)],
            "next_fleet_id": next_fleet_id,
        },
    )


def timing_test_state(target_x: float = 10.0) -> GameState:
    source = planet_at(1, 0, 0.0, 0.0, 10, production=0)
    target = planet_at(2, -1, target_x, 0.0, 0, production=0)
    return GameState(
        tick=0,
        player_id=0,
        planets=(source, target),
        initial_planets=(source, target),
        next_fleet_id=20,
        raw_observation={
            "step": 0,
            "player": 0,
            "planets": [list(source.raw), list(target.raw)],
            "next_fleet_id": 20,
        },
    )


def candidate(
    target_planet_id: int,
    mission_type: MissionType = MissionType.CAPTURE_NEUTRAL,
    source_planet_ids: tuple[int, ...] = (1,),
    launches: tuple[LaunchCandidate, ...] | None = None,
    outcome: CandidateOutcome = CandidateOutcome.UNTESTED,
) -> MissionCandidate:
    if launches is None:
        launches = (LaunchCandidate(source_planet_id=1, angle=0.0, ships=1),)
    return MissionCandidate(
        mission_type=mission_type,
        target_planet_id=target_planet_id,
        source_planet_ids=source_planet_ids,
        launches=launches,
        outcome=outcome,
    )


class PlannerEvaluationTests(unittest.TestCase):
    def test_evaluation_module_imports_and_exports_are_available(self) -> None:
        importlib.import_module("ow_planner.evaluation")

        self.assertIsNotNone(evaluate_candidates)
        self.assertIsNotNone(evaluate_and_score_candidates)
        self.assertIs(MissionEvaluation, MissionEvaluation)
        self.assertIs(MissionEvaluationFacts, MissionEvaluationFacts)
        self.assertIs(MissionFutureDeltaFacts, MissionFutureDeltaFacts)
        self.assertIs(MissionTimingFacts, MissionTimingFacts)
        self.assertIs(MissionValueFacts, MissionValueFacts)
        self.assertIs(PlanetEvaluationFacts, PlanetEvaluationFacts)
        self.assertIs(PlanetFutureDeltaFacts, PlanetFutureDeltaFacts)
        self.assertIs(ScoreComponent, ScoreComponent)
        self.assertIs(EvaluationConfig, EvaluationConfig)
        self.assertIsNotNone(baseline_state_after_horizon)
        self.assertIsNotNone(candidate_state_after_horizon)
        self.assertIsNotNone(extract_candidate_facts)
        self.assertIsNotNone(mission_future_delta_facts)
        self.assertIsNotNone(mission_timing_facts)
        self.assertIsNotNone(mission_value_facts)
        self.assertIsNotNone(planet_evaluation_facts)
        self.assertIsNotNone(planet_future_delta_facts)

    def test_enum_string_values_are_stable(self) -> None:
        self.assertEqual(MissionEvaluationStatus.UNEVALUATED.value, "unevaluated")
        self.assertEqual(MissionEvaluationStatus.EVALUATED.value, "evaluated")
        self.assertEqual(MissionEvaluationStatus.REJECTED.value, "rejected")

    def test_dataclasses_are_constructible_and_frozen(self) -> None:
        mission = candidate(2)
        config = EvaluationConfig(horizon_ticks=12)
        component = ScoreComponent(name="placeholder", value=2.5, weight=0.75)
        planet_delta = PlanetFutureDeltaFacts(
            planet_id=2,
            before_owner=-1,
            baseline_owner=-1,
            mission_owner=0,
            before_ships=3,
            baseline_ships=3,
            mission_ships=1,
            mission_ship_delta_vs_baseline=-2,
            mission_ship_delta_vs_before=-2,
            mission_owner_changed_vs_baseline=True,
            mission_owner_changed_vs_before=True,
        )
        future_delta = MissionFutureDeltaFacts(
            target=planet_delta,
            sources=(
                PlanetFutureDeltaFacts(
                    planet_id=1,
                    before_owner=0,
                    baseline_owner=0,
                    mission_owner=0,
                    before_ships=5,
                    baseline_ships=5,
                    mission_ships=4,
                    mission_ship_delta_vs_baseline=-1,
                    mission_ship_delta_vs_before=-1,
                    mission_owner_changed_vs_baseline=False,
                    mission_owner_changed_vs_before=False,
                ),
            ),
            total_source_ship_delta_vs_baseline=-1,
            total_source_ship_delta_vs_before=-1,
        )
        value_facts = MissionValueFacts(
            target_owner_before=-1,
            target_owner_baseline=-1,
            target_owner_mission=0,
            target_captured_by_player=True,
            target_retained_by_player=False,
            target_lost_by_player=False,
            target_production_before=2,
            target_production_baseline_controlled_by_player=0,
            target_production_mission_controlled_by_player=2,
            production_delta_vs_baseline=2,
            target_ship_delta_vs_baseline=-2,
            total_source_ship_delta_vs_baseline=-1,
            total_source_ship_delta_vs_before=-1,
            ships_spent=1,
            mission_valid_for_value=True,
        )
        timing_facts = MissionTimingFacts(
            launch_arrival_ticks=(3,),
            min_arrival_ticks=3,
            max_arrival_ticks=3,
            timing_complete=True,
        )
        facts = MissionEvaluationFacts(
            mission_type=MissionType.CAPTURE_NEUTRAL,
            target_planet_id=2,
            source_planet_ids=(1,),
            launch_count=1,
            ships_spent=1,
            launch_angles=(0.0,),
            candidate_outcome=CandidateOutcome.UNTESTED,
            target_before=PlanetEvaluationFacts(2, -1, 3, 2, True),
            sources_before=(PlanetEvaluationFacts(1, 0, 5, 1),),
            baseline_horizon_ticks=0,
            target_baseline=PlanetEvaluationFacts(2, -1, 3, 2, True),
            sources_baseline=(PlanetEvaluationFacts(1, 0, 5, 1),),
            mission_horizon_ticks=0,
            target_mission=PlanetEvaluationFacts(2, -1, 3, 2, True),
            sources_mission=(PlanetEvaluationFacts(1, 0, 4, 1),),
            future_delta=future_delta,
            value_facts=value_facts,
            timing_facts=timing_facts,
            notes=("structural",),
        )
        evaluation = MissionEvaluation(
            candidate=mission,
            facts=facts,
            score_components=(component,),
            total_score=None,
        )

        self.assertEqual(config.horizon_ticks, 12)
        self.assertEqual(component.name, "placeholder")
        self.assertEqual(planet_delta.mission_ship_delta_vs_baseline, -2)
        self.assertEqual(future_delta.total_source_ship_delta_vs_baseline, -1)
        self.assertEqual(value_facts.production_delta_vs_baseline, 2)
        self.assertEqual(timing_facts.launch_arrival_ticks, (3,))
        self.assertEqual(facts.notes, ("structural",))
        self.assertIs(evaluation.candidate, mission)
        with self.assertRaises(FrozenInstanceError):
            config.horizon_ticks = 1
        with self.assertRaises(FrozenInstanceError):
            component.value = 3.0
        with self.assertRaises(FrozenInstanceError):
            planet_delta.mission_ships = 2
        with self.assertRaises(FrozenInstanceError):
            future_delta.sources = ()
        with self.assertRaises(FrozenInstanceError):
            value_facts.ships_spent = 2
        with self.assertRaises(FrozenInstanceError):
            timing_facts.min_arrival_ticks = 1
        with self.assertRaises(FrozenInstanceError):
            facts.notes = ()
        with self.assertRaises(FrozenInstanceError):
            facts.target_before = None
        with self.assertRaises(FrozenInstanceError):
            facts.target_baseline = None
        with self.assertRaises(FrozenInstanceError):
            facts.target_mission = None
        with self.assertRaises(FrozenInstanceError):
            evaluation.total_score = 1.0

    def test_planet_evaluation_facts_construction_and_frozen_behavior(self) -> None:
        planet_facts = planet_evaluation_facts(planet(7, owner=2, ships=11, production=3, is_comet=True))

        self.assertEqual(planet_facts, PlanetEvaluationFacts(7, 2, 11, 3, True))
        with self.assertRaises(FrozenInstanceError):
            planet_facts.ships = 12

    def test_planet_future_delta_facts_compare_mission_to_baseline_and_before(self) -> None:
        delta = planet_future_delta_facts(
            before=PlanetEvaluationFacts(2, -1, 3, 0),
            baseline=PlanetEvaluationFacts(2, -1, 3, 0),
            mission=PlanetEvaluationFacts(2, 0, 1, 0),
        )

        self.assertEqual(delta.planet_id, 2)
        self.assertEqual(delta.before_owner, -1)
        self.assertEqual(delta.baseline_owner, -1)
        self.assertEqual(delta.mission_owner, 0)
        self.assertEqual(delta.before_ships, 3)
        self.assertEqual(delta.baseline_ships, 3)
        self.assertEqual(delta.mission_ships, 1)
        self.assertEqual(delta.mission_ship_delta_vs_baseline, -2)
        self.assertEqual(delta.mission_ship_delta_vs_before, -2)
        self.assertIs(delta.mission_owner_changed_vs_baseline, True)
        self.assertIs(delta.mission_owner_changed_vs_before, True)

    def test_planet_future_delta_facts_handles_missing_snapshots(self) -> None:
        delta = planet_future_delta_facts(
            before=None,
            baseline=PlanetEvaluationFacts(9, 1, 4, 2),
            mission=None,
            planet_id=9,
        )

        self.assertEqual(delta.planet_id, 9)
        self.assertIsNone(delta.before_owner)
        self.assertEqual(delta.baseline_owner, 1)
        self.assertIsNone(delta.mission_owner)
        self.assertIsNone(delta.mission_ship_delta_vs_baseline)
        self.assertIsNone(delta.mission_ship_delta_vs_before)
        self.assertIsNone(delta.mission_owner_changed_vs_baseline)
        self.assertIsNone(delta.mission_owner_changed_vs_before)

    def test_mission_future_delta_facts_preserve_source_order_and_aggregate_known_deltas(self) -> None:
        delta = mission_future_delta_facts(
            target_planet_id=2,
            source_planet_ids=(3, 1, 1),
            target_before=PlanetEvaluationFacts(2, -1, 0, 0),
            target_baseline=PlanetEvaluationFacts(2, -1, 0, 0),
            target_mission=PlanetEvaluationFacts(2, 0, 1, 0),
            sources_before=(
                PlanetEvaluationFacts(3, 0, 8, 0),
                PlanetEvaluationFacts(1, 0, 5, 0),
                PlanetEvaluationFacts(1, 0, 5, 0),
            ),
            sources_baseline=(
                PlanetEvaluationFacts(3, 0, 8, 0),
                PlanetEvaluationFacts(1, 0, 5, 0),
                PlanetEvaluationFacts(1, 0, 5, 0),
            ),
            sources_mission=(
                PlanetEvaluationFacts(3, 0, 6, 0),
                PlanetEvaluationFacts(1, 0, 4, 0),
                PlanetEvaluationFacts(1, 0, 5, 0),
            ),
        )

        self.assertEqual(delta.target.planet_id, 2)
        self.assertIs(delta.target.mission_owner_changed_vs_baseline, True)
        self.assertEqual(
            tuple(source.planet_id for source in delta.sources),
            (3, 1, 1),
        )
        self.assertEqual(
            tuple(source.mission_ship_delta_vs_baseline for source in delta.sources),
            (-2, -1, 0),
        )
        self.assertEqual(delta.total_source_ship_delta_vs_baseline, -3)
        self.assertEqual(delta.total_source_ship_delta_vs_before, -3)

    def test_mission_future_delta_facts_uses_none_aggregate_when_any_source_delta_missing(self) -> None:
        delta = mission_future_delta_facts(
            target_planet_id=2,
            source_planet_ids=(1, 99),
            target_before=PlanetEvaluationFacts(2, -1, 0, 0),
            target_baseline=PlanetEvaluationFacts(2, -1, 0, 0),
            target_mission=None,
            sources_before=(PlanetEvaluationFacts(1, 0, 5, 0),),
            sources_baseline=(PlanetEvaluationFacts(1, 0, 5, 0),),
            sources_mission=(PlanetEvaluationFacts(1, 0, 4, 0),),
        )

        self.assertIsNone(delta.target.mission_ship_delta_vs_baseline)
        self.assertEqual(
            tuple(source.planet_id for source in delta.sources),
            (1, 99),
        )
        self.assertEqual(delta.sources[0].mission_ship_delta_vs_baseline, -1)
        self.assertIsNone(delta.sources[1].mission_ship_delta_vs_baseline)
        self.assertIsNone(delta.total_source_ship_delta_vs_baseline)

    def test_mission_value_facts_capture_control_and_production_delta(self) -> None:
        future_delta = MissionFutureDeltaFacts(
            target=PlanetFutureDeltaFacts(
                planet_id=2,
                mission_ship_delta_vs_baseline=1,
            ),
            sources=(PlanetFutureDeltaFacts(planet_id=1, mission_ship_delta_vs_baseline=-1),),
            total_source_ship_delta_vs_baseline=-1,
            total_source_ship_delta_vs_before=-1,
        )

        value_facts = mission_value_facts(
            player_id=0,
            target_before=PlanetEvaluationFacts(2, -1, 0, 3),
            target_baseline=PlanetEvaluationFacts(2, -1, 0, 3),
            target_mission=PlanetEvaluationFacts(2, 0, 1, 3),
            future_delta=future_delta,
            ships_spent=1,
        )

        self.assertEqual(value_facts.target_owner_before, -1)
        self.assertEqual(value_facts.target_owner_baseline, -1)
        self.assertEqual(value_facts.target_owner_mission, 0)
        self.assertIs(value_facts.target_captured_by_player, True)
        self.assertIs(value_facts.target_retained_by_player, False)
        self.assertIs(value_facts.target_lost_by_player, False)
        self.assertEqual(value_facts.target_production_before, 3)
        self.assertEqual(value_facts.target_production_baseline_controlled_by_player, 0)
        self.assertEqual(value_facts.target_production_mission_controlled_by_player, 3)
        self.assertEqual(value_facts.production_delta_vs_baseline, 3)
        self.assertEqual(value_facts.target_ship_delta_vs_baseline, 1)
        self.assertEqual(value_facts.total_source_ship_delta_vs_baseline, -1)
        self.assertEqual(value_facts.total_source_ship_delta_vs_before, -1)
        self.assertEqual(value_facts.ships_spent, 1)
        self.assertIs(value_facts.mission_valid_for_value, True)

    def test_mission_value_facts_mark_missing_or_error_inputs_invalid(self) -> None:
        future_delta = MissionFutureDeltaFacts(
            target=PlanetFutureDeltaFacts(planet_id=2),
            sources=(PlanetFutureDeltaFacts(planet_id=1),),
        )

        value_facts = mission_value_facts(
            player_id=0,
            target_before=PlanetEvaluationFacts(2, -1, 0, 3),
            target_baseline=PlanetEvaluationFacts(2, -1, 0, 3),
            target_mission=None,
            future_delta=future_delta,
            ships_spent=2,
            mission_simulation_error="source planet does not have enough ships",
        )

        self.assertEqual(value_facts.target_owner_before, -1)
        self.assertEqual(value_facts.target_owner_baseline, -1)
        self.assertIsNone(value_facts.target_owner_mission)
        self.assertIsNone(value_facts.target_captured_by_player)
        self.assertEqual(value_facts.target_production_baseline_controlled_by_player, 0)
        self.assertIsNone(value_facts.target_production_mission_controlled_by_player)
        self.assertIsNone(value_facts.production_delta_vs_baseline)
        self.assertIsNone(value_facts.target_ship_delta_vs_baseline)
        self.assertEqual(value_facts.ships_spent, 2)
        self.assertIs(value_facts.mission_valid_for_value, False)

    def test_mission_timing_facts_no_launch_is_complete(self) -> None:
        facts = mission_timing_facts(timing_test_state(), candidate(2, launches=()))

        self.assertEqual(facts, MissionTimingFacts(timing_complete=True))

    def test_mission_timing_facts_single_launch_uses_geometry_and_ship_speed(self) -> None:
        mission = candidate(
            2,
            launches=(LaunchCandidate(source_planet_id=1, angle=0.0, ships=1),),
        )

        facts = mission_timing_facts(timing_test_state(target_x=10.0), mission)

        self.assertEqual(facts.launch_arrival_ticks, (10,))
        self.assertEqual(facts.min_arrival_ticks, 10)
        self.assertEqual(facts.max_arrival_ticks, 10)
        self.assertIs(facts.timing_complete, True)
        self.assertIsNone(facts.missing_timing_target_planet_id)
        self.assertEqual(facts.missing_timing_source_planet_ids, ())

    def test_mission_timing_facts_multi_launch_preserves_order_and_min_max(self) -> None:
        mission = candidate(
            2,
            launches=(
                LaunchCandidate(source_planet_id=1, angle=0.0, ships=1),
                LaunchCandidate(source_planet_id=1, angle=0.0, ships=1000),
            ),
        )

        facts = mission_timing_facts(timing_test_state(target_x=10.0), mission)

        self.assertEqual(facts.launch_arrival_ticks, (10, 2))
        self.assertEqual(facts.min_arrival_ticks, 2)
        self.assertEqual(facts.max_arrival_ticks, 10)
        self.assertIs(facts.timing_complete, True)

    def test_mission_timing_facts_missing_target_is_incomplete(self) -> None:
        facts = mission_timing_facts(timing_test_state(), candidate(99))

        self.assertEqual(facts.launch_arrival_ticks, (None,))
        self.assertIsNone(facts.min_arrival_ticks)
        self.assertIsNone(facts.max_arrival_ticks)
        self.assertIs(facts.timing_complete, False)
        self.assertEqual(facts.missing_timing_target_planet_id, 99)

    def test_mission_timing_facts_missing_source_is_incomplete(self) -> None:
        mission = candidate(
            2,
            source_planet_ids=(99,),
            launches=(LaunchCandidate(source_planet_id=99, angle=0.0, ships=1),),
        )

        facts = mission_timing_facts(timing_test_state(), mission)

        self.assertEqual(facts.launch_arrival_ticks, (None,))
        self.assertIs(facts.timing_complete, False)
        self.assertEqual(facts.missing_timing_source_planet_ids, (99,))

    def test_mission_timing_facts_missing_state_is_incomplete_without_missing_ids(self) -> None:
        facts = mission_timing_facts(None, candidate(2))

        self.assertEqual(facts.launch_arrival_ticks, (None,))
        self.assertIsNone(facts.min_arrival_ticks)
        self.assertIsNone(facts.max_arrival_ticks)
        self.assertIs(facts.timing_complete, False)
        self.assertIsNone(facts.missing_timing_target_planet_id)
        self.assertEqual(facts.missing_timing_source_planet_ids, ())

    def test_mission_timing_facts_invalid_launch_ships_are_incomplete(self) -> None:
        mission = candidate(
            2,
            launches=(LaunchCandidate(source_planet_id=1, angle=0.0, ships=0),),
        )

        facts = mission_timing_facts(timing_test_state(), mission)

        self.assertEqual(facts.launch_arrival_ticks, (None,))
        self.assertIsNone(facts.min_arrival_ticks)
        self.assertIsNone(facts.max_arrival_ticks)
        self.assertIs(facts.timing_complete, False)

    def test_evaluate_candidates_returns_empty_tuple_for_empty_input(self) -> None:
        self.assertEqual(evaluate_candidates(state_with_planet(), ()), ())

    def test_evaluate_candidates_preserves_candidate_input_order(self) -> None:
        first = candidate(2, MissionType.CAPTURE_NEUTRAL)
        second = candidate(3, MissionType.ATTACK_ENEMY)

        evaluations = evaluate_candidates(state_with_planet(), (first, second))

        self.assertEqual(
            tuple(evaluation.candidate for evaluation in evaluations),
            (first, second),
        )
        self.assertIs(evaluations[0].candidate, first)
        self.assertIs(evaluations[1].candidate, second)

    def test_extract_candidate_facts_for_neutral_capture_candidate(self) -> None:
        mission = candidate(2)

        facts = extract_candidate_facts(mission)

        self.assertEqual(facts.mission_type, MissionType.CAPTURE_NEUTRAL)
        self.assertEqual(facts.target_planet_id, 2)
        self.assertEqual(facts.source_planet_ids, (1,))
        self.assertEqual(facts.launch_count, 1)
        self.assertEqual(facts.ships_spent, 1)
        self.assertEqual(facts.launch_angles, (0.0,))
        self.assertEqual(facts.candidate_outcome, CandidateOutcome.UNTESTED)
        self.assertIsNone(facts.target_before)
        self.assertEqual(facts.sources_before, ())
        self.assertIsNone(facts.missing_target_planet_id)
        self.assertEqual(facts.missing_source_planet_ids, ())
        self.assertEqual(facts.baseline_horizon_ticks, 0)
        self.assertIsNone(facts.target_baseline)
        self.assertEqual(facts.sources_baseline, ())
        self.assertIsNone(facts.missing_baseline_target_planet_id)
        self.assertEqual(facts.missing_baseline_source_planet_ids, ())
        self.assertEqual(facts.mission_horizon_ticks, 0)
        self.assertIsNone(facts.target_mission)
        self.assertEqual(facts.sources_mission, ())
        self.assertIsNone(facts.missing_mission_target_planet_id)
        self.assertEqual(facts.missing_mission_source_planet_ids, ())
        self.assertIsNone(facts.mission_simulation_error)
        self.assertEqual(facts.future_delta.target.planet_id, 2)
        self.assertIsNone(facts.future_delta.target.mission_ship_delta_vs_baseline)
        self.assertEqual(
            tuple(source.planet_id for source in facts.future_delta.sources),
            (1,),
        )
        self.assertIsNone(facts.future_delta.total_source_ship_delta_vs_baseline)
        self.assertEqual(facts.value_facts, MissionValueFacts(ships_spent=1))
        self.assertEqual(facts.timing_facts.launch_arrival_ticks, (None,))
        self.assertIs(facts.timing_facts.timing_complete, False)

    def test_extract_candidate_facts_for_enemy_attack_candidate(self) -> None:
        mission = candidate(
            3,
            mission_type=MissionType.ATTACK_ENEMY,
            outcome=CandidateOutcome.VALIDATED,
        )

        facts = extract_candidate_facts(mission)

        self.assertEqual(facts.mission_type, MissionType.ATTACK_ENEMY)
        self.assertEqual(facts.target_planet_id, 3)
        self.assertEqual(facts.candidate_outcome, CandidateOutcome.VALIDATED)

    def test_multi_launch_candidate_totals_and_ordered_angles(self) -> None:
        mission = candidate(
            4,
            source_planet_ids=(3, 1),
            launches=(
                LaunchCandidate(source_planet_id=3, angle=1.25, ships=5),
                LaunchCandidate(source_planet_id=1, angle=-0.5, ships=7),
            ),
        )

        facts = extract_candidate_facts(mission)

        self.assertEqual(facts.source_planet_ids, (3, 1))
        self.assertEqual(facts.launch_count, 2)
        self.assertEqual(facts.ships_spent, 12)
        self.assertEqual(facts.launch_angles, (1.25, -0.5))

    def test_no_launch_candidate_has_zero_launch_facts(self) -> None:
        mission = candidate(5, launches=())

        facts = extract_candidate_facts(mission)

        self.assertEqual(facts.launch_count, 0)
        self.assertEqual(facts.ships_spent, 0)
        self.assertEqual(facts.launch_angles, ())

    def test_target_before_state_facts_include_owner_ships_production_and_comet(self) -> None:
        facts = extract_candidate_facts(candidate(2), state_with_planet())

        self.assertEqual(facts.target_before, PlanetEvaluationFacts(2, -1, 3, 2, True))
        self.assertIsNone(facts.missing_target_planet_id)

    def test_source_before_state_facts_for_one_source(self) -> None:
        facts = extract_candidate_facts(candidate(2), state_with_planet())

        self.assertEqual(facts.sources_before, (PlanetEvaluationFacts(1, 0, 5, 1),))
        self.assertEqual(facts.missing_source_planet_ids, ())

    def test_source_before_state_facts_preserve_multiple_source_order(self) -> None:
        mission = candidate(
            2,
            source_planet_ids=(3, 1),
            launches=(
                LaunchCandidate(source_planet_id=3, angle=1.0, ships=2),
                LaunchCandidate(source_planet_id=1, angle=0.0, ships=1),
            ),
        )

        facts = extract_candidate_facts(mission, state_with_planet())

        self.assertEqual(
            facts.sources_before,
            (
                PlanetEvaluationFacts(3, 1, 8, 4),
                PlanetEvaluationFacts(1, 0, 5, 1),
            ),
        )

    def test_duplicate_source_ids_preserve_duplicate_facts(self) -> None:
        mission = candidate(
            2,
            source_planet_ids=(1, 1),
            launches=(
                LaunchCandidate(source_planet_id=1, angle=0.0, ships=1),
                LaunchCandidate(source_planet_id=1, angle=0.5, ships=2),
            ),
        )

        facts = extract_candidate_facts(mission, state_with_planet())

        self.assertEqual(
            facts.sources_before,
            (
                PlanetEvaluationFacts(1, 0, 5, 1),
                PlanetEvaluationFacts(1, 0, 5, 1),
            ),
        )

    def test_missing_target_id_is_reported_without_crashing(self) -> None:
        facts = extract_candidate_facts(candidate(99), state_with_planet())

        self.assertIsNone(facts.target_before)
        self.assertEqual(facts.missing_target_planet_id, 99)

    def test_missing_source_ids_are_reported_in_candidate_order(self) -> None:
        mission = candidate(
            2,
            source_planet_ids=(1, 99, 3, 42),
            launches=(),
        )

        facts = extract_candidate_facts(mission, state_with_planet())

        self.assertEqual(
            facts.sources_before,
            (
                PlanetEvaluationFacts(1, 0, 5, 1),
                PlanetEvaluationFacts(3, 1, 8, 4),
            ),
        )
        self.assertEqual(facts.missing_source_planet_ids, (99, 42))

    def test_none_target_id_is_not_reported_missing(self) -> None:
        mission = MissionCandidate(
            mission_type=MissionType.REINFORCE,
            target_planet_id=None,
            source_planet_ids=(1,),
            launches=(),
        )

        facts = extract_candidate_facts(mission, state_with_planet())

        self.assertIsNone(facts.target_before)
        self.assertIsNone(facts.missing_target_planet_id)
        self.assertIsNone(facts.target_baseline)
        self.assertIsNone(facts.missing_baseline_target_planet_id)

    def test_horizon_none_uses_zero_baseline(self) -> None:
        mission = candidate(2)

        (evaluation,) = evaluate_candidates(
            state_with_planet(),
            (mission,),
            EvaluationConfig(horizon_ticks=None),
        )

        self.assertEqual(evaluation.facts.baseline_horizon_ticks, 0)
        self.assertEqual(evaluation.facts.target_baseline, evaluation.facts.target_before)
        self.assertEqual(evaluation.facts.sources_baseline, evaluation.facts.sources_before)

    def test_horizon_zero_baseline_matches_current_state_facts(self) -> None:
        mission = candidate(2)

        (evaluation,) = evaluate_candidates(
            state_with_planet(),
            (mission,),
            EvaluationConfig(horizon_ticks=0),
        )

        self.assertEqual(evaluation.facts.baseline_horizon_ticks, 0)
        self.assertEqual(evaluation.facts.target_baseline, PlanetEvaluationFacts(2, -1, 3, 2, True))
        self.assertEqual(evaluation.facts.sources_baseline, (PlanetEvaluationFacts(1, 0, 5, 1),))

    def test_baseline_state_after_horizon_zero_returns_input_state(self) -> None:
        state = state_with_planet()

        self.assertIs(baseline_state_after_horizon(state, 0), state)

    def test_positive_baseline_horizon_uses_idle_simulation(self) -> None:
        mission = candidate(3, mission_type=MissionType.ATTACK_ENEMY)

        with patch("ow_planner.evaluation.simulate_ticks", wraps=idle_simulate_ticks) as simulate:
            (evaluation,) = evaluate_candidates(
                state_with_planet(),
                (mission,),
                EvaluationConfig(horizon_ticks=2),
            )

        simulate.assert_called_once()
        self.assertEqual(simulate.call_args.args[1], 2)
        self.assertEqual(evaluation.facts.baseline_horizon_ticks, 2)

    def test_baseline_target_facts_after_production_for_owned_and_enemy_planets(self) -> None:
        enemy_mission = candidate(3, mission_type=MissionType.ATTACK_ENEMY)
        own_mission = candidate(1, mission_type=MissionType.DEFEND_OWN)

        enemy_eval, own_eval = evaluate_candidates(
            state_with_planet(),
            (enemy_mission, own_mission),
            EvaluationConfig(horizon_ticks=2),
        )

        self.assertEqual(enemy_eval.facts.target_baseline, PlanetEvaluationFacts(3, 1, 16, 4))
        self.assertEqual(own_eval.facts.target_baseline, PlanetEvaluationFacts(1, 0, 7, 1))

    def test_baseline_neutral_target_does_not_gain_production(self) -> None:
        (evaluation,) = evaluate_candidates(
            state_with_planet(),
            (candidate(2),),
            EvaluationConfig(horizon_ticks=2),
        )

        self.assertEqual(evaluation.facts.target_before, PlanetEvaluationFacts(2, -1, 3, 2, True))
        self.assertEqual(evaluation.facts.target_baseline, PlanetEvaluationFacts(2, -1, 3, 2, True))

    def test_baseline_source_facts_preserve_candidate_source_order(self) -> None:
        mission = candidate(
            2,
            source_planet_ids=(3, 1),
            launches=(),
        )

        (evaluation,) = evaluate_candidates(
            state_with_planet(),
            (mission,),
            EvaluationConfig(horizon_ticks=1),
        )

        self.assertEqual(
            evaluation.facts.sources_baseline,
            (
                PlanetEvaluationFacts(3, 1, 12, 4),
                PlanetEvaluationFacts(1, 0, 6, 1),
            ),
        )

    def test_duplicate_source_ids_preserve_duplicate_baseline_facts(self) -> None:
        mission = candidate(
            2,
            source_planet_ids=(1, 1),
            launches=(),
        )

        (evaluation,) = evaluate_candidates(
            state_with_planet(),
            (mission,),
            EvaluationConfig(horizon_ticks=1),
        )

        self.assertEqual(
            evaluation.facts.sources_baseline,
            (
                PlanetEvaluationFacts(1, 0, 6, 1),
                PlanetEvaluationFacts(1, 0, 6, 1),
            ),
        )

    def test_missing_baseline_target_id_is_reported_without_crashing(self) -> None:
        (evaluation,) = evaluate_candidates(
            state_with_planet(),
            (candidate(99),),
            EvaluationConfig(horizon_ticks=1),
        )

        self.assertIsNone(evaluation.facts.target_baseline)
        self.assertEqual(evaluation.facts.missing_baseline_target_planet_id, 99)

    def test_missing_baseline_source_ids_are_reported_without_crashing(self) -> None:
        mission = candidate(
            2,
            source_planet_ids=(1, 99, 3, 42),
            launches=(),
        )

        (evaluation,) = evaluate_candidates(
            state_with_planet(),
            (mission,),
            EvaluationConfig(horizon_ticks=1),
        )

        self.assertEqual(
            evaluation.facts.sources_baseline,
            (
                PlanetEvaluationFacts(1, 0, 6, 1),
                PlanetEvaluationFacts(3, 1, 12, 4),
            ),
        )
        self.assertEqual(evaluation.facts.missing_baseline_source_planet_ids, (99, 42))

    def test_none_target_id_is_not_reported_missing_for_baseline(self) -> None:
        mission = MissionCandidate(
            mission_type=MissionType.REINFORCE,
            target_planet_id=None,
            source_planet_ids=(1,),
            launches=(),
        )

        (evaluation,) = evaluate_candidates(
            state_with_planet(),
            (mission,),
            EvaluationConfig(horizon_ticks=1),
        )

        self.assertIsNone(evaluation.facts.target_baseline)
        self.assertIsNone(evaluation.facts.missing_baseline_target_planet_id)

    def test_zero_horizon_no_launch_mission_facts_match_current_and_baseline(self) -> None:
        mission = candidate(2, launches=())

        (evaluation,) = evaluate_candidates(
            state_with_planet(),
            (mission,),
            EvaluationConfig(horizon_ticks=0),
        )

        self.assertEqual(evaluation.facts.mission_horizon_ticks, 0)
        self.assertEqual(evaluation.facts.target_mission, evaluation.facts.target_before)
        self.assertEqual(evaluation.facts.target_mission, evaluation.facts.target_baseline)
        self.assertEqual(evaluation.facts.sources_mission, evaluation.facts.sources_before)
        self.assertEqual(evaluation.facts.sources_mission, evaluation.facts.sources_baseline)
        self.assertIsNone(evaluation.facts.mission_simulation_error)
        self.assertEqual(
            evaluation.facts.future_delta.target.mission_ship_delta_vs_baseline,
            0,
        )
        self.assertIs(
            evaluation.facts.future_delta.target.mission_owner_changed_vs_baseline,
            False,
        )
        self.assertEqual(
            tuple(
                source.mission_ship_delta_vs_baseline
                for source in evaluation.facts.future_delta.sources
            ),
            (0,),
        )
        self.assertEqual(evaluation.facts.value_facts.target_owner_before, -1)
        self.assertEqual(evaluation.facts.value_facts.target_owner_baseline, -1)
        self.assertEqual(evaluation.facts.value_facts.target_owner_mission, -1)
        self.assertIs(evaluation.facts.value_facts.target_captured_by_player, False)
        self.assertEqual(evaluation.facts.value_facts.production_delta_vs_baseline, 0)
        self.assertEqual(evaluation.facts.value_facts.target_ship_delta_vs_baseline, 0)
        self.assertEqual(
            evaluation.facts.value_facts.total_source_ship_delta_vs_baseline,
            0,
        )
        self.assertEqual(evaluation.facts.value_facts.ships_spent, 0)
        self.assertIs(evaluation.facts.value_facts.mission_valid_for_value, True)
        self.assertEqual(evaluation.facts.timing_facts.launch_arrival_ticks, ())
        self.assertIs(evaluation.facts.timing_facts.timing_complete, True)

    def test_no_launch_positive_horizon_candidate_future_matches_idle_baseline(self) -> None:
        state = launch_test_state(next_fleet_id=None)
        mission = candidate(2, launches=())

        (evaluation,) = evaluate_candidates(
            state,
            (mission,),
            EvaluationConfig(horizon_ticks=2),
        )

        self.assertEqual(evaluation.facts.mission_horizon_ticks, 2)
        self.assertEqual(evaluation.facts.target_mission, evaluation.facts.target_baseline)
        self.assertEqual(evaluation.facts.sources_mission, evaluation.facts.sources_baseline)
        self.assertIsNone(evaluation.facts.mission_simulation_error)
        self.assertEqual(
            evaluation.facts.future_delta.target.mission_ship_delta_vs_baseline,
            0,
        )
        self.assertEqual(
            evaluation.facts.future_delta.total_source_ship_delta_vs_baseline,
            0,
        )
        self.assertEqual(evaluation.facts.value_facts.production_delta_vs_baseline, 0)
        self.assertEqual(
            evaluation.facts.value_facts.total_source_ship_delta_vs_baseline,
            0,
        )
        self.assertEqual(evaluation.facts.value_facts.ships_spent, 0)
        self.assertIs(evaluation.facts.value_facts.mission_valid_for_value, True)
        self.assertEqual(evaluation.facts.timing_facts.launch_arrival_ticks, ())
        self.assertIs(evaluation.facts.timing_facts.timing_complete, True)

    def test_candidate_state_after_horizon_launch_reduces_source_at_zero_horizon(self) -> None:
        state = launch_test_state(source_ships=10)
        mission = candidate(
            2,
            launches=(LaunchCandidate(source_planet_id=1, angle=0.0, ships=3),),
        )

        future = candidate_state_after_horizon(state, mission, 0)

        source_after = next(planet for planet in future.planets if planet.planet_id == 1)
        target_after = next(planet for planet in future.planets if planet.planet_id == 2)
        self.assertEqual(source_after.ships, 7)
        self.assertEqual(target_after.owner, -1)
        self.assertEqual(target_after.ships, 0)

    def test_neutral_capture_candidate_populates_target_mission_facts(self) -> None:
        state = launch_test_state(target_owner=-1, target_ships=0, target_production=3)
        mission = candidate(
            2,
            launches=(LaunchCandidate(source_planet_id=1, angle=0.0, ships=1),),
        )

        (evaluation,) = evaluate_candidates(
            state,
            (mission,),
            EvaluationConfig(horizon_ticks=1),
        )

        self.assertEqual(evaluation.facts.target_baseline, PlanetEvaluationFacts(2, -1, 0, 3))
        self.assertEqual(evaluation.facts.target_mission, PlanetEvaluationFacts(2, 0, 1, 3))
        self.assertEqual(evaluation.facts.sources_mission, (PlanetEvaluationFacts(1, 0, 9, 0),))
        self.assertIsNone(evaluation.facts.mission_simulation_error)
        self.assertEqual(evaluation.facts.future_delta.target.baseline_owner, -1)
        self.assertEqual(evaluation.facts.future_delta.target.mission_owner, 0)
        self.assertEqual(
            evaluation.facts.future_delta.target.mission_ship_delta_vs_baseline,
            1,
        )
        self.assertIs(
            evaluation.facts.future_delta.target.mission_owner_changed_vs_baseline,
            True,
        )
        self.assertEqual(
            evaluation.facts.future_delta.sources[0].mission_ship_delta_vs_baseline,
            -1,
        )
        self.assertEqual(
            evaluation.facts.future_delta.sources[0].mission_ship_delta_vs_before,
            -1,
        )
        self.assertEqual(
            evaluation.facts.future_delta.total_source_ship_delta_vs_baseline,
            -1,
        )
        self.assertIs(evaluation.facts.value_facts.target_captured_by_player, True)
        self.assertIs(evaluation.facts.value_facts.target_retained_by_player, False)
        self.assertIs(evaluation.facts.value_facts.target_lost_by_player, False)
        self.assertEqual(
            evaluation.facts.value_facts.target_production_before,
            3,
        )
        self.assertEqual(
            evaluation.facts.value_facts.target_production_baseline_controlled_by_player,
            0,
        )
        self.assertEqual(
            evaluation.facts.value_facts.target_production_mission_controlled_by_player,
            3,
        )
        self.assertEqual(evaluation.facts.value_facts.production_delta_vs_baseline, 3)
        self.assertEqual(evaluation.facts.value_facts.target_ship_delta_vs_baseline, 1)
        self.assertEqual(
            evaluation.facts.value_facts.total_source_ship_delta_vs_baseline,
            -1,
        )
        self.assertEqual(
            evaluation.facts.value_facts.total_source_ship_delta_vs_before,
            -1,
        )
        self.assertEqual(evaluation.facts.value_facts.ships_spent, 1)
        self.assertIs(evaluation.facts.value_facts.mission_valid_for_value, True)
        self.assertEqual(evaluation.facts.timing_facts.launch_arrival_ticks, (1,))
        self.assertEqual(evaluation.facts.timing_facts.min_arrival_ticks, 1)
        self.assertEqual(evaluation.facts.timing_facts.max_arrival_ticks, 1)
        self.assertIs(evaluation.facts.timing_facts.timing_complete, True)

    def test_enemy_attack_candidate_populates_target_mission_facts(self) -> None:
        state = launch_test_state(target_owner=1, target_ships=0, target_production=4)
        mission = candidate(
            2,
            mission_type=MissionType.ATTACK_ENEMY,
            launches=(LaunchCandidate(source_planet_id=1, angle=0.0, ships=5),),
        )

        (evaluation,) = evaluate_candidates(
            state,
            (mission,),
            EvaluationConfig(horizon_ticks=1),
        )

        self.assertEqual(evaluation.facts.target_baseline, PlanetEvaluationFacts(2, 1, 4, 4))
        self.assertEqual(evaluation.facts.target_mission, PlanetEvaluationFacts(2, 0, 1, 4))
        self.assertIsNone(evaluation.facts.mission_simulation_error)
        self.assertEqual(evaluation.facts.future_delta.target.baseline_owner, 1)
        self.assertEqual(evaluation.facts.future_delta.target.mission_owner, 0)
        self.assertIs(
            evaluation.facts.future_delta.target.mission_owner_changed_vs_baseline,
            True,
        )
        self.assertIs(evaluation.facts.value_facts.target_captured_by_player, True)
        self.assertEqual(evaluation.facts.value_facts.production_delta_vs_baseline, 4)
        self.assertEqual(evaluation.facts.value_facts.target_ship_delta_vs_baseline, -3)
        self.assertEqual(
            evaluation.facts.value_facts.total_source_ship_delta_vs_baseline,
            -5,
        )
        self.assertEqual(evaluation.facts.value_facts.ships_spent, 5)
        self.assertIs(evaluation.facts.value_facts.mission_valid_for_value, True)

    def test_candidate_conversion_rejection_records_mission_simulation_error(self) -> None:
        state = launch_test_state(source_ships=1)
        mission = candidate(
            2,
            launches=(LaunchCandidate(source_planet_id=1, angle=0.0, ships=2),),
        )

        (evaluation,) = evaluate_candidates(
            state,
            (mission,),
            EvaluationConfig(horizon_ticks=1),
        )

        self.assertIn("enough ships", evaluation.facts.mission_simulation_error)
        self.assertIsNone(evaluation.facts.target_mission)
        self.assertEqual(evaluation.facts.sources_mission, ())
        self.assertIsNone(
            evaluation.facts.future_delta.target.mission_ship_delta_vs_baseline
        )
        self.assertIsNone(
            evaluation.facts.future_delta.sources[0].mission_ship_delta_vs_baseline
        )
        self.assertIsNone(evaluation.facts.future_delta.total_source_ship_delta_vs_baseline)
        self.assertEqual(evaluation.facts.value_facts.ships_spent, 2)
        self.assertIsNone(evaluation.facts.value_facts.target_owner_mission)
        self.assertIsNone(evaluation.facts.value_facts.production_delta_vs_baseline)
        self.assertIs(evaluation.facts.value_facts.mission_valid_for_value, False)

    def test_missing_mission_target_id_is_reported_without_crashing(self) -> None:
        state = launch_test_state()
        mission = candidate(2, launches=())
        source_only = GameState(
            tick=1,
            player_id=0,
            planets=(state.planets[0],),
            initial_planets=(state.planets[0],),
            next_fleet_id=state.next_fleet_id,
        )

        with patch(
            "ow_planner.evaluation.candidate_state_after_horizon",
            return_value=source_only,
        ):
            (evaluation,) = evaluate_candidates(
                state,
                (mission,),
                EvaluationConfig(horizon_ticks=1),
            )

        self.assertIsNone(evaluation.facts.target_mission)
        self.assertEqual(evaluation.facts.missing_mission_target_planet_id, 2)
        self.assertIsNone(
            evaluation.facts.future_delta.target.mission_ship_delta_vs_baseline
        )
        self.assertIsNone(evaluation.facts.value_facts.target_owner_mission)
        self.assertIsNone(evaluation.facts.value_facts.production_delta_vs_baseline)
        self.assertIs(evaluation.facts.value_facts.mission_valid_for_value, False)

    def test_missing_mission_source_ids_are_reported_without_crashing(self) -> None:
        state = launch_test_state()
        mission = candidate(2, source_planet_ids=(1, 99), launches=())
        target_only = GameState(
            tick=1,
            player_id=0,
            planets=(state.planets[1],),
            initial_planets=(state.planets[1],),
            next_fleet_id=state.next_fleet_id,
        )

        with patch(
            "ow_planner.evaluation.candidate_state_after_horizon",
            return_value=target_only,
        ):
            (evaluation,) = evaluate_candidates(
                state,
                (mission,),
                EvaluationConfig(horizon_ticks=1),
            )

        self.assertEqual(evaluation.facts.sources_mission, ())
        self.assertEqual(evaluation.facts.missing_mission_source_planet_ids, (1, 99))
        self.assertIsNone(
            evaluation.facts.future_delta.sources[0].mission_ship_delta_vs_baseline
        )
        self.assertIsNone(
            evaluation.facts.future_delta.sources[1].mission_ship_delta_vs_baseline
        )
        self.assertIsNone(
            evaluation.facts.value_facts.total_source_ship_delta_vs_baseline
        )
        self.assertIs(evaluation.facts.value_facts.mission_valid_for_value, False)

    def test_none_target_id_is_not_reported_missing_for_mission(self) -> None:
        mission = MissionCandidate(
            mission_type=MissionType.REINFORCE,
            target_planet_id=None,
            source_planet_ids=(1,),
            launches=(),
        )

        (evaluation,) = evaluate_candidates(
            state_with_planet(),
            (mission,),
            EvaluationConfig(horizon_ticks=1),
        )

        self.assertIsNone(evaluation.facts.target_mission)
        self.assertIsNone(evaluation.facts.missing_mission_target_planet_id)

    def test_mission_source_facts_preserve_candidate_source_order_and_duplicates(self) -> None:
        mission = candidate(
            2,
            source_planet_ids=(3, 1, 1),
            launches=(),
        )

        (evaluation,) = evaluate_candidates(
            state_with_planet(),
            (mission,),
            EvaluationConfig(horizon_ticks=1),
        )

        self.assertEqual(
            evaluation.facts.sources_mission,
            (
                PlanetEvaluationFacts(3, 1, 12, 4),
                PlanetEvaluationFacts(1, 0, 6, 1),
                PlanetEvaluationFacts(1, 0, 6, 1),
            ),
        )

    def test_baseline_facts_remain_separate_from_mission_facts(self) -> None:
        state = launch_test_state(target_owner=-1, target_ships=0)
        mission = candidate(
            2,
            launches=(LaunchCandidate(source_planet_id=1, angle=0.0, ships=1),),
        )

        (evaluation,) = evaluate_candidates(
            state,
            (mission,),
            EvaluationConfig(horizon_ticks=1),
        )

        self.assertEqual(evaluation.facts.target_baseline, PlanetEvaluationFacts(2, -1, 0, 0))
        self.assertEqual(evaluation.facts.target_mission, PlanetEvaluationFacts(2, 0, 1, 0))
        self.assertEqual(evaluation.facts.future_delta.target.baseline_owner, -1)
        self.assertEqual(evaluation.facts.future_delta.target.mission_owner, 0)
        self.assertIs(
            evaluation.facts.future_delta.target.mission_owner_changed_vs_baseline,
            True,
        )

    def test_evaluate_candidates_returns_evaluated_wrappers_with_facts(self) -> None:
        mission = candidate(2)
        state = state_with_planet()
        mission_state = candidate_state_after_horizon(state, mission, 0)

        (evaluation,) = evaluate_candidates(state, (mission,))

        self.assertEqual(evaluation.status, MissionEvaluationStatus.EVALUATED)
        self.assertEqual(
            evaluation.facts,
            extract_candidate_facts(
                mission,
                state,
                baseline_state=state,
                mission_state=mission_state,
                player_id=state.player_id,
            ),
        )
        self.assertEqual(evaluation.facts.baseline_horizon_ticks, 0)
        self.assertEqual(evaluation.score_components, ())
        self.assertIsNone(evaluation.total_score)
        self.assertIsNone(evaluation.note)

    def test_evaluate_and_score_candidates_returns_scored_evaluations(self) -> None:
        state = launch_test_state(target_owner=-1, target_ships=0, target_production=3)
        mission = candidate(
            2,
            launches=(LaunchCandidate(source_planet_id=1, angle=0.0, ships=1),),
        )

        (evaluation,) = evaluate_and_score_candidates(
            state,
            (mission,),
            evaluation_config=EvaluationConfig(horizon_ticks=1),
        )

        self.assertIs(evaluation.candidate, mission)
        self.assertEqual(
            tuple(component.name for component in evaluation.score_components),
            (
                "production_delta_vs_baseline",
                "target_ship_delta_vs_baseline",
                "source_ship_delta_vs_baseline",
                "ships_spent",
                "max_arrival_ticks",
            ),
        )
        self.assertEqual(
            evaluation.score_components[-1],
            ScoreComponent("max_arrival_ticks", 1.0, -0.05),
        )
        self.assertAlmostEqual(evaluation.total_score, 29.7)

    def test_evaluate_and_score_candidates_applies_custom_scoring_config(self) -> None:
        state = launch_test_state(target_owner=-1, target_ships=0, target_production=3)
        mission = candidate(
            2,
            launches=(LaunchCandidate(source_planet_id=1, angle=0.0, ships=1),),
        )

        (evaluation,) = evaluate_and_score_candidates(
            state,
            (mission,),
            evaluation_config=EvaluationConfig(horizon_ticks=1),
            scoring_config=MissionScoringConfig(
                production_delta_weight=1.0,
                ships_spent_weight=-1.0,
            ),
        )

        self.assertAlmostEqual(evaluation.total_score, 1.95)

    def test_evaluate_and_score_candidates_propagates_invalid_penalty(self) -> None:
        state = launch_test_state(source_ships=1)
        mission = candidate(
            2,
            launches=(LaunchCandidate(source_planet_id=1, angle=0.0, ships=2),),
        )

        (evaluation,) = evaluate_and_score_candidates(
            state,
            (mission,),
            evaluation_config=EvaluationConfig(horizon_ticks=1),
        )

        self.assertIn("enough ships", evaluation.facts.mission_simulation_error)
        self.assertEqual(
            evaluation.score_components,
            (ScoreComponent("invalid_mission_penalty", 1.0, -1000.0),),
        )
        self.assertEqual(evaluation.total_score, -1000.0)

    def test_evaluate_and_score_candidates_returns_empty_tuple_for_empty_input(self) -> None:
        self.assertEqual(evaluate_and_score_candidates(state_with_planet(), ()), ())

    def test_evaluate_candidates_remains_unscored_by_default(self) -> None:
        mission = candidate(2, launches=())

        (evaluation,) = evaluate_candidates(state_with_planet(), (mission,))

        self.assertEqual(evaluation.score_components, ())
        self.assertIsNone(evaluation.total_score)

    def test_evaluate_and_score_candidates_does_not_mutate_state_or_candidates(self) -> None:
        state = launch_test_state(target_owner=-1, target_ships=0, target_production=3)
        mission = candidate(
            2,
            launches=(LaunchCandidate(source_planet_id=1, angle=0.0, ships=1),),
        )
        state_before = copy.deepcopy(state)
        mission_before = copy.deepcopy(mission)

        evaluate_and_score_candidates(
            state,
            (mission,),
            evaluation_config=EvaluationConfig(horizon_ticks=1),
        )

        self.assertEqual(state, state_before)
        self.assertEqual(mission, mission_before)

    def test_evaluate_and_score_candidates_does_not_call_generation(self) -> None:
        with patch("ow_planner.candidates.generate_candidates") as generate:
            evaluate_and_score_candidates(
                launch_test_state(target_owner=-1, target_ships=0, target_production=3),
                (candidate(2),),
                evaluation_config=EvaluationConfig(horizon_ticks=1),
            )

        generate.assert_not_called()

    def test_evaluate_and_score_candidates_adds_no_ranking_or_selection_fields(self) -> None:
        (evaluation,) = evaluate_and_score_candidates(
            launch_test_state(target_owner=-1, target_ships=0, target_production=3),
            (candidate(2),),
            evaluation_config=EvaluationConfig(horizon_ticks=1),
        )

        self.assertFalse(hasattr(evaluation, "rank"))
        self.assertFalse(hasattr(evaluation, "selected"))

    def test_config_rejects_invalid_horizon_ticks(self) -> None:
        for horizon_ticks in (-1, True, 1.5, "3"):
            with self.subTest(horizon_ticks=horizon_ticks):
                with self.assertRaises(ValueError):
                    EvaluationConfig(horizon_ticks=horizon_ticks)

    def test_evaluate_candidates_does_not_mutate_state_or_candidates(self) -> None:
        state = state_with_planet()
        first = candidate(2)
        second = candidate(3, MissionType.ATTACK_ENEMY)
        state_before = copy.deepcopy(state)
        candidates_before = copy.deepcopy((first, second))

        evaluate_candidates(state, (first, second), EvaluationConfig(horizon_ticks=5))

        self.assertEqual(state, state_before)
        self.assertEqual((first, second), candidates_before)
        self.assertEqual(state.raw_observation, state_before.raw_observation)

    def test_no_launch_evaluation_does_not_call_generation_or_launch_helpers(self) -> None:
        mission = candidate(2, launches=())
        with (
            patch("ow_planner.candidates.generate_candidates") as generate,
            patch("ow_planner.evaluation.mission_candidate_to_orders") as action_convert,
            patch("ow_planner.outcomes.validate_estimated_pair_outcomes") as outcomes,
            patch("ow_planner.evaluation.simulate_ticks") as simulate_ticks,
            patch("ow_planner.evaluation.simulate_launch_orders") as simulate_launch_orders,
        ):
            evaluate_candidates(state_with_planet(), (mission,))

        generate.assert_not_called()
        action_convert.assert_not_called()
        outcomes.assert_not_called()
        simulate_ticks.assert_not_called()
        simulate_launch_orders.assert_not_called()

    def test_launch_evaluation_does_not_call_generation_or_outcome_helpers(self) -> None:
        with (
            patch("ow_planner.candidates.generate_candidates") as generate,
            patch("ow_planner.outcomes.validate_estimated_pair_outcomes") as outcomes,
        ):
            evaluate_candidates(launch_test_state(), (candidate(2),))

        generate.assert_not_called()
        outcomes.assert_not_called()

    def test_no_ranking_or_selection_behavior_is_introduced(self) -> None:
        evaluation = evaluate_candidates(state_with_planet(), (candidate(2),))[0]

        self.assertFalse(hasattr(evaluation, "rank"))
        self.assertFalse(hasattr(evaluation, "selected"))
        self.assertEqual(evaluation.score_components, ())
        self.assertIsNone(evaluation.total_score)


if __name__ == "__main__":
    unittest.main()
