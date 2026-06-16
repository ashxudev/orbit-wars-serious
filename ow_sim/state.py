"""State containers and observation parsing for Orbit Wars.

Cycle 1 is limited to official Kaggle observation schema parsing. The parser
does not simulate movement, production, collision, combat, or strategy.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence, TypeAlias


Point2D: TypeAlias = tuple[float, float]
"""A 2D point represented as ``(x, y)``."""


PLANET_ROW_LENGTH = 7
FLEET_ROW_LENGTH = 7


@dataclass(frozen=True, slots=True)
class Planet:
    """Parsed planet row.

    Official row format:
    ``[id, owner, x, y, radius, ships, production]``.
    """

    planet_id: int
    owner: int
    x: float
    y: float
    radius: float
    ships: int
    production: int
    is_comet: bool = False
    initial_position: Point2D | None = None
    raw: tuple[object, ...] = field(default_factory=tuple)

    @property
    def id(self) -> int:
        """Official planet id alias."""

        return self.planet_id

    @property
    def position(self) -> Point2D:
        """Current planet position."""

        return (self.x, self.y)


@dataclass(frozen=True, slots=True)
class Fleet:
    """Parsed fleet row.

    Official row format:
    ``[id, owner, x, y, angle, from_planet_id, ships]``.
    """

    fleet_id: int
    owner: int
    x: float
    y: float
    angle: float
    from_planet_id: int
    ships: int
    raw: tuple[object, ...] = field(default_factory=tuple)

    @property
    def id(self) -> int:
        """Official fleet id alias."""

        return self.fleet_id

    @property
    def position(self) -> Point2D:
        """Current fleet position."""

        return (self.x, self.y)


@dataclass(frozen=True, slots=True)
class CometGroup:
    """Parsed comet group metadata.

    Official group shape is a mapping with ``planet_ids``, ``paths``, and
    ``path_index``. Paths are parsed as tuples of ``(x, y)`` points only; comet
    motion is deferred to a later simulator cycle.
    """

    planet_ids: tuple[int, ...] = field(default_factory=tuple)
    paths: tuple[tuple[Point2D, ...], ...] = field(default_factory=tuple)
    path_index: int | None = None
    raw: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GameState:
    """Parsed Orbit Wars observation state.

    Missing optional fields use safe neutral defaults. The original observation
    is deep-copied into ``raw_observation`` so later validation can inspect it
    without sharing mutable lists with caller code.
    """

    tick: int | None = None
    player_id: int | None = None
    planets: tuple[Planet, ...] = field(default_factory=tuple)
    fleets: tuple[Fleet, ...] = field(default_factory=tuple)
    angular_velocity: float | None = None
    initial_planets: tuple[Planet, ...] = field(default_factory=tuple)
    next_fleet_id: int | None = None
    comet_planet_ids: frozenset[int] = field(default_factory=frozenset)
    comets: tuple[CometGroup, ...] = field(default_factory=tuple)
    remaining_overage_time: float | None = None
    raw_observation: Mapping[str, object] | None = None

    @property
    def step(self) -> int | None:
        """Official observation step alias."""

        return self.tick

    @classmethod
    def from_obs(cls, obs: Mapping[str, object]) -> GameState:
        """Parse a Kaggle Orbit Wars observation.

        Confirmed top-level fields include ``planets``, ``fleets``, ``player``,
        ``step``, ``angular_velocity``, ``initial_planets``, ``next_fleet_id``,
        ``comets``, ``comet_planet_ids``, and ``remainingOverageTime``.
        """

        comet_planet_ids = frozenset(
            _as_int(value, "comet_planet_ids[]")
            for value in _optional_iterable(obs.get("comet_planet_ids"))
        )
        initial_rows = tuple(_optional_iterable(obs.get("initial_planets")))
        initial_positions = {
            _as_int(row[0], "initial_planets[][0]"): (
                _as_float(row[2], "initial_planets[][2]"),
                _as_float(row[3], "initial_planets[][3]"),
            )
            for row in _planet_rows(initial_rows, "initial_planets")
        }

        return cls(
            tick=_optional_int(obs.get("step"), "step"),
            player_id=_optional_int(obs.get("player"), "player"),
            planets=tuple(
                _parse_planet(row, comet_planet_ids, initial_positions)
                for row in _planet_rows(_optional_iterable(obs.get("planets")), "planets")
            ),
            fleets=tuple(
                _parse_fleet(row)
                for row in _fleet_rows(_optional_iterable(obs.get("fleets")), "fleets")
            ),
            angular_velocity=_optional_float(
                obs.get("angular_velocity"), "angular_velocity"
            ),
            initial_planets=tuple(
                _parse_planet(row, comet_planet_ids, initial_positions)
                for row in _planet_rows(initial_rows, "initial_planets")
            ),
            next_fleet_id=_optional_int(obs.get("next_fleet_id"), "next_fleet_id"),
            comet_planet_ids=comet_planet_ids,
            comets=tuple(_parse_comet_group(group) for group in _optional_iterable(obs.get("comets"))),
            remaining_overage_time=_optional_float(
                obs.get("remainingOverageTime"), "remainingOverageTime"
            ),
            raw_observation=copy.deepcopy(dict(obs)),
        )


def _parse_planet(
    row: Sequence[object],
    comet_planet_ids: frozenset[int],
    initial_positions: Mapping[int, Point2D],
) -> Planet:
    planet_id = _as_int(row[0], "planet.id")
    return Planet(
        planet_id=planet_id,
        owner=_as_int(row[1], "planet.owner"),
        x=_as_float(row[2], "planet.x"),
        y=_as_float(row[3], "planet.y"),
        radius=_as_float(row[4], "planet.radius"),
        ships=_as_int(row[5], "planet.ships"),
        production=_as_int(row[6], "planet.production"),
        is_comet=planet_id in comet_planet_ids,
        initial_position=initial_positions.get(planet_id),
        raw=tuple(row),
    )


def _parse_fleet(row: Sequence[object]) -> Fleet:
    return Fleet(
        fleet_id=_as_int(row[0], "fleet.id"),
        owner=_as_int(row[1], "fleet.owner"),
        x=_as_float(row[2], "fleet.x"),
        y=_as_float(row[3], "fleet.y"),
        angle=_as_float(row[4], "fleet.angle"),
        from_planet_id=_as_int(row[5], "fleet.from_planet_id"),
        ships=_as_int(row[6], "fleet.ships"),
        raw=tuple(row),
    )


def _parse_comet_group(group: object) -> CometGroup:
    if not isinstance(group, Mapping):
        raise ValueError("comets[] must be a mapping")

    paths = []
    for path in _optional_iterable(group.get("paths")):
        points = []
        for point in _optional_iterable(path):
            if not isinstance(point, Sequence) or isinstance(point, (str, bytes)):
                raise ValueError("comets[].paths[][] must be a 2-item point")
            if len(point) != 2:
                raise ValueError("comets[].paths[][] must have length 2")
            points.append(
                (
                    _as_float(point[0], "comets[].paths[][].x"),
                    _as_float(point[1], "comets[].paths[][].y"),
                )
            )
        paths.append(tuple(points))

    return CometGroup(
        planet_ids=tuple(
            _as_int(value, "comets[].planet_ids[]")
            for value in _optional_iterable(group.get("planet_ids"))
        ),
        paths=tuple(paths),
        path_index=_optional_int(group.get("path_index"), "comets[].path_index"),
        raw=copy.deepcopy(dict(group)),
    )


def _planet_rows(rows: Iterable[object], field_name: str) -> tuple[Sequence[object], ...]:
    parsed = []
    for index, row in enumerate(rows):
        parsed.append(_row(row, PLANET_ROW_LENGTH, f"{field_name}[{index}]"))
    return tuple(parsed)


def _fleet_rows(rows: Iterable[object], field_name: str) -> tuple[Sequence[object], ...]:
    parsed = []
    for index, row in enumerate(rows):
        parsed.append(_row(row, FLEET_ROW_LENGTH, f"{field_name}[{index}]"))
    return tuple(parsed)


def _row(row: object, expected_length: int, field_name: str) -> Sequence[object]:
    if not isinstance(row, Sequence) or isinstance(row, (str, bytes)):
        raise ValueError(f"{field_name} must be a sequence")
    if len(row) != expected_length:
        raise ValueError(
            f"{field_name} must have length {expected_length}; got {len(row)}"
        )
    return row


def _optional_iterable(value: object | None) -> tuple[object, ...]:
    if value is None:
        return ()
    if isinstance(value, Mapping) or isinstance(value, (str, bytes)):
        raise ValueError("expected an iterable collection")
    try:
        return tuple(value)  # type: ignore[arg-type]
    except TypeError as exc:
        raise ValueError("expected an iterable collection") from exc


def _optional_int(value: object | None, field_name: str) -> int | None:
    if value is None:
        return None
    return _as_int(value, field_name)


def _optional_float(value: object | None, field_name: str) -> float | None:
    if value is None:
        return None
    return _as_float(value, field_name)


def _as_int(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an int")
    return value


def _as_float(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a number")
    return float(value)
