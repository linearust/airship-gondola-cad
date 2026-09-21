"""Invalid numeric audit evidence must not silently pass."""

import unittest

from gondola.validation.evidence import overlap_failures


class OverlapEvidenceTests(unittest.TestCase):
    def test_nested_overlaps_fail_in_either_sign(self):
        result = overlap_failures(
            {
                "samples": [
                    {"overlap_frame_mm3": 0.1},
                    {"nested": {"rail_shoe_overlap_mm3": -0.2}},
                ]
            },
            1e-5,
        )
        self.assertEqual(
            result,
            [
                {"field": "/samples/0/overlap_frame_mm3", "volume_mm3": 0.1},
                {
                    "field": "/samples/1/nested/rail_shoe_overlap_mm3",
                    "volume_mm3": -0.2,
                },
            ],
        )

    def test_nonfinite_overlaps_fail(self):
        for volume in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(volume=volume):
                result = overlap_failures({"overlap_mm3": volume}, 1e-5)
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0]["field"], "/overlap_mm3")

    def test_tolerance_and_required_blocking_contacts_are_not_failures(self):
        self.assertEqual(
            overlap_failures(
                {
                    "rail_overlap_mm3": 1e-5,
                    "shoe_overlap_mm3": -1e-6,
                    "blocking_intersection_mm3": 1.0,
                    "bearing_contact_area_mm2": 2.0,
                    "overlap_scope": "Nominal solid envelopes",
                },
                1e-5,
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
