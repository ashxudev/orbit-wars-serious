"""Pure geometry helpers for the Orbit Wars simulator.

These helpers compute geometry facts only. They do not move planets or fleets,
resolve collisions as game events, apply production, or mutate state.
"""

from __future__ import annotations

import math
from typing import TypeAlias

from .constants import ROTATION_RADIUS_LIMIT, SUN_CENTER, SUN_RADIUS


Point2D: TypeAlias = tuple[float, float]


def distance(a: Point2D, b: Point2D) -> float:
    """Return Euclidean distance between two 2D points."""

    return distance_xy(a[0], a[1], b[0], b[1])


def distance_xy(ax: float, ay: float, bx: float, by: float) -> float:
    """Return Euclidean distance between two explicit x/y points."""

    return math.hypot(bx - ax, by - ay)


def clamp(value: float, lower: float, upper: float) -> float:
    """Clamp ``value`` into the inclusive ``[lower, upper]`` interval."""

    if lower > upper:
        raise ValueError("lower must be <= upper")
    return max(lower, min(upper, value))


def angle_between(a: Point2D, b: Point2D) -> float:
    """Return the angle in radians from point ``a`` to point ``b``."""

    return math.atan2(b[1] - a[1], b[0] - a[0])


def vector_from_angle(angle: float, magnitude: float = 1.0) -> Point2D:
    """Return the vector represented by ``angle`` and ``magnitude``."""

    return (math.cos(angle) * magnitude, math.sin(angle) * magnitude)


def point_to_segment_distance(point: Point2D, start: Point2D, end: Point2D) -> float:
    """Return the shortest distance from ``point`` to segment ``start``-``end``."""

    sx, sy = start
    ex, ey = end
    wx = ex - sx
    wy = ey - sy
    length_sq = wx * wx + wy * wy
    if length_sq == 0.0:
        return distance(point, start)

    t = ((point[0] - sx) * wx + (point[1] - sy) * wy) / length_sq
    t = clamp(t, 0.0, 1.0)
    projection = (sx + t * wx, sy + t * wy)
    return distance(point, projection)


def segment_circle_intersects(
    start: Point2D,
    end: Point2D,
    center: Point2D,
    radius: float,
) -> bool:
    """Return whether a segment intersects or touches a circle."""

    return point_to_segment_distance(center, start, end) <= radius


def segment_hits_sun(
    start: Point2D,
    end: Point2D,
    *,
    center: Point2D = SUN_CENTER,
    radius: float = SUN_RADIUS,
) -> bool:
    """Return whether a segment enters the sun radius.

    The official interpreter removes fleets when the segment distance to the
    sun center is strictly less than the sun radius.
    """

    return point_to_segment_distance(center, start, end) < radius


def swept_circle_intersects(
    moving_point_start: Point2D,
    moving_point_end: Point2D,
    circle_center_start: Point2D,
    circle_center_end: Point2D,
    radius: float,
) -> bool:
    """Return whether a moving point comes within a moving circle radius.

    Both movements are treated as linear chords over the same normalized time
    interval. This mirrors the official swept pair geometry primitive without
    turning the result into simulator behavior.
    """

    d0x = moving_point_start[0] - circle_center_start[0]
    d0y = moving_point_start[1] - circle_center_start[1]
    dvx = (moving_point_end[0] - moving_point_start[0]) - (
        circle_center_end[0] - circle_center_start[0]
    )
    dvy = (moving_point_end[1] - moving_point_start[1]) - (
        circle_center_end[1] - circle_center_start[1]
    )

    a = dvx * dvx + dvy * dvy
    b = 2.0 * (d0x * dvx + d0y * dvy)
    c = d0x * d0x + d0y * d0y - radius * radius

    if a < 1e-12:
        return c <= 0.0

    discriminant = b * b - 4.0 * a * c
    if discriminant < 0.0:
        return False

    root = math.sqrt(discriminant)
    t1 = (-b - root) / (2.0 * a)
    t2 = (-b + root) / (2.0 * a)
    return t2 >= 0.0 and t1 <= 1.0


def is_orbiting_position(
    position: Point2D,
    radius: float,
    *,
    center: Point2D = SUN_CENTER,
    rotation_radius_limit: float = ROTATION_RADIUS_LIMIT,
) -> bool:
    """Return whether a planet position is classified as orbiting."""

    return distance(position, center) + radius < rotation_radius_limit


def is_static_position(
    position: Point2D,
    radius: float,
    *,
    center: Point2D = SUN_CENTER,
    rotation_radius_limit: float = ROTATION_RADIUS_LIMIT,
) -> bool:
    """Return whether a planet position is classified as static."""

    return not is_orbiting_position(
        position,
        radius,
        center=center,
        rotation_radius_limit=rotation_radius_limit,
    )
