"""Planner V2 mission-surface candidate generation.

This module creates bounded V2-only candidates when the legacy candidate
surface misses obvious productive responses. The candidates still flow through
the existing evaluation, commitment, strategy, and action-conversion contracts.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from ow_planner import (
    CandidateOutcome,
    LaunchCandidate,
    MissionCandidate,
    MissionType,
)
from ow_sim.geometry import angle_between, distance
from ow_sim.state import GameState, Planet

from .diagnosis import diagnose_board
from .trajectory import diagnose_trajectory
from .types import BoardDiagnosis, PlannerV2Config, PlannerV2Mode


def generate_surface_candidates(
    state: GameState,
    existing_candidates: Sequence[MissionCandidate] = (),
    config: PlannerV2Config | None = None,
    diagnosis: BoardDiagnosis | None = None,
) -> tuple[MissionCandidate, ...]:
    """Return bounded V2 mission-surface candidates for ``state``.

    Existing candidates remain the primary surface. V2 candidates fill missing
    mission families such as urgent defense, enemy production denial, rank
    pressure, and safe continuation. Stable ordering and dedupe keep the output
    deterministic.
    """

    effective_config = PlannerV2Config() if config is None else config
    if effective_config.max_surface_candidates == 0:
        return ()
    if state.player_id is None:
        return ()

    effective_diagnosis = diagnose_board(state) if diagnosis is None else diagnosis
    trajectory = diagnose_trajectory(state)
    candidates: list[MissionCandidate] = []
    existing_keys = _candidate_keys(existing_candidates)

    def append(candidate: MissionCandidate | None) -> None:
        if candidate is None:
            return
        key = _candidate_key(candidate)
        if key in existing_keys:
            return
        if key in _candidate_keys(candidates):
            return
        candidates.append(candidate)

    if effective_config.enable_trajectory_second_source:
        for candidate in _trajectory_second_source_candidates(state, trajectory):
            append(candidate)
            if _surface_limit_reached(candidates, effective_config):
                return tuple(candidates)

    for candidate in _urgent_defense_candidates(state, effective_diagnosis):
        append(candidate)
        if _surface_limit_reached(candidates, effective_config):
            return tuple(candidates)

    if (
        effective_config.enable_trajectory_continuation
        and effective_diagnosis.mode is PlannerV2Mode.FOUR_PLAYER
    ):
        for candidate in _trajectory_preservation_candidates(state, trajectory):
            append(candidate)
            if _surface_limit_reached(candidates, effective_config):
                return tuple(candidates)

    for candidate in _safe_continuation_candidates(state, effective_diagnosis):
        append(candidate)
        if _surface_limit_reached(candidates, effective_config):
            return tuple(candidates)

    for candidate in _enemy_denial_candidates(state, effective_diagnosis):
        append(candidate)
        if _surface_limit_reached(candidates, effective_config):
            return tuple(candidates)

    return tuple(candidates)


def _urgent_defense_candidates(
    state: GameState,
    diagnosis: BoardDiagnosis,
) -> tuple[MissionCandidate, ...]:
    player_id = state.player_id
    if player_id is None:
        return ()
    owned = _owned_planets(state, player_id)
    if len(owned) < 2:
        return ()
    target_ids = list(diagnosis.vulnerable_owned_planet_ids)
    if not target_ids and (
        diagnosis.pressure_magnitude > 0
        or "pressure_visible" in diagnosis.labels
        or diagnosis.owned_planet_count <= 4
    ):
        target_ids = [
            planet.planet_id
            for planet in sorted(
                (planet for planet in owned if planet.production > 0),
                key=lambda planet: (planet.ships, -planet.production, planet.planet_id),
            )[:2]
        ]
    candidates: list[MissionCandidate] = []
    for target_id in target_ids:
        target = _planet_by_id(state, target_id)
        if target is None or target.owner != player_id:
            continue
        source = _best_source_for_target(
            owned,
            target,
            exclude_target=True,
            prefer_production_safe=True,
        )
        if source is None:
            continue
        ships = _reserve_send_ships(
            source,
            desired=max(2, target.production * 2, min(source.ships - 1, 6)),
        )
        if ships <= 0:
            continue
        launch = _launch_between(source, target, ships, player_id)
        candidates.append(
            MissionCandidate(
                mission_type=MissionType.REINFORCE,
                target_planet_id=target.planet_id,
                source_planet_ids=(source.planet_id,),
                launches=(launch,),
                outcome=CandidateOutcome.VALIDATED,
                note="planner_v2_surface:urgent_defense",
            )
        )
    return tuple(candidates)


def _trajectory_preservation_candidates(
    state: GameState,
    trajectory,
) -> tuple[MissionCandidate, ...]:
    player_id = state.player_id
    if player_id is None:
        return ()
    target_ids = tuple(trajectory.preservation_target_planet_ids)
    if not target_ids:
        return ()
    owned = _owned_planets(state, player_id)
    candidates: list[MissionCandidate] = []
    for target_id in target_ids[:3]:
        target = _planet_by_id(state, target_id)
        if target is None or target.owner != player_id:
            continue
        source = _best_source_for_target(
            owned,
            target,
            exclude_target=True,
            prefer_production_safe=True,
        )
        if source is None:
            continue
        deficit = _source_reserve_floor(target) - target.ships
        ships = _reserve_send_ships(
            source,
            desired=max(2, deficit, target.production * 2),
        )
        if ships <= 0:
            continue
        launch = _launch_between(source, target, ships, player_id)
        candidates.append(
            MissionCandidate(
                mission_type=MissionType.REINFORCE,
                target_planet_id=target.planet_id,
                source_planet_ids=(source.planet_id,),
                launches=(launch,),
                outcome=CandidateOutcome.VALIDATED,
                note="planner_v2_surface:trajectory_preserve_source",
            )
        )
    return tuple(candidates)


def _trajectory_second_source_candidates(
    state: GameState,
    trajectory,
) -> tuple[MissionCandidate, ...]:
    player_id = state.player_id
    if player_id is None:
        return ()
    objectives = {
        objective.value for objective in trajectory.recommended_objectives
    }
    if not (
        "secure_second_source" in objectives
        or "capture_nearest_productive_neutral" in objectives
    ):
        return ()
    owned = _owned_planets(state, player_id)
    if not owned:
        return ()
    targets = _ordered_neutral_targets(state, player_id)
    candidates: list[MissionCandidate] = []
    for target in targets[:4]:
        source = _source_preserving_source_for_target(owned, target)
        if source is None:
            continue
        ships = _source_preserving_capture_ships(source, target)
        if ships <= 0:
            continue
        launch = _launch_between(source, target, ships, player_id)
        candidates.append(
            MissionCandidate(
                mission_type=MissionType.CAPTURE_NEUTRAL,
                target_planet_id=target.planet_id,
                source_planet_ids=(source.planet_id,),
                launches=(launch,),
                outcome=CandidateOutcome.VALIDATED,
                note="planner_v2_surface:trajectory_second_source",
            )
        )
    return tuple(candidates)


def _enemy_denial_candidates(
    state: GameState,
    diagnosis: BoardDiagnosis,
) -> tuple[MissionCandidate, ...]:
    player_id = state.player_id
    if player_id is None:
        return ()
    owned = _owned_planets(state, player_id)
    if not owned:
        return ()
    targets = _ordered_enemy_targets(state, diagnosis, player_id)
    candidates: list[MissionCandidate] = []
    for target in targets[:4]:
        source = _best_source_for_target(owned, target)
        if source is None:
            continue
        ships = _target_send_ships(source, target)
        if ships <= 0:
            continue
        launch = _launch_between(source, target, ships, player_id)
        mission_type = (
            MissionType.CAPTURE_NEUTRAL
            if target.owner < 0
            else MissionType.ATTACK_ENEMY
        )
        candidates.append(
            MissionCandidate(
                mission_type=mission_type,
                target_planet_id=target.planet_id,
                source_planet_ids=(source.planet_id,),
                launches=(launch,),
                outcome=CandidateOutcome.VALIDATED,
                note=(
                    "planner_v2_surface:safe_expand"
                    if target.owner < 0
                    else "planner_v2_surface:enemy_denial"
                ),
            )
        )
    return tuple(candidates)


def _safe_continuation_candidates(
    state: GameState,
    diagnosis: BoardDiagnosis,
) -> tuple[MissionCandidate, ...]:
    player_id = state.player_id
    if player_id is None:
        return ()
    owned = _owned_planets(state, player_id)
    if not owned:
        return ()
    targets = _ordered_neutral_targets(state, player_id)
    if not targets:
        targets = _ordered_enemy_targets(state, diagnosis, player_id)
    candidates: list[MissionCandidate] = []
    for target in targets[:4]:
        source = _best_source_for_target(owned, target)
        if source is None:
            continue
        ships = _target_send_ships(source, target)
        if ships <= 0:
            continue
        mission_type = (
            MissionType.CAPTURE_NEUTRAL
            if target.owner < 0
            else MissionType.ATTACK_ENEMY
        )
        launch = _launch_between(source, target, ships, player_id)
        candidates.append(
            MissionCandidate(
                mission_type=mission_type,
                target_planet_id=target.planet_id,
                source_planet_ids=(source.planet_id,),
                launches=(launch,),
                outcome=CandidateOutcome.VALIDATED,
                note="planner_v2_surface:safe_continuation",
            )
        )
    return tuple(candidates)


def _owned_planets(state: GameState, player_id: int) -> tuple[Planet, ...]:
    return tuple(
        sorted(
            (planet for planet in state.planets if planet.owner == player_id),
            key=lambda planet: planet.planet_id,
        )
    )


def _ordered_enemy_targets(
    state: GameState,
    diagnosis: BoardDiagnosis,
    player_id: int,
) -> tuple[Planet, ...]:
    high_value = set(diagnosis.high_value_target_ids)
    targets = tuple(
        planet
        for planet in state.planets
        if planet.owner >= 0 and planet.owner != player_id and not planet.is_comet
    )
    return tuple(
        sorted(
            targets,
            key=lambda planet: (
                0 if planet.planet_id in high_value else 1,
                -planet.production,
                planet.ships,
                planet.planet_id,
            ),
        )
    )


def _ordered_neutral_targets(state: GameState, player_id: int) -> tuple[Planet, ...]:
    del player_id
    targets = tuple(
        planet
        for planet in state.planets
        if planet.owner < 0 and planet.production > 0 and not planet.is_comet
    )
    return tuple(
        sorted(
            targets,
            key=lambda planet: (-planet.production, planet.ships, planet.planet_id),
        )
    )


def _best_source_for_target(
    owned: Sequence[Planet],
    target: Planet,
    *,
    exclude_target: bool = False,
    prefer_production_safe: bool = False,
) -> Planet | None:
    sources = tuple(
        planet
        for planet in owned
        if (not exclude_target or planet.planet_id != target.planet_id)
        and planet.ships > 1
    )
    if not sources:
        return None
    return min(
        sources,
        key=lambda planet: (
            0 if not prefer_production_safe or planet.production == 0 else 1,
            distance(planet.position, target.position),
            -planet.ships,
            planet.planet_id,
        ),
    )


def _reserve_send_ships(source: Planet, *, desired: int) -> int:
    capacity = max(0, source.ships - 1)
    if capacity <= 0:
        return 0
    return max(1, min(capacity, desired))


def _target_send_ships(source: Planet, target: Planet) -> int:
    capacity = max(0, source.ships - 1)
    if capacity <= 0:
        return 0
    capture_need = max(1, target.ships + 1)
    if capacity >= capture_need:
        return capture_need
    if capacity >= 3:
        return max(2, capacity // 2)
    return capacity


def _source_preserving_source_for_target(
    owned: Sequence[Planet],
    target: Planet,
) -> Planet | None:
    candidates = tuple(
        planet for planet in owned if _source_preserving_capture_ships(planet, target) > 0
    )
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda planet: (
            0 if planet.production > 0 else 1,
            distance(planet.position, target.position),
            -planet.ships,
            planet.planet_id,
        ),
    )


def _source_preserving_capture_ships(source: Planet, target: Planet) -> int:
    reserve = max(3, source.production * 2 + 1)
    capture_need = max(1, target.ships + 1)
    if source.ships - capture_need < reserve:
        return 0
    return capture_need


def _source_reserve_floor(planet: Planet) -> int:
    return max(3, planet.production * 2 + 1)


def _launch_between(
    source: Planet,
    target: Planet,
    ships: int,
    player_id: int,
) -> LaunchCandidate:
    return LaunchCandidate(
        source_planet_id=source.planet_id,
        angle=angle_between(source.position, target.position),
        ships=ships,
        player_id=player_id,
    )


def _planet_by_id(state: GameState, planet_id: int) -> Planet | None:
    for planet in state.planets:
        if planet.planet_id == planet_id:
            return planet
    return None


def _surface_limit_reached(
    candidates: Sequence[MissionCandidate],
    config: PlannerV2Config,
) -> bool:
    return (
        config.max_surface_candidates is not None
        and len(candidates) >= config.max_surface_candidates
    )


def _candidate_keys(
    candidates: Iterable[MissionCandidate],
) -> set[tuple[object, ...]]:
    return {_candidate_key(candidate) for candidate in candidates}


def _candidate_key(candidate: MissionCandidate) -> tuple[object, ...]:
    return (
        candidate.mission_type.value,
        candidate.target_planet_id,
        tuple(
            (launch.source_planet_id, launch.ships)
            for launch in candidate.launches
        ),
    )


__all__ = ("generate_surface_candidates",)
