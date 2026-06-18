"""Deterministic metrics extraction from official match replays.

Evaluation Harness Cycle 5 turns one official ``env.toJSON()`` payload into
the existing ``MatchMetrics`` contract. It does not run matches, write
artifacts, build scoreboards, or submit to Kaggle.
"""

from __future__ import annotations

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
