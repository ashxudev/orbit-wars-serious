"""Planner V2 strategic trajectory diagnosis.

The trajectory layer is intentionally facts-first. It explains whether an
early position is already on a fragile production curve before the one-turn
mission/search selector tries to choose an action.
"""

from __future__ import annotations

from collections.abc import Sequence

from ow_sim.geometry import distance
from ow_sim.state import GameState, Planet

from .types import TrajectoryDiagnosis, TrajectoryObjective, TrajectoryPhase


def diagnose_trajectory(state: GameState) -> TrajectoryDiagnosis:
    """Return deterministic trajectory facts for ``state``."""

    if not isinstance(state, GameState):
        raise ValueError("state must be a GameState")
    player_id = state.player_id
    turn = state.tick
    owned = _owned_planets(state, player_id)
    owned_production_planets = tuple(planet for planet in owned if planet.production > 0)
    owned_ships = sum(planet.ships for planet in owned)
    owned_fleet_ships = sum(
        fleet.ships for fleet in state.fleets if player_id is not None and fleet.owner == player_id
    )
    neutral_targets = _nearest_productive_neutrals(state, owned)
    opponent_production_by_player = _opponent_production_by_player(state, player_id)
    leader_production = max(opponent_production_by_player, default=0)
    owned_production = sum(planet.production for planet in owned)
    second_source_secured = len(owned_production_planets) >= 2
    best_neutral_production = max(
        (planet.production for planet, _dist in neutral_targets),
        default=0,
    )
    single_source_fragile = (
        len(owned_production_planets) == 1
        and owned_production > 0
        and _turn_value(turn) <= 60
    )
    source_drain_risk = any(
        planet.production > 0 and planet.ships <= _source_reserve_floor(planet)
        for planet in owned
    )
    expansion_deficit = _expansion_deficit(
        turn=turn,
        owned_production_planet_count=len(owned_production_planets),
        owned_production=owned_production,
        best_neutral_production=best_neutral_production,
    )
    production_gap_to_leader = max(0, leader_production - owned_production)
    objectives = _recommended_objectives(
        turn=turn,
        owned=owned,
        owned_production_planets=owned_production_planets,
        best_neutral_production=best_neutral_production,
        second_source_secured=second_source_secured,
        single_source_fragile=single_source_fragile,
        source_drain_risk=source_drain_risk,
        expansion_deficit=expansion_deficit,
        production_gap_to_leader=production_gap_to_leader,
    )
    labels = _trajectory_labels(
        owned_planet_count=len(owned),
        owned_production=owned_production,
        second_source_secured=second_source_secured,
        single_source_fragile=single_source_fragile,
        source_drain_risk=source_drain_risk,
        expansion_deficit=expansion_deficit,
        production_gap_to_leader=production_gap_to_leader,
        objectives=objectives,
    )
    return TrajectoryDiagnosis(
        turn=turn,
        phase=_phase(turn, owned),
        player_id=player_id,
        owned_planet_count=len(owned),
        owned_production=owned_production,
        owned_ships=owned_ships,
        owned_fleet_ships=owned_fleet_ships,
        best_neutral_production_available=best_neutral_production,
        nearest_productive_neutral_ids=tuple(
            planet.planet_id for planet, _dist in neutral_targets[:3]
        ),
        nearest_productive_neutral_distances=tuple(
            dist for _planet, dist in neutral_targets[:3]
        ),
        second_source_secured=second_source_secured,
        single_source_fragile=single_source_fragile,
        source_drain_risk=source_drain_risk,
        expansion_deficit=expansion_deficit,
        production_gap_to_leader=production_gap_to_leader,
        recommended_objectives=objectives,
        labels=labels,
    )


def _owned_planets(state: GameState, player_id: int | None) -> tuple[Planet, ...]:
    if player_id is None:
        return ()
    return tuple(
        sorted(
            (planet for planet in state.planets if planet.owner == player_id),
            key=lambda planet: planet.planet_id,
        )
    )


def _nearest_productive_neutrals(
    state: GameState,
    owned: Sequence[Planet],
) -> tuple[tuple[Planet, float], ...]:
    neutrals = tuple(
        planet
        for planet in state.planets
        if planet.owner < 0 and planet.production > 0 and not planet.is_comet
    )
    if not neutrals:
        return ()
    if not owned:
        return tuple(
            sorted(
                ((planet, float("inf")) for planet in neutrals),
                key=lambda item: (-item[0].production, item[0].ships, item[0].planet_id),
            )
        )
    return tuple(
        sorted(
            (
                (planet, min(distance(source.position, planet.position) for source in owned))
                for planet in neutrals
            ),
            key=lambda item: (
                item[1],
                -item[0].production,
                item[0].ships,
                item[0].planet_id,
            ),
        )
    )


def _opponent_production_by_player(
    state: GameState,
    player_id: int | None,
) -> tuple[int, ...]:
    totals: dict[int, int] = {}
    for planet in state.planets:
        if planet.owner < 0 or planet.owner == player_id:
            continue
        totals[planet.owner] = totals.get(planet.owner, 0) + planet.production
    return tuple(totals[player] for player in sorted(totals))


def _phase(turn: int | None, owned: Sequence[Planet]) -> TrajectoryPhase:
    if not owned:
        return TrajectoryPhase.TERMINAL
    value = _turn_value(turn)
    if value <= 10:
        return TrajectoryPhase.OPENING
    if value <= 60:
        return TrajectoryPhase.EARLY_BASE
    return TrajectoryPhase.MIDGAME


def _turn_value(turn: int | None) -> int:
    return -1 if turn is None else turn


def _source_reserve_floor(planet: Planet) -> int:
    return max(3, planet.production * 2 + 1)


def _expansion_deficit(
    *,
    turn: int | None,
    owned_production_planet_count: int,
    owned_production: int,
    best_neutral_production: int,
) -> int:
    value = _turn_value(turn)
    expected_sources = 1
    if value >= 20:
        expected_sources = 2
    if value >= 40:
        expected_sources = 2 if owned_production >= 2 else 3
    if best_neutral_production <= 0:
        expected_sources = min(expected_sources, max(1, owned_production_planet_count))
    return max(0, expected_sources - owned_production_planet_count)


def _recommended_objectives(
    *,
    turn: int | None,
    owned: Sequence[Planet],
    owned_production_planets: Sequence[Planet],
    best_neutral_production: int,
    second_source_secured: bool,
    single_source_fragile: bool,
    source_drain_risk: bool,
    expansion_deficit: int,
    production_gap_to_leader: int,
) -> tuple[TrajectoryObjective, ...]:
    del turn, owned
    objectives: list[TrajectoryObjective] = []
    if expansion_deficit > 0 or (not second_source_secured and best_neutral_production > 0):
        objectives.append(TrajectoryObjective.SECURE_SECOND_SOURCE)
        objectives.append(TrajectoryObjective.CAPTURE_NEAREST_PRODUCTIVE_NEUTRAL)
    if single_source_fragile or source_drain_risk:
        objectives.append(TrajectoryObjective.PRESERVE_PRIMARY_SOURCE)
    if not second_source_secured and best_neutral_production > 0:
        objectives.append(TrajectoryObjective.DELAY_ENEMY_DENIAL_UNTIL_BASE_SECURED)
    if second_source_secured and production_gap_to_leader > 0:
        objectives.append(TrajectoryObjective.DENY_AFTER_STABILIZING)
    if len(owned_production_planets) >= 2 and source_drain_risk:
        objectives.append(TrajectoryObjective.HOLD_RECENT_CAPTURE)
    return tuple(dict.fromkeys(objectives))


def _trajectory_labels(
    *,
    owned_planet_count: int,
    owned_production: int,
    second_source_secured: bool,
    single_source_fragile: bool,
    source_drain_risk: bool,
    expansion_deficit: int,
    production_gap_to_leader: int,
    objectives: Sequence[TrajectoryObjective],
) -> tuple[str, ...]:
    labels: list[str] = []
    if owned_planet_count == 0:
        labels.append("locally_unrecoverable_terminal")
    if expansion_deficit > 0:
        labels.append("under_expanded")
    if single_source_fragile:
        labels.append("single_source_fragile")
    if source_drain_risk:
        labels.append("source_drained")
    if (
        not second_source_secured
        and owned_production > 0
        and TrajectoryObjective.DELAY_ENEMY_DENIAL_UNTIL_BASE_SECURED in objectives
    ):
        labels.append("late_denial_before_base")
    if production_gap_to_leader > 0:
        labels.append("production_gap_to_leader")
    if second_source_secured:
        labels.append("second_source_secured")
    return tuple(dict.fromkeys(labels))


__all__ = ("diagnose_trajectory",)
