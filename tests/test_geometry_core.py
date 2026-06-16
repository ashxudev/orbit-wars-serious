"""Tests for pure geometry helpers."""

from __future__ import annotations

import math
import unittest

from ow_sim import constants
from ow_sim.geometry import (
    angle_between,
    distance,
    distance_xy,
    is_orbiting_position,
    is_static_position,
    point_to_segment_distance,
    segment_circle_intersects,
    segment_hits_sun,
    swept_circle_intersects,
    vector_from_angle,
)


class GeometryCoreTests(unittest.TestCase):
    def assertPointAlmostEqual(
        self,
        actual: tuple[float, float],
        expected: tuple[float, float],
    ) -> None:
        self.assertAlmostEqual(actual[0], expected[0])
        self.assertAlmostEqual(actual[1], expected[1])

    def test_distance_handles_3_4_5_triangle(self) -> None:
        self.assertEqual(distance((0.0, 0.0), (3.0, 4.0)), 5.0)

    def test_distance_xy_handles_3_4_5_triangle(self) -> None:
        self.assertEqual(distance_xy(1.0, 2.0, 4.0, 6.0), 5.0)

    def test_angle_between_cardinal_directions(self) -> None:
        origin = (0.0, 0.0)

        self.assertAlmostEqual(angle_between(origin, (1.0, 0.0)), 0.0)
        self.assertAlmostEqual(angle_between(origin, (0.0, 1.0)), math.pi / 2.0)
        self.assertAlmostEqual(angle_between(origin, (-1.0, 0.0)), math.pi)
        self.assertAlmostEqual(angle_between(origin, (0.0, -1.0)), -math.pi / 2.0)

    def test_vector_from_angle_cardinal_directions(self) -> None:
        self.assertPointAlmostEqual(vector_from_angle(0.0, 3.0), (3.0, 0.0))
        self.assertPointAlmostEqual(
            vector_from_angle(math.pi / 2.0, 2.0),
            (0.0, 2.0),
        )
        self.assertPointAlmostEqual(
            vector_from_angle(math.pi, 4.0),
            (-4.0, 0.0),
        )

    def test_point_to_segment_distance_on_segment(self) -> None:
        self.assertEqual(
            point_to_segment_distance((2.0, 0.0), (0.0, 0.0), (4.0, 0.0)),
            0.0,
        )

    def test_point_to_segment_distance_beyond_endpoint(self) -> None:
        self.assertEqual(
            point_to_segment_distance((5.0, 0.0), (0.0, 0.0), (3.0, 0.0)),
            2.0,
        )

    def test_point_to_segment_distance_vertical_segment(self) -> None:
        self.assertEqual(
            point_to_segment_distance((2.0, 2.0), (0.0, 0.0), (0.0, 4.0)),
            2.0,
        )

    def test_point_to_segment_distance_horizontal_segment(self) -> None:
        self.assertEqual(
            point_to_segment_distance((2.0, 3.0), (0.0, 0.0), (4.0, 0.0)),
            3.0,
        )

    def test_segment_circle_intersects_hit_miss_and_tangent(self) -> None:
        center = (0.0, 0.0)

        self.assertTrue(
            segment_circle_intersects((-2.0, 0.0), (2.0, 0.0), center, 1.0)
        )
        self.assertFalse(
            segment_circle_intersects((-2.0, 2.0), (2.0, 2.0), center, 1.0)
        )
        self.assertTrue(
            segment_circle_intersects((-2.0, 1.0), (2.0, 1.0), center, 1.0)
        )

    def test_segment_hits_sun_uses_confirmed_center_and_radius(self) -> None:
        self.assertTrue(segment_hits_sun((0.0, 50.0), (100.0, 50.0)))
        self.assertFalse(segment_hits_sun((0.0, 61.0), (100.0, 61.0)))

        tangent_y = constants.SUN_CENTER[1] + constants.SUN_RADIUS
        self.assertFalse(segment_hits_sun((0.0, tangent_y), (100.0, tangent_y)))

    def test_swept_circle_stationary_hit(self) -> None:
        self.assertTrue(
            swept_circle_intersects(
                (0.5, 0.0),
                (0.5, 0.0),
                (0.0, 0.0),
                (0.0, 0.0),
                1.0,
            )
        )

    def test_swept_circle_stationary_miss(self) -> None:
        self.assertFalse(
            swept_circle_intersects(
                (2.0, 0.0),
                (2.0, 0.0),
                (0.0, 0.0),
                (0.0, 0.0),
                1.0,
            )
        )

    def test_swept_circle_moving_chord_hit(self) -> None:
        self.assertTrue(
            swept_circle_intersects(
                (0.0, 0.0),
                (2.0, 0.0),
                (1.0, 1.0),
                (1.0, -1.0),
                0.25,
            )
        )

    def test_swept_circle_parallel_miss(self) -> None:
        self.assertFalse(
            swept_circle_intersects(
                (0.0, 0.0),
                (2.0, 0.0),
                (0.0, 3.0),
                (2.0, 3.0),
                1.0,
            )
        )

    def test_orbit_static_classification_uses_confirmed_threshold(self) -> None:
        self.assertTrue(is_orbiting_position((70.0, 50.0), 2.0))
        self.assertTrue(is_static_position((99.0, 50.0), 1.0))
        self.assertTrue(is_static_position((90.0, 50.0), 10.0))
