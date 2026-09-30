"""Native side-slot rail geometry, full contact and segmented adjustment limits."""

import json
import math
import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class RailContactTests(unittest.TestCase):
    def test_three_wing_pairs_and_closed_base_keep_manufacturing_thickness(self):
        from gondola.parts import rail

        shape = rail.rail_shape()
        self.assertTrue(shape.isValid())
        self.assertEqual(len(shape.Solids), 1)
        self.assertEqual(rail.PAD_CENTRES, (-140, 0, 140))
        self.assertAlmostEqual(shape.BoundBox.XLength, 300)
        self.assertAlmostEqual(shape.BoundBox.YLength, 32)
        self.assertAlmostEqual(shape.BoundBox.ZLength, 9.5)
        for x in range(-140, 141, 10):
            line = Part.makeLine(App.Vector(x, 0, 0), App.Vector(x, 0, 1.5))
            self.assertAlmostEqual(shape.common(line).Length, 1.5)
        for x in (-140, 0, 140):
            for y in (-12, 12):
                line = Part.makeLine(App.Vector(x, y, -0.1), App.Vector(x, y, 1.6))
                self.assertAlmostEqual(shape.common(line).Length, 1.5)

    def test_wider_centre_retains_two_six_and_four_twelve_mm_flex_spans(self):
        from gondola.parts import rail

        report = rail.flex_relief_check()
        self.assertTrue(report["passed"], report)
        self.assertEqual(len(report["open_spans"]), 6)
        widths = [
            row["x_range_mm"][1] - row["x_range_mm"][0] for row in report["open_spans"]
        ]
        self.assertEqual(widths, [12, 12, 6, 6, 12, 12])

    def test_waists_preserve_wall_roots_and_transition_smoothly(self):
        from gondola.parts import rail

        shape = rail.rail_shape()
        for first, last in (
            (-131, -119),
            (-81, -69),
            (-31, -25),
            (25, 31),
            (69, 81),
            (119, 131),
        ):
            for fraction, expected in ((0, 6), (0.25, 5.25), (0.5, 4.5), (1, 6)):
                x = first + (last - first) * fraction
                with self.subTest(gap=(first, last), fraction=fraction):
                    cross_section = Part.makeLine(
                        App.Vector(x, -4, 0.75), App.Vector(x, 4, 0.75)
                    )
                    self.assertAlmostEqual(shape.common(cross_section).Length, expected)
                    thickness = Part.makeLine(
                        App.Vector(x, 0, 0), App.Vector(x, 0, 1.5)
                    )
                    self.assertAlmostEqual(shape.common(thickness).Length, 1.5)

    def test_accidental_bridge_between_walls_fails(self):
        from gondola.parts import rail

        bridged = rail.rail_shape().fuse(
            Part.makeBox(6, 2.5, 1, App.Vector(25, -1.25, 1.5))
        )
        self.assertFalse(rail.flex_relief_check(bridged)["passed"])

    def test_slot_limits_retain_whole_foot_and_reject_gap_positions(self):
        from gondola.cad import translated_shape
        from gondola.parts import rail

        shape = rail.rail_shape()
        self.assertEqual(len(rail.supported_slot_ranges()), 7)
        for low, high in rail.supported_slot_ranges():
            for x in (low, (low + high) / 2, high):
                with self.subTest(x=x):
                    report = rail.attachment_position_check(x)
                    self.assertTrue(report["passed"], report)
                    self.assertGreaterEqual(
                        report["minimum_full_foot_end_margin_mm"], 0.8 - 1e-6
                    )
                    self.assertTrue(
                        rail.attachment_check(translated_shape(shape, x=-x))["passed"]
                    )
            for x in (low - 0.01, high + 0.01):
                self.assertFalse(rail.attachment_position_check(x)["passed"])
        for x in (-125, -75, -28, 28, 75, 125):
            self.assertFalse(rail.attachment_position_check(x)["passed"])
        # Having no collision in a gap does not imply a valid attachment.
        self.assertFalse(
            rail.attachment_check(translated_shape(shape, x=-28))["passed"]
        )

    def test_long_propulsion_foot_has_shorter_supported_travel(self):
        from gondola.cad import translated_shape
        from gondola.parts import rail

        shape = rail.rail_shape()
        ranges = rail.supported_slot_ranges(contact_length=32)
        self.assertEqual(len(ranges), 5)
        for centre, (low, high) in zip((-100, -50, 0, 50, 100), ranges):
            half_travel = 8.2 if centre == 0 else 2.2
            self.assertAlmostEqual(low, centre - half_travel)
            self.assertAlmostEqual(high, centre + half_travel)
            for x in (low, high):
                self.assertTrue(
                    rail.attachment_position_check(x, contact_length=32)["passed"]
                )
                self.assertTrue(
                    rail.attachment_check(
                        translated_shape(shape, x=-x), contact_length=32
                    )["passed"]
                )
            self.assertFalse(
                rail.attachment_position_check(high + 0.01, contact_length=32)["passed"]
            )
        for x in (-140, 140, 10):
            self.assertFalse(
                rail.attachment_position_check(x, contact_length=32)["passed"]
            )
        self.assertAlmostEqual(rail.mount_base_shape(length=32).BoundBox.XLength, 32)

    def test_l_mount_seats_and_lifts_without_deflecting_ear(self):
        from gondola.parts import rail

        report = rail.attachment_check()
        self.assertTrue(report["passed"], report)
        self.assertIn("face-prism", report["continuous_vertical_removal"]["method"])
        self.assertAlmostEqual(report["missing_full_top_contact_mm3"], 0)
        self.assertAlmostEqual(report["missing_flat_side_contact_mm3"], 0)

    def test_missing_clamp_leg_and_top_seat_are_rejected(self):
        from gondola.parts import rail

        for cut in (
            Part.makeBox(2, 2.5, 1, App.Vector(3, -3.75, 3)),
            Part.makeBox(2, 2.5, 1, App.Vector(3, -1.25, 9.5)),
        ):
            with self.subTest(cut=cut.BoundBox):
                self.assertFalse(
                    rail.attachment_check(mount=rail.mount_base_shape().cut(cut))[
                        "passed"
                    ]
                )

    def test_added_hook_fails_continuous_vertical_release(self):
        from gondola.parts import rail

        # A tongue enters the clear slot while seated but catches its ceiling.
        hook = Part.makeBox(1, 3, 0.3, App.Vector(-0.5, -1.5, 6.35))
        report = rail.attachment_check(mount=rail.mount_base_shape().fuse(hook))
        self.assertFalse(report["passed"])
        self.assertGreater(report["continuous_vertical_removal"]["overlap_mm3"], 0)

    def test_invalid_dimensions_fail_before_building_geometry(self):
        from gondola.parts import rail

        for length in (0, -1, math.nan, math.inf, True, None, "300", 10):
            with self.subTest(length=length), self.assertRaises(ValueError):
                rail.rail_shape(length, ())
        for values in ((math.nan,), (True,), ("0",), None, (0, 0), (24,)):
            with self.subTest(values=values), self.assertRaises(ValueError):
                rail.rail_shape(50, values)
        for top in (8.5, 10.9, math.nan, True):
            with self.subTest(top=top), self.assertRaises(ValueError):
                rail.mount_base_shape(top)

    def test_tape_pairs_and_process_matched_coupons(self):
        from gondola.cad import translated_shape
        from gondola.parts import rail

        doc = App.newDocument("SideSlotCouponTest")
        try:
            built = rail.build_rail(doc)
            self.assertEqual(len(built["tapes"]), 6)
            solid = built["printed"][0].Shape
            centres = []
            for tape in built["tapes"]:
                centres.append(round(tape.Shape.CenterOfMass.x, 6))
                self.assertLess(solid.common(tape.Shape).Volume, 1e-6)
                self.assertGreater(
                    solid.common(translated_shape(tape.Shape, z=-0.01)).Volume, 0.5
                )
            self.assertEqual(sorted(centres), [-140, -140, 0, 0, 140, 140])
            self.assertEqual(len(rail.build_coupons(doc)["printed"]), 2)
            self.assertAlmostEqual(doc.RailFitSample.Shape.BoundBox.XLength, 50)
            for coupon in (doc.RailFitSample, doc.MountFitSample):
                contract = json.loads(coupon.RailAttachmentContract)
                self.assertEqual(contract["rail_length_mm"], 50)
                self.assertEqual(contract["wall_segments_x_mm"], [[-25, 25]])
                self.assertEqual(contract["free_base_spans_x_mm"], [])
                self.assertIsNone(contract["free_span_minimum_width_mm"])
                ranges = contract["supported_bolt_axis_ranges_x_mm"]
                self.assertEqual(len(ranges), 1)
                self.assertAlmostEqual(ranges[0][0], -16.2)
                self.assertAlmostEqual(ranges[0][1], 16.2)
            rail_contract = json.loads(doc.ContinuousRail.RailAttachmentContract)
            self.assertEqual(rail_contract["rail_length_mm"], 300)
            self.assertEqual(rail_contract["free_span_minimum_width_mm"], 4.5)
            self.assertTrue(
                rail.attachment_check(
                    doc.RailFitSample.Shape, doc.MountFitSample.Shape
                )["passed"]
            )
        finally:
            App.closeDocument(doc.Name)

    def test_underside_adhesive_allowed_but_unmodeled(self):
        from gondola.parts import rail

        contract = rail.tape_attachment_contract()
        self.assertIn("double-sided", contract["attachment"])
        self.assertIn("not modeled", contract["reference_scope"])
        self.assertIn("not load-qualified", contract["qualification"])


if __name__ == "__main__":
    unittest.main()
