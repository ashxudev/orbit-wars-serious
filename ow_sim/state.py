"""Provisional state containers for parsed Orbit Wars observations.

The exact engine observation schema is not confirmed in this workspace yet.
These dataclasses are conservative placeholders for imports and early tests;
real parsing should wait for official input or replay inspection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, TypeAlias


Point2D: TypeAlias = tuple[float, float]
"""A provisional 2D point represented as ``(x, y)``."""


@dataclass(frozen=True, slots=True)
class Planet:
    """Minimal provisional planet state.

    Fields are intentionally sparse until the official planet schema is known.
    """

    planet_id: str
    position: Point2D
    owner: int | None = None
    ships: float | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Fleet:
    """Minimal provisional fleet state.

    Launch, velocity, and arrival fields are deferred until the engine schema
    and timing rules are confirmed.
    """

    fleet_id: str
    owner: int | None = None
    ships: float | None = None
    position: Point2D | None = None
    source_id: str | None = None
    target_id: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GameState:
    """Minimal provisional game state container."""

    tick: int | None = None
    player_id: int | None = None
    planets: tuple[Planet, ...] = field(default_factory=tuple)
    fleets: tuple[Fleet, ...] = field(default_factory=tuple)
    raw_observation: Mapping[str, object] | None = None
