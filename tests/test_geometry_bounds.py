"""Analytical box distances used by independent motion certificates."""

import unittest
from types import SimpleNamespace

from gondola.validation.geometry import bounding_box_distance


def bounds(low, high):
    return SimpleNamespace(
        **{axis + "Min": value for axis, value in zip("XYZ", low)},
        **{axis + "Max": value for axis, value in zip("XYZ", high)},
    )


class BoundingBoxDistanceTests(unittest.TestCase):
    def test_diagonal_separation_is_symmetric_and_translation_invariant(self):
        # Nearest corners differ by (3, 4, 12), whose distance is exactly 13.
        for shift in (0, -100, 10000):
            first = bounds((shift,) * 3, (shift + 1,) * 3)
            second = bounds(
                tuple(shift + v for v in (4, 5, 13)),
                tuple(shift + v for v in (5, 6, 14)),
            )
            with self.subTest(shift=shift):
                self.assertEqual(bounding_box_distance(first, second), 13)
                self.assertEqual(bounding_box_distance(second, first), 13)

    def test_touching_overlapping_and_contained_bounds_have_no_separation(self):
        first = bounds((0, 0, 0), (2, 2, 2))
        for low, high in (
            ((2, 0, 0), (3, 1, 1)),  # Face contact.
            ((2, 2, 0), (3, 3, 1)),  # Edge contact.
            ((2, 2, 2), (3, 3, 3)),  # Corner contact.
            ((1, 1, 1), (3, 3, 3)),  # Overlap.
            ((0.5, 0.5, 0.5), (1.5, 1.5, 1.5)),  # Containment.
        ):
            with self.subTest(low=low, high=high):
                second = bounds(low, high)
                self.assertEqual(bounding_box_distance(first, second), 0)
                self.assertEqual(bounding_box_distance(second, first), 0)
