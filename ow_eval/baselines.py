"""Deterministic built-in baselines for local evaluation matches.

Evaluation Harness Cycle 3 provides small named baseline opponents for local
testing only. These are intentionally simple and do not import the official
Kaggle environment.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from enum import Enum
from typing import Any

from ow_sim.geometry import angle_between, distance
from ow_sim.state import GameState, Planet

from .contracts import AgentSourceKind, AgentSpec


KaggleAgent = Callable[[Any, Any], list[list[int | float]]]
SOURCE_RESERVE_SHIPS = 1


class BaselineName(str, Enum):
    """Available built-in baseline names."""

    NOOP = "noop"
    NEAREST_NEUTRAL = "nearest_neutral"


def available_builtin_baselines() -> tuple[str, ...]:
    """Return available built-in baseline names in stable order."""

    return tuple(baseline.value for baseline in BaselineName)


def builtin_baseline_spec(
    baseline: BaselineName | str,
    name: str | None = None,
) -> AgentSpec:
    """Return an explicit ``BUILTIN_BASELINE`` agent spec."""

    baseline_name = _validated_baseline_name(baseline)
    return AgentSpec(
        name=name or baseline_name,
        source_kind=AgentSourceKind.BUILTIN_BASELINE,
        metadata=(("baseline", baseline_name),),
    )


def load_builtin_baseline(agent_spec: AgentSpec) -> KaggleAgent:
    """Return the built-in baseline callable for ``agent_spec``."""

    if agent_spec.source_kind is not AgentSourceKind.BUILTIN_BASELINE:
        raise ValueError("agent source kind must be builtin_baseline")

    explicit_baseline = _explicit_baseline_name(agent_spec)
    if explicit_baseline is None:
        baseline_name = BaselineName.NOOP.value
    else:
        baseline_name = _validated_baseline_name(explicit_baseline)

    if baseline_name == BaselineName.NOOP.value:
        return noop_baseline_agent
    if baseline_name == BaselineName.NEAREST_NEUTRAL.value:
        return nearest_neutral_baseline_agent
    raise ValueError(f"unknown builtin baseline: {baseline_name}")


def noop_baseline_agent(
    observation: Any,
    configuration: Any = None,
) -> list[list[int | float]]:
    """Return a fresh no-action list."""

    _ = observation, configuration
    return []


def nearest_neutral_baseline_agent(
    observation: Mapping[str, object],
    configuration: Any = None,
) -> list[list[int | float]]:
    """Send one ship from the closest eligible source to a neutral planet."""

    _ = configuration
    try:
        state = GameState.from_obs(observation)
    except Exception:
        return []

    if state.player_id is None:
        return []

    sources = tuple(
        planet
        for planet in state.planets
        if planet.owner == state.player_id and planet.ships > SOURCE_RESERVE_SHIPS
    )
    targets = tuple(
        planet
        for planet in state.planets
        if planet.owner == -1
    )
    if not sources or not targets:
        return []

    source, target = _nearest_source_target_pair(sources, targets)
    return [[source.planet_id, angle_between(source.position, target.position), 1]]


def _nearest_source_target_pair(
    sources: tuple[Planet, ...],
    targets: tuple[Planet, ...],
) -> tuple[Planet, Planet]:
    return min(
        (
            (source, target)
            for source in sources
            for target in targets
        ),
        key=lambda pair: (
            distance(pair[0].position, pair[1].position),
            pair[0].planet_id,
            pair[1].planet_id,
        ),
    )


def _explicit_baseline_name(agent_spec: AgentSpec) -> str | None:
    for key, value in agent_spec.metadata:
        if key == "baseline":
            return value
    return None


def _validated_baseline_name(baseline: BaselineName | str) -> str:
    baseline_name = baseline.value if isinstance(baseline, BaselineName) else baseline
    if baseline_name not in available_builtin_baselines():
        raise ValueError(f"unknown builtin baseline: {baseline_name}")
    return baseline_name


__all__ = (
    "BaselineName",
    "SOURCE_RESERVE_SHIPS",
    "available_builtin_baselines",
    "builtin_baseline_spec",
    "load_builtin_baseline",
    "nearest_neutral_baseline_agent",
    "noop_baseline_agent",
)
