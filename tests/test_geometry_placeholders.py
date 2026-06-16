"""Tests for cycle-0 geometry helpers."""

from __future__ import annotations

import unittest

from ow_sim.geometry import distance


class GeometryPlaceholderTests(unittest.TestCase):
    def test_distance_handles_3_4_5_triangle(self) -> None:
        self.assertEqual(distance((0.0, 0.0), (3.0, 4.0)), 5.0)
