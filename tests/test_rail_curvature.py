"""Independent ordinary top seats and paired crowns retain distinct behavior."""

import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class LocalRailCurvatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.parts import rail

        cls.rail = rail.rail_shape(50, (0,))
        cls.mount = rail.mount_base_shape()

    def test_round_root_stock_is_checked_without_the_builder(self):
        from gondola.validation.rail_curvature import root_stock_check

        self.assertTrue(root_stock_check(self.rail, (0,))["passed"])
        for position, size in (
            ((9, -0.5, 1.5), (1, 1, 1)),
            ((-7, 1.25, 1.5), (14, 0.5, 0.5)),
        ):
            damaged = self.rail.cut(Part.makeBox(*size, App.Vector(*position)))
            self.assertFalse(root_stock_check(damaged, (0,))["passed"])

    def test_top_datum_retains_support_through_full_trim(self):
        from gondola.validation.rail_curvature import local_seat_check

        for offset, area in ((-3, 35), (0, 40), (3, 35)):
            section = self.rail.copy()
            section.translate(App.Vector(-offset, 0, 0))
            report = local_seat_check(section, self.mount)
            self.assertTrue(report["passed"], report)
            self.assertAlmostEqual(report["top_bearing"]["nominal_area_mm2"], area)
            self.assertEqual(report["bottom_datum_contacts"], [])
        damaged = self.mount.cut(Part.makeBox(2, 2.5, 0.1, App.Vector(-1, -1.25, 9.5)))
        self.assertFalse(local_seat_check(self.rail, damaged)["passed"])

    def test_lower_clearance_and_each_cheek_are_required(self):
        from gondola.validation.rail_curvature import local_seat_check

        filled = self.mount.fuse(Part.makeBox(2, 1, 1, App.Vector(-1, 2, 1.5)))
        report = local_seat_check(self.rail, filled)
        self.assertFalse(report["passed"])
        self.assertGreater(report["blocked_lower_clearance_mm3"], 0)
        for y in (-1.26, 1.25):
            damaged = self.mount.cut(Part.makeBox(4, 0.02, 1, App.Vector(-2, y, 8)))
            self.assertFalse(local_seat_check(self.rail, damaged)["passed"])

    def test_carrier_follows_wall_and_does_not_claim_fixed_deck_clearance(self):
        from gondola.validation.rail_curvature import angular_clearance_check

        report = angular_clearance_check(self.rail, self.mount, follow_wall=True)
        self.assertTrue(report["passed"], report)
        self.assertTrue(report["carrier_follows_wall"])
        self.assertEqual(report["slot_positions_mm"], [-3, 0, 3])
        self.assertEqual(len(report["poses"]), 51)
        self.assertIn("not a fixed-deck clearance claim", report["scope"])
        fixed = angular_clearance_check(self.rail, self.mount)
        self.assertFalse(fixed["passed"])
        self.assertTrue(any(p["interference_mm3"] > 1e-5 for p in fixed["poses"]))

    def test_paired_propulsion_retains_crowns_and_fixed_frame_clearance(self):
        from gondola.parts import propulsion
        from gondola.validation.rail_curvature import (
            angular_clearance_check,
            local_seat_check,
        )

        frame = propulsion.fixed_frame_shape()
        frame.translate(App.Vector(-14, 0, 0))
        report = local_seat_check(self.rail, frame, shared=True)
        self.assertTrue(report["passed"], report)
        self.assertTrue(
            all(
                not r["flat_contact_area_claimed"]
                for r in report["bottom_datum_contacts"]
            )
        )
        self.assertTrue(angular_clearance_check(self.rail, frame)["passed"])
        flat = frame.fuse(Part.makeBox(10, 1.25, 0.4, App.Vector(-5, 1.75, 1.5)))
        self.assertFalse(local_seat_check(self.rail, flat, shared=True)["passed"])

    def test_top_seat_preserves_fastener_floors_and_exact_lift(self):
        from gondola.validation.rail_contact import attachment_check

        report = attachment_check(self.rail, self.mount)
        self.assertTrue(report["passed"], report)
        self.assertLess(report["missing_head_support_mm3"], 1e-6)
        self.assertLess(report["missing_printed_nut_floor_mm3"], 1e-6)
        self.assertEqual(
            report["continuous_vertical_removal"]["method"],
            "continuous upward planar-face sweep",
        )
        self.assertLess(report["continuous_vertical_removal"]["overlap_mm3"], 1e-6)
        damaged = self.mount.cut(Part.makeBox(2, 1, 0.5, App.Vector(-1, 2.1, 8)))
        self.assertFalse(attachment_check(self.rail, damaged)["passed"])


if __name__ == "__main__":
    unittest.main()
