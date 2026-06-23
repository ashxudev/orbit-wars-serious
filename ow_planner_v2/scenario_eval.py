"""Planner V2 scenario evaluation over existing simulator primitives."""

from __future__ import annotations

from collections.abc import Sequence

from ow_planner.actions import launch_candidate_to_order
from ow_sim.forecast import fleet_ticks_to_reach_distance
from ow_sim.geometry import angle_between, distance
from ow_sim.state import GameState, Planet
from ow_sim.timeline import simulate_ticks
from ow_sim.whatif import LaunchOrder, apply_launch_orders

from .types import (
    ActionSetPlan,
    BoardDiagnosis,
    PlannerV2Config,
    ScenarioEvaluation,
    ScenarioOutcome,
)


def evaluate_action_set_scenarios(
    state: GameState,
    action_sets: Sequence[ActionSetPlan],
    diagnosis: BoardDiagnosis,
    config: PlannerV2Config | None = None,
) -> tuple[ScenarioEvaluation, ...]:
    """Evaluate action sets against idle baselines for configured horizons."""

    if not isinstance(state, GameState):
        raise ValueError("state must be a GameState")
    effective_config = PlannerV2Config() if config is None else config
    horizons = _scenario_horizons(diagnosis, effective_config)
    idle_by_horizon = _rollout_by_horizon(state, horizons)
    return tuple(
        _evaluate_action_set(
            state,
            plan,
            diagnosis,
            horizons,
            idle_by_horizon,
        )
        for plan in action_sets
    )


def _evaluate_action_set(
    state: GameState,
    plan: ActionSetPlan,
    diagnosis: BoardDiagnosis,
    horizons: tuple[int, ...],
    idle_by_horizon: dict[int, GameState],
) -> ScenarioEvaluation:
    if not plan.launches:
        outcomes = tuple(
            ScenarioOutcome(
                horizon=horizon,
                valid=False,
                score=-10000.0,
                notes=("no_launches",),
            )
            for horizon in horizons
        )
        return ScenarioEvaluation(
            plan_id=plan.plan_id,
            outcomes=outcomes,
            valid=False,
            notes=("no launches",),
        )

    try:
        orders = _launch_orders_for_plan(state, plan)
    except Exception as exc:
        outcomes = tuple(
            ScenarioOutcome(
                horizon=horizon,
                valid=False,
                score=-10000.0,
                notes=(f"invalid_launch:{type(exc).__name__}:{exc}",),
            )
            for horizon in horizons
        )
        return ScenarioEvaluation(
            plan_id=plan.plan_id,
            outcomes=outcomes,
            valid=False,
            notes=("invalid launch",),
        )

    try:
        launched_state = apply_launch_orders(state, orders)
        action_by_horizon = _rollout_by_horizon(launched_state, horizons)
        response_orders = _enemy_response_orders(
            launched_state,
            plan,
            player_id=state.player_id,
            max_horizon=max(horizons, default=0),
        )
        response_by_horizon = (
            {}
            if not response_orders
            else _rollout_by_horizon(
                apply_launch_orders(launched_state, response_orders),
                horizons,
            )
        )
    except Exception as exc:
        outcomes = tuple(
            ScenarioOutcome(
                horizon=horizon,
                valid=False,
                score=-10000.0,
                notes=(f"simulation_error:{type(exc).__name__}:{exc}",),
            )
            for horizon in horizons
        )
        return ScenarioEvaluation(
            plan_id=plan.plan_id,
            outcomes=outcomes,
            valid=False,
            notes=("simulation error",),
        )

    outcomes = tuple(
        _scenario_outcome(
            state,
            plan,
            diagnosis,
            idle_by_horizon[horizon],
            action_by_horizon[horizon],
            response_by_horizon.get(horizon),
            horizon,
        )
        for horizon in horizons
    )
    return ScenarioEvaluation(
        plan_id=plan.plan_id,
        outcomes=outcomes,
        valid=any(outcome.valid for outcome in outcomes),
    )


def _launch_orders_for_plan(
    state: GameState,
    plan: ActionSetPlan,
) -> tuple[LaunchOrder, ...]:
    remaining = {
        planet.planet_id: planet.ships
        for planet in state.planets
    }
    orders: list[LaunchOrder] = []
    for launch in plan.launches:
        order = launch_candidate_to_order(state, launch)
        if remaining.get(order.source_planet_id, 0) < order.ships:
            raise ValueError("source planet does not have enough ships")
        remaining[order.source_planet_id] -= order.ships
        orders.append(order)
    return tuple(orders)


def _scenario_outcome(
    state: GameState,
    plan: ActionSetPlan,
    diagnosis: BoardDiagnosis,
    idle_state: GameState,
    action_state: GameState,
    response_state: GameState | None,
    horizon: int,
) -> ScenarioOutcome:
    player_id = state.player_id
    if player_id is None:
        return ScenarioOutcome(
            horizon=horizon,
            valid=False,
            score=-10000.0,
            notes=("missing_player_id",),
        )
    target_ids = tuple(
        dict.fromkeys(
            mission.target_planet_id
            for mission in plan.missions
            if mission.target_planet_id is not None
        )
    )
    source_ids = tuple(dict.fromkeys(launch.source_planet_id for launch in plan.launches))
    vulnerable_ids = diagnosis.vulnerable_owned_planet_ids
    idle_stats = _player_stats(idle_state, player_id)
    action_stats = _player_stats(action_state, player_id)
    idle_opponent_production = _opponent_production(idle_state, player_id)
    action_opponent_production = _opponent_production(action_state, player_id)
    source_lost_ids = _lost_planet_ids(action_state, source_ids, player_id)
    vulnerable_lost_ids = _lost_planet_ids(action_state, vulnerable_ids, player_id)
    source_lost_production = _planet_production_sum(state, source_lost_ids)
    vulnerable_lost_production = _planet_production_sum(state, vulnerable_lost_ids)
    source_counterattack_lost_ids = _response_lost_planet_ids(
        action_state,
        response_state,
        source_ids,
        player_id,
    )
    target_hold_failure_ids = _response_lost_planet_ids(
        action_state,
        response_state,
        target_ids,
        player_id,
    )
    source_counterattack_lost_production = _planet_production_sum(
        state,
        source_counterattack_lost_ids,
    )
    target_hold_failure_production = _planet_production_sum(
        state,
        target_hold_failure_ids,
    )
    target_owned_count = sum(
        1
        for target_id in target_ids
        if _planet_owner(action_state, target_id) == player_id
    )
    own_production_delta = action_stats.production - idle_stats.production
    own_planet_delta = action_stats.planet_count - idle_stats.planet_count
    own_ship_delta = action_stats.total_ships - idle_stats.total_ships
    opponent_production_delta = action_opponent_production - idle_opponent_production
    eliminated = action_stats.planet_count == 0 and action_stats.fleet_ships == 0
    score = _scenario_score(
        own_production_delta=own_production_delta,
        own_planet_delta=own_planet_delta,
        own_ship_delta=own_ship_delta,
        opponent_production_delta=opponent_production_delta,
        target_owned_count=target_owned_count,
        source_lost_count=len(source_lost_ids),
        source_lost_production=source_lost_production,
        source_counterattack_lost_count=len(source_counterattack_lost_ids),
        source_counterattack_lost_production=source_counterattack_lost_production,
        target_hold_failure_count=len(target_hold_failure_ids),
        target_hold_failure_production=target_hold_failure_production,
        vulnerable_lost_count=len(vulnerable_lost_ids),
        vulnerable_lost_production=vulnerable_lost_production,
        eliminated=eliminated,
        ships_committed=sum(launch.ships for launch in plan.launches),
    )
    return ScenarioOutcome(
        horizon=horizon,
        valid=True,
        score=score,
        own_production_delta=own_production_delta,
        own_planet_delta=own_planet_delta,
        own_planet_count=action_stats.planet_count,
        own_ship_delta=own_ship_delta,
        own_production=action_stats.production,
        opponent_production_delta=opponent_production_delta,
        idle_own_planet_count=idle_stats.planet_count,
        idle_own_production=idle_stats.production,
        target_owned_by_player_count=target_owned_count,
        target_planet_ids=target_ids,
        source_planet_lost_ids=source_lost_ids,
        source_planet_lost_production=source_lost_production,
        source_counterattack_lost_ids=source_counterattack_lost_ids,
        source_counterattack_lost_production=source_counterattack_lost_production,
        target_hold_failure_ids=target_hold_failure_ids,
        target_hold_failure_production=target_hold_failure_production,
        vulnerable_planet_lost_ids=vulnerable_lost_ids,
        vulnerable_planet_lost_production=vulnerable_lost_production,
        eliminated=eliminated,
        notes=_outcome_notes(
            eliminated=eliminated,
            source_lost_ids=source_lost_ids,
            source_counterattack_lost_ids=source_counterattack_lost_ids,
            target_hold_failure_ids=target_hold_failure_ids,
            vulnerable_lost_ids=vulnerable_lost_ids,
            own_production_delta=own_production_delta,
            own_planet_delta=own_planet_delta,
            opponent_production_delta=opponent_production_delta,
        ),
    )


def _scenario_score(
    *,
    own_production_delta: int,
    own_planet_delta: int,
    own_ship_delta: int,
    opponent_production_delta: int,
    target_owned_count: int,
    source_lost_count: int,
    source_lost_production: int,
    source_counterattack_lost_count: int,
    source_counterattack_lost_production: int,
    target_hold_failure_count: int,
    target_hold_failure_production: int,
    vulnerable_lost_count: int,
    vulnerable_lost_production: int,
    eliminated: bool,
    ships_committed: int,
) -> float:
    score = 0.0
    score += own_production_delta * 80.0
    score += own_planet_delta * 45.0
    score += -opponent_production_delta * 45.0
    score += target_owned_count * 18.0
    score += own_ship_delta * 0.25
    score -= source_lost_count * 140.0
    score -= source_lost_production * 35.0
    score -= source_counterattack_lost_count * 160.0
    score -= source_counterattack_lost_production * 55.0
    score -= target_hold_failure_count * 100.0
    score -= target_hold_failure_production * 35.0
    score -= vulnerable_lost_count * 180.0
    score -= vulnerable_lost_production * 45.0
    score -= ships_committed * 0.2
    if eliminated:
        score -= 1000.0
    return score


def _outcome_notes(
    *,
    eliminated: bool,
    source_lost_ids: tuple[int, ...],
    source_counterattack_lost_ids: tuple[int, ...],
    target_hold_failure_ids: tuple[int, ...],
    vulnerable_lost_ids: tuple[int, ...],
    own_production_delta: int,
    own_planet_delta: int,
    opponent_production_delta: int,
) -> tuple[str, ...]:
    notes: list[str] = []
    if eliminated:
        notes.append("eliminated")
    if source_lost_ids:
        notes.append("source_planet_lost")
    if source_counterattack_lost_ids:
        notes.append("source_counterattack_lost")
    if target_hold_failure_ids:
        notes.append("target_hold_failure")
    if vulnerable_lost_ids:
        notes.append("vulnerable_planet_lost")
    if own_production_delta > 0:
        notes.append("own_production_gain")
    elif own_production_delta < 0:
        notes.append("own_production_loss")
    if own_planet_delta > 0:
        notes.append("own_planet_gain")
    elif own_planet_delta < 0:
        notes.append("own_planet_loss")
    if opponent_production_delta < 0:
        notes.append("opponent_production_denied")
    return tuple(notes)


def _scenario_horizons(
    diagnosis: BoardDiagnosis,
    config: PlannerV2Config,
) -> tuple[int, ...]:
    horizons = list(config.horizons)
    if diagnosis.mode.value == "endgame" or "late_game_state" in diagnosis.labels:
        horizons.append(config.endgame_horizon)
    return tuple(dict.fromkeys(horizons))


def _rollout_by_horizon(
    state: GameState,
    horizons: tuple[int, ...],
) -> dict[int, GameState]:
    current = state
    current_horizon = 0
    states: dict[int, GameState] = {}
    for horizon in sorted(horizons):
        current = simulate_ticks(current, horizon - current_horizon)
        current_horizon = horizon
        states[horizon] = current
    return states


def _enemy_response_orders(
    state: GameState,
    plan: ActionSetPlan,
    *,
    player_id: int | None,
    max_horizon: int,
) -> tuple[LaunchOrder, ...]:
    if player_id is None or max_horizon <= 0:
        return ()
    guarded_ids = tuple(
        dict.fromkeys(
            (
                *(launch.source_planet_id for launch in plan.launches),
                *(
                    mission.target_planet_id
                    for mission in plan.missions
                    if mission.target_planet_id is not None
                ),
            )
        )
    )
    if not guarded_ids:
        return ()
    enemy_sources = tuple(
        sorted(
            (
                planet
                for planet in state.planets
                if planet.owner >= 0
                and planet.owner != player_id
                and planet.ships > 1
            ),
            key=lambda planet: (-planet.production, -planet.ships, planet.planet_id),
        )
    )
    if not enemy_sources:
        return ()

    orders: list[LaunchOrder] = []
    used_source_ids: set[int] = set()
    for target_id in guarded_ids:
        target = _planet_by_id(state, target_id)
        if target is None:
            continue
        option = _best_enemy_response_option(
            enemy_sources,
            target,
            used_source_ids=used_source_ids,
            max_horizon=max_horizon,
        )
        if option is None:
            continue
        source, ships = option
        used_source_ids.add(source.planet_id)
        orders.append(
            LaunchOrder(
                source_planet_id=source.planet_id,
                angle=angle_between(source.position, target.position),
                ships=ships,
                player_id=source.owner,
            )
        )
    return tuple(orders)


def _best_enemy_response_option(
    enemy_sources: Sequence[Planet],
    target: Planet,
    *,
    used_source_ids: set[int],
    max_horizon: int,
) -> tuple[Planet, int] | None:
    options: list[tuple[int, float, int, int, Planet, int]] = []
    for source in enemy_sources:
        if source.planet_id in used_source_ids or source.planet_id == target.planet_id:
            continue
        ships = source.ships - 1
        if ships <= 0:
            continue
        travel_distance = max(
            0.0,
            distance(source.position, target.position) - target.radius,
        )
        travel_ticks = fleet_ticks_to_reach_distance(travel_distance, ships)
        if travel_ticks > max_horizon:
            continue
        options.append(
            (
                travel_ticks,
                distance(source.position, target.position),
                -ships,
                source.planet_id,
                source,
                ships,
            )
        )
    if not options:
        return None
    _travel_ticks, _distance, _neg_ships, _planet_id, source, ships = min(options)
    return source, ships


class _PlayerStats(tuple):
    __slots__ = ()

    @property
    def planet_count(self) -> int:
        return self[0]

    @property
    def production(self) -> int:
        return self[1]

    @property
    def planet_ships(self) -> int:
        return self[2]

    @property
    def fleet_ships(self) -> int:
        return self[3]

    @property
    def total_ships(self) -> int:
        return self.planet_ships + self.fleet_ships


def _player_stats(state: GameState, player_id: int) -> _PlayerStats:
    planets = tuple(planet for planet in state.planets if planet.owner == player_id)
    fleets = tuple(fleet for fleet in state.fleets if fleet.owner == player_id)
    return _PlayerStats(
        (
            len(planets),
            sum(planet.production for planet in planets),
            sum(planet.ships for planet in planets),
            sum(fleet.ships for fleet in fleets),
        )
    )


def _opponent_production(state: GameState, player_id: int) -> int:
    return sum(
        planet.production
        for planet in state.planets
        if planet.owner >= 0 and planet.owner != player_id
    )


def _lost_planet_ids(
    state: GameState,
    planet_ids: Sequence[int],
    player_id: int,
) -> tuple[int, ...]:
    lost = []
    for planet_id in planet_ids:
        owner = _planet_owner(state, planet_id)
        if owner is not None and owner != player_id:
            lost.append(planet_id)
    return tuple(lost)


def _response_lost_planet_ids(
    action_state: GameState,
    response_state: GameState | None,
    planet_ids: Sequence[int],
    player_id: int,
) -> tuple[int, ...]:
    if response_state is None:
        return ()
    lost = []
    for planet_id in dict.fromkeys(planet_ids):
        if (
            _planet_owner(action_state, planet_id) == player_id
            and _planet_owner(response_state, planet_id) != player_id
        ):
            lost.append(planet_id)
    return tuple(lost)


def _planet_production_sum(state: GameState, planet_ids: Sequence[int]) -> int:
    target_ids = set(planet_ids)
    return sum(
        planet.production
        for planet in state.planets
        if planet.planet_id in target_ids
    )


def _planet_owner(state: GameState, planet_id: int) -> int | None:
    planet = _planet_by_id(state, planet_id)
    return None if planet is None else planet.owner


def _planet_by_id(state: GameState, planet_id: int) -> Planet | None:
    for planet in state.planets:
        if planet.planet_id == planet_id:
            return planet
    return None


__all__ = ("evaluate_action_set_scenarios",)
