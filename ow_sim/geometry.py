"""Geometry helpers for the Orbit Wars simulator.

Cycle 0 only includes unambiguous pure helpers. Collision, swept intersections,
orbital motion, and sun interactions are intentionally deferred.
"""

from __future__ import annotations

import math

from .state import Point2D


def distance(a: Point2D, b: Point2D) -> float:
    """Return Euclidean distance between two 2D points."""

    return math.hypot(b[0] - a[0], b[1] - a[1])
