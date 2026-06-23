"""Deterministic metrics extraction from official match replays.

Evaluation Harness Cycle 5 turns one official ``env.toJSON()`` payload into
the existing ``MatchMetrics`` contract. It does not run matches, write
artifacts, build scoreboards, or submit to Kaggle.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from ow_sim.state import GameState

from .contracts import MatchMetrics


ERROR_STATUSES = frozenset(("ERROR", "FAILED", "INVALID", "TIMEOUT"))


def extract_match_metrics(
    replay_payload: Mapping[str, object],
    controlled_seat: int,
) -> MatchMetrics:
    """Extract deterministic metrics for ``controlled_seat`` from a replay."""

    if not isinstance(replay_payload, Mapping):
        raise ValueError("replay_payload must be a mapping")
    if isinstance(controlled_seat, bool) or not isinstance(controlled_seat, int):
        raise ValueError("controlled_seat must be a non-negative integer")
    if controlled_seat < 0:
        raise ValueError("controlled_seat must be a non-negative integer")

    controlled_records = _controlled_step_records(replay_payload, controlled_seat)
    top_level_rewards = _numeric_rewards(replay_payload.get("rewards"))
    final_score = _final_score(top_level_rewards, controlled_records, controlled_seat)
    final_state = _final_observed_state(controlled_records)
    states = tuple(_observed_state(record) for record in controlled_records)
    productions = tuple(_controlled_production(state, controlled_seat) for state in states)
    action_targets = tuple(
        target_owner
        for record, state in zip(controlled_records, states)
        for target_owner in _action_target_owners(record.get("action"), state, controlled_seat)
    )

    return MatchMetrics(
        final_rank=_final_rank(top_level_rewards, controlled_seat),
        final_score=final_score,
        final_planets=_final_planets(final_state, controlled_seat),
        final_ships=_final_ships(final_state, controlled_seat),
        final_production=_final_production(final_state, controlled_seat),
        turns_survived=_turns_survived(controlled_records),
        no_action_count=sum(
            1
            for record in controlled_records
            if record.get("action") == []
        ),
        error_count=sum(
            1
            for record in controlled_records
            if _status(record) in ERROR_STATUSES
        ),
        invalid_action_count=sum(
            1
            for record in controlled_records
            if _status(record) == "INVALID"
        ),
        timeout_count=sum(
            1
            for record in controlled_records
            if _status(record) == "TIMEOUT"
        ),
        action_count_after_t20=sum(
            len(_action_rows(record.get("action")))
            for index, record in enumerate(controlled_records)
            if index >= 20
        ),
        no_action_with_owned_production_count=sum(
            1
            for record, production in zip(controlled_records, productions)
            if production > 0 and not _action_rows(record.get("action"))
        ),
        enemy_target_action_count=sum(1 for owner in action_targets if owner == "enemy"),
        own_transfer_action_count=sum(1 for owner in action_targets if owner == "own"),
        neutral_target_action_count=sum(1 for owner in action_targets if owner == "neutral"),
        production_collapse=_production_collapse(productions),
        defense_coverage_count=_defense_coverage_count(controlled_records, states, controlled_seat),
        four_player_rank_pressure_count=_four_player_rank_pressure_count(states, controlled_seat),
        early_elimination=_early_elimination(controlled_records, productions),
    )


def _controlled_step_records(
    replay_payload: Mapping[str, object],
    controlled_seat: int,
) -> tuple[Mapping[str, object], ...]:
    steps = replay_payload.get("steps")
    if not _is_sequence(steps):
        raise ValueError("steps must be a sequence")

    records = []
    for step_index, step in enumerate(steps):
        if not _is_sequence(step):
            raise ValueError(f"steps[{step_index}] must be a sequence")
        if controlled_seat >= len(step):
            raise ValueError(
                f"steps[{step_index}] missing controlled seat {controlled_seat}"
            )
        record = step[controlled_seat]
        if not isinstance(record, Mapping):
            raise ValueError(f"steps[{step_index}][{controlled_seat}] must be a mapping")
        records.append(record)
    return tuple(records)


def _numeric_rewards(value: object) -> tuple[float | None, ...] | None:
    if not _is_sequence(value):
        return None
    return tuple(_numeric_or_none(item) for item in value)


def _final_score(
    top_level_rewards: tuple[float | None, ...] | None,
    controlled_records: tuple[Mapping[str, object], ...],
    controlled_seat: int,
) -> float | None:
    if top_level_rewards is not None and controlled_seat < len(top_level_rewards):
        controlled_reward = top_level_rewards[controlled_seat]
        if controlled_reward is not None:
            return controlled_reward
    if not controlled_records:
        return None
    return _numeric_or_none(controlled_records[-1].get("reward"))


def _final_rank(
    top_level_rewards: tuple[float | None, ...] | None,
    controlled_seat: int,
) -> int | None:
    if top_level_rewards is None or controlled_seat >= len(top_level_rewards):
        return None
    controlled_reward = top_level_rewards[controlled_seat]
    if controlled_reward is None:
        return None
    return 1 + sum(
        1
        for index, reward in enumerate(top_level_rewards)
        if index != controlled_seat and reward is not None and reward > controlled_reward
    )


def _final_observed_state(
    controlled_records: tuple[Mapping[str, object], ...],
) -> GameState | None:
    for record in reversed(controlled_records):
        observation = record.get("observation")
        if isinstance(observation, Mapping):
            return GameState.from_obs(observation)
    return None


def _observed_state(record: Mapping[str, object]) -> GameState | None:
    observation = record.get("observation")
    if isinstance(observation, Mapping):
        return GameState.from_obs(observation)
    return None


def _final_planets(state: GameState | None, controlled_seat: int) -> int | None:
    if state is None:
        return None
    return sum(1 for planet in state.planets if planet.owner == controlled_seat)


def _final_ships(state: GameState | None, controlled_seat: int) -> int | None:
    if state is None:
        return None
    planet_ships = sum(
        planet.ships
        for planet in state.planets
        if planet.owner == controlled_seat
    )
    fleet_ships = sum(
        fleet.ships
        for fleet in state.fleets
        if fleet.owner == controlled_seat
    )
    return planet_ships + fleet_ships


def _final_production(state: GameState | None, controlled_seat: int) -> int | None:
    if state is None:
        return None
    return sum(
        planet.production
        for planet in state.planets
        if planet.owner == controlled_seat
    )


def _controlled_production(state: GameState | None, controlled_seat: int) -> int:
    if state is None:
        return 0
    return sum(
        planet.production
        for planet in state.planets
        if planet.owner == controlled_seat
    )


def _action_rows(value: object) -> tuple[Sequence[object], ...]:
    if not _is_sequence(value):
        return ()
    rows = []
    for row in value:
        if _is_sequence(row) and len(row) >= 3:
            rows.append(row)
    return tuple(rows)


def _action_target_owners(
    action_value: object,
    state: GameState | None,
    controlled_seat: int,
) -> tuple[str, ...]:
    if state is None:
        return ()
    owners: list[str] = []
    for row in _action_rows(action_value):
        source_id = row[0]
        angle = row[1]
        if isinstance(source_id, bool) or not isinstance(source_id, int):
            continue
        if isinstance(angle, bool) or not isinstance(angle, (int, float)):
            continue
        target = _inferred_action_target(state, source_id, float(angle))
        if target is None:
            continue
        if target.owner == controlled_seat:
            owners.append("own")
        elif target.owner < 0:
            owners.append("neutral")
        else:
            owners.append("enemy")
    return tuple(owners)


def _inferred_action_target(state: GameState, source_id: int, angle: float):
    source = next(
        (planet for planet in state.planets if planet.planet_id == source_id),
        None,
    )
    if source is None:
        return None
    candidates = []
    for planet in state.planets:
        if planet.planet_id == source_id:
            continue
        dx = planet.x - source.x
        dy = planet.y - source.y
        target_angle = math.atan2(dy, dx)
        delta = abs(math.atan2(math.sin(angle - target_angle), math.cos(angle - target_angle)))
        distance = math.hypot(dx, dy)
        candidates.append((delta, distance, planet.planet_id, planet))
    if not candidates:
        return None
    return min(candidates)[3]


def _production_collapse(productions: tuple[int, ...]) -> bool:
    peak = max(productions, default=0)
    final = productions[-1] if productions else 0
    return peak > 0 and final <= max(0, peak // 2)


def _defense_coverage_count(
    records: tuple[Mapping[str, object], ...],
    states: tuple[GameState | None, ...],
    controlled_seat: int,
) -> int:
    count = 0
    for record, state in zip(records, states):
        if state is None:
            continue
        owned_under_pressure = {
            planet.planet_id
            for planet in state.planets
            if planet.owner == controlled_seat
            and any(
                fleet.owner != controlled_seat
                and _fleet_appears_inbound_to_planet(fleet, planet)
                for fleet in state.fleets
            )
        }
        if not owned_under_pressure:
            continue
        for row in _action_rows(record.get("action")):
            if not row:
                continue
            if row[0] in owned_under_pressure:
                count += 1
                break
    return count


def _fleet_appears_inbound_to_planet(fleet, planet) -> bool:
    dx = planet.x - fleet.x
    dy = planet.y - fleet.y
    target_angle = math.atan2(dy, dx)
    delta = abs(math.atan2(math.sin(fleet.angle - target_angle), math.cos(fleet.angle - target_angle)))
    return delta <= 0.2


def _four_player_rank_pressure_count(
    states: tuple[GameState | None, ...],
    controlled_seat: int,
) -> int:
    count = 0
    for state in states:
        if state is None:
            continue
        owner_ids = sorted({planet.owner for planet in state.planets if planet.owner >= 0})
        if len(owner_ids) < 4:
            continue
        productions = {
            owner: sum(planet.production for planet in state.planets if planet.owner == owner)
            for owner in owner_ids
        }
        controlled_production = productions.get(controlled_seat, 0)
        if any(production > controlled_production for production in productions.values()):
            count += 1
    return count


def _early_elimination(
    controlled_records: tuple[Mapping[str, object], ...],
    productions: tuple[int, ...],
) -> bool:
    if not controlled_records or not productions:
        return False
    survived = _turns_survived(controlled_records)
    final_production = productions[-1] if productions else 0
    return final_production == 0 and survived < 250


def _turns_survived(controlled_records: tuple[Mapping[str, object], ...]) -> int:
    for index, record in enumerate(controlled_records, start=1):
        status = _status(record)
        if status is not None and status != "ACTIVE":
            return index
    return len(controlled_records)


def _status(record: Mapping[str, object]) -> str | None:
    status = record.get("status")
    if status is None:
        return None
    return str(status).upper()


def _numeric_or_none(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _is_sequence(value: object) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes))


__all__ = (
    "ERROR_STATUSES",
    "extract_match_metrics",
)
