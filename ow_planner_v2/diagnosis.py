"""Central board diagnosis for Planner V2."""

from __future__ import annotations

from ow_planner import (
    enemy_denial_opportunity_facts,
    four_player_plateau_facts,
    four_player_rank_facts,
    own_transfer_intent_facts,
    owned_production_threat_facts,
    strategy_mode_facts,
)
from ow_planner.strategy_modes import StrategyMode
from ow_sim.state import GameState

from .types import BoardDiagnosis, PlannerV2Mode


def diagnose_board(state: GameState) -> BoardDiagnosis:
    """Return a deterministic Planner V2 board diagnosis."""

    if not isinstance(state, GameState):
        raise ValueError("state must be a GameState")

    mode_facts = strategy_mode_facts(state)
    player_id = state.player_id
    owned_planets = tuple(
        planet for planet in state.planets if player_id is not None and planet.owner == player_id
    )
    opponent_planets = tuple(
        planet
        for planet in state.planets
        if player_id is not None and planet.owner >= 0 and planet.owner != player_id
    )
    neutral_planets = tuple(planet for planet in state.planets if planet.owner < 0)
    owned_fleets = tuple(
        fleet for fleet in state.fleets if player_id is not None and fleet.owner == player_id
    )
    threat_report = owned_production_threat_facts(state)
    transfer_report = own_transfer_intent_facts(state, threat_report=threat_report)
    denial_report = enemy_denial_opportunity_facts(state)
    plateau_report = four_player_plateau_facts(state)
    rank_report = four_player_rank_facts(
        state,
        declared_player_count=4 if mode_facts.mode is StrategyMode.FOUR_PLAYER else None,
    )

    mode = _planner_v2_mode(
        mode_facts.mode,
        mode_facts.player_count,
        owned_planet_count=len(owned_planets),
    )
    high_value_targets = _high_value_target_ids(
        denial_report=denial_report,
        rank_report=rank_report,
        neutral_planets=neutral_planets,
    )
    vulnerable_owned_planet_ids = tuple(
        facts.planet_id for facts in threat_report.planet_facts if facts.at_risk
    )
    pressure_magnitude = sum(
        facts.incoming_enemy_ships for facts in threat_report.planet_facts
    )
    source_drain_risk_planet_ids = _source_drain_risk_planet_ids(
        owned_planets=owned_planets,
        vulnerable_owned_planet_ids=vulnerable_owned_planet_ids,
    )
    pressure_labels = tuple(threat_report.labels)
    rank_labels = tuple(rank_report.labels)
    transfer_labels = tuple(transfer_report.labels)
    denial_labels = tuple(denial_report.labels)
    plateau_labels = tuple(plateau_report.labels)
    labels = _diagnosis_labels(
        mode=mode,
        owned_planet_count=len(owned_planets),
        owned_production=sum(planet.production for planet in owned_planets),
        pressure_labels=pressure_labels,
        rank_labels=rank_labels,
        transfer_labels=transfer_labels,
        denial_labels=denial_labels,
        plateau_labels=plateau_labels,
    )
    return BoardDiagnosis(
        mode=mode,
        player_id=player_id,
        active_player_ids=mode_facts.active_player_ids,
        opponent_player_ids=mode_facts.opponent_player_ids,
        owned_planet_count=len(owned_planets),
        owned_production=sum(planet.production for planet in owned_planets),
        owned_planet_ships=sum(planet.ships for planet in owned_planets),
        owned_fleet_ships=sum(fleet.ships for fleet in owned_fleets),
        opponent_production=sum(planet.production for planet in opponent_planets),
        opponent_planet_ships=sum(planet.ships for planet in opponent_planets),
        neutral_production=sum(planet.production for planet in neutral_planets),
        pressure_magnitude=pressure_magnitude,
        source_drain_risk_planet_ids=source_drain_risk_planet_ids,
        vulnerable_owned_planet_ids=vulnerable_owned_planet_ids,
        high_value_target_ids=high_value_targets,
        rank_labels=rank_labels,
        pressure_labels=pressure_labels,
        transfer_labels=transfer_labels,
        denial_labels=denial_labels,
        plateau_labels=plateau_labels,
        labels=labels,
    )


def _planner_v2_mode(
    mode: StrategyMode,
    active_player_count: int,
    *,
    owned_planet_count: int,
) -> PlannerV2Mode:
    if owned_planet_count == 0:
        return PlannerV2Mode.ENDGAME
    if mode is StrategyMode.TWO_PLAYER:
        return PlannerV2Mode.ENDGAME if active_player_count < 2 else PlannerV2Mode.TWO_PLAYER
    if mode is StrategyMode.FOUR_PLAYER:
        return PlannerV2Mode.FOUR_PLAYER
    if active_player_count <= 2:
        return PlannerV2Mode.ENDGAME
    return PlannerV2Mode.UNKNOWN


def _high_value_target_ids(
    *,
    denial_report,
    rank_report,
    neutral_planets,
) -> tuple[int, ...]:
    target_ids: list[int] = []
    for fact in getattr(denial_report, "opportunity_facts", ()):
        if getattr(fact, "high_value_denial_opportunity", False):
            target_ids.append(fact.target_planet_id)
    for fact in getattr(rank_report, "swing_target_facts", ()):
        if getattr(fact, "high_value_swing_target", False):
            target_ids.append(fact.target_planet_id)
    for planet in neutral_planets:
        if planet.production > 0:
            target_ids.append(planet.planet_id)
    return tuple(dict.fromkeys(target_ids))


def _diagnosis_labels(
    *,
    mode: PlannerV2Mode,
    owned_planet_count: int,
    owned_production: int,
    pressure_labels: tuple[str, ...],
    rank_labels: tuple[str, ...],
    transfer_labels: tuple[str, ...],
    denial_labels: tuple[str, ...],
    plateau_labels: tuple[str, ...],
) -> tuple[str, ...]:
    labels: list[str] = [mode.value]
    if owned_planet_count == 0:
        labels.append("source_less_no_owned_planets")
    if owned_production > 0:
        labels.append("owned_production_available")
    if mode is PlannerV2Mode.ENDGAME:
        labels.append("late_game_state")
    if pressure_labels:
        labels.append("pressure_visible")
    if rank_labels:
        labels.append("rank_context_visible")
    if transfer_labels:
        labels.append("own_transfer_context_visible")
    if denial_labels:
        labels.append("enemy_denial_context_visible")
    if plateau_labels:
        labels.append("four_player_plateau_context_visible")
    if owned_production > 0 and not pressure_labels and not denial_labels:
        labels.append("action_starvation_risk")
    return tuple(dict.fromkeys(labels))


def _source_drain_risk_planet_ids(
    *,
    owned_planets,
    vulnerable_owned_planet_ids: tuple[int, ...],
) -> tuple[int, ...]:
    vulnerable = set(vulnerable_owned_planet_ids)
    risk_ids: list[int] = []
    for planet in owned_planets:
        if planet.planet_id in vulnerable:
            risk_ids.append(planet.planet_id)
        elif planet.production > 0 and planet.ships <= max(3, planet.production * 2):
            risk_ids.append(planet.planet_id)
    return tuple(dict.fromkeys(risk_ids))


__all__ = ("diagnose_board",)
