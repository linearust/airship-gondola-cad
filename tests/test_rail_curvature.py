"""Independent root/crown witnesses reject changes that defeat local relief."""

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

        report = root_stock_check(self.rail, (0,))
        self.assertTrue(report["passed"], report)
        for position, size in (
            ((9, -0.5, 1.5), (1, 1, 1)),
            ((-7, 1.25, 1.5), (14, 0.5, 0.5)),
        ):
            with self.subTest(position=position):
                damaged = self.rail.cut(Part.makeBox(*size, App.Vector(*position)))
                self.assertFalse(root_stock_check(damaged, (0,))["passed"])

    def test_crown_profile_rejects_a_flat_lower_extension(self):
        from gondola.validation.rail_curvature import local_seat_check

        report = local_seat_check(self.rail, self.mount)
        self.assertTrue(report["passed"], report)
        self.assertTrue(
            all(
                not row["flat_contact_area_claimed"]
                for row in report["bottom_datum_contacts"]
            )
        )
        extension = Part.makeBox(10, 1.25, 0.4, App.Vector(-5, 1.75, 1.5))
        flat = self.mount.fuse(extension)
        report = local_seat_check(self.rail, flat)
        self.assertFalse(report["passed"])
        self.assertGreater(
            report["bottom_datum_contacts"][1]["excess_below_crown_mm3"], 0
        )

    def test_root_clearance_and_each_cheek_are_independently_required(self):
        from gondola.validation.rail_curvature import local_seat_check

        filled = self.mount.fuse(Part.makeBox(2, 0.2, 0.5, App.Vector(-1, 1.3, 1.6)))
        self.assertGreater(
            local_seat_check(self.rail, filled)["blocked_root_relief_mm3"], 0
        )
        for y in (-1.26, 1.25):
            with self.subTest(y=y):
                damaged = self.mount.cut(Part.makeBox(4, 0.02, 1, App.Vector(-2, y, 8)))
                self.assertFalse(local_seat_check(self.rail, damaged)["passed"])

    def test_angular_screen_covers_both_trim_extremes_and_rejects_flat_feet(self):
        from gondola.validation.rail_curvature import angular_clearance_check

        report = angular_clearance_check(self.rail, self.mount)
        self.assertTrue(report["passed"], report)
        self.assertEqual(report["slot_positions_mm"], [-3, 0, 3])
        self.assertEqual(len(report["poses"]), 51)
        self.assertIn("not a certified continuous sweep", report["scope"])
        flat = self.mount.fuse(Part.makeBox(10, 1.25, 0.4, App.Vector(-5, 1.75, 1.5)))
        report = angular_clearance_check(self.rail, flat)
        self.assertFalse(report["passed"])
        self.assertTrue(
            any(
                row["interference_mm3"] > 1e-5
                for row in report["poses"]
                if abs(row["angle_deg"]) == 2
            )
        )

    def test_crowned_attachment_preserves_fastener_floors_and_exact_lift(self):
        from gondola.validation.rail_contact import attachment_check

        report = attachment_check(self.rail, self.mount)
        self.assertTrue(report["passed"], report)
        self.assertLess(report["missing_head_support_mm3"], 1e-6)
        self.assertLess(report["missing_printed_nut_floor_mm3"], 1e-6)
        self.assertIn(
            "continuous upward", report["continuous_vertical_removal"]["method"]
        )
        self.assertLess(report["continuous_vertical_removal"]["overlap_mm3"], 1e-6)
        damaged = self.mount.cut(Part.makeBox(2, 1, 0.5, App.Vector(-1, 2.1, 8)))
        self.assertFalse(attachment_check(self.rail, damaged)["passed"])


if __name__ == "__main__":
    unittest.main()
