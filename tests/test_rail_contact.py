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
        self.assertEqual(rail.PAD_CENTRES, (-136, 0, 136))
        self.assertAlmostEqual(shape.BoundBox.XLength, 300)
        self.assertAlmostEqual(shape.BoundBox.YLength, 32)
        self.assertAlmostEqual(shape.BoundBox.ZLength, 9.5)
        for x in range(-140, 141, 10):
            line = Part.makeLine(App.Vector(x, 0, 0), App.Vector(x, 0, 1.5))
            self.assertAlmostEqual(shape.common(line).Length, 1.5)
        for x in (-136, 0, 136):
            for y in (-12, 12):
                line = Part.makeLine(App.Vector(x, y, -0.1), App.Vector(x, y, 1.6))
                self.assertAlmostEqual(shape.common(line).Length, 1.5)

    def test_nine_walls_retain_eight_open_flex_spans(self):
        from gondola.parts import rail

        report = rail.flex_relief_check()
        self.assertTrue(report["passed"], report)
        self.assertEqual(len(report["open_spans"]), 8)
        widths = [
            row["x_range_mm"][1] - row["x_range_mm"][0] for row in report["open_spans"]
        ]
        self.assertEqual(widths, [8] * 8)
        line = Part.makeLine(App.Vector(-151, 0, 8.5), App.Vector(151, 0, 8.5))
        actual_walls = sorted(
            (edge.BoundBox.XMin, edge.BoundBox.XMax)
            for edge in rail.rail_shape().common(line).Edges
        )
        self.assertEqual(
            actual_walls,
            [
                (-149, -123),
                (-115, -89),
                (-81, -55),
                (-47, -21),
                (-13, 13),
                (21, 47),
                (55, 81),
                (89, 115),
                (123, 149),
            ],
        )

    def test_straight_base_and_all_supports_share_regular_geometry(self):
        from gondola.parts import rail

        shape = rail.rail_shape()
        intervals = rail.wall_segments()
        self.assertEqual([b - a for a, b in intervals], [26] * 9)
        centres = [(a + b) / 2 for a, b in intervals]
        self.assertEqual([b - a for a, b in zip(centres, centres[1:])], [34] * 8)
        # Both free spans and wall roots retain the same straight base width.
        for x in (-119, -102, -85, -68, -51, -34, -17, 17, 34, 51, 68, 85, 102, 119):
            with self.subTest(x=x):
                cross_section = Part.makeLine(
                    App.Vector(x, -4, 0.75), App.Vector(x, 4, 0.75)
                )
                self.assertAlmostEqual(shape.common(cross_section).Length, 5)
                thickness = Part.makeLine(App.Vector(x, 0, 0), App.Vector(x, 0, 1.5))
                self.assertAlmostEqual(shape.common(thickness).Length, 1.5)
        self.assertTrue(
            all(
                type(face.Surface).__name__ == "Plane"
                for face in rail.base_shape().Faces
            )
        )
        self.assertTrue(
            all(
                type(face.Surface).__name__ == "Plane"
                for face in rail.plate_shape(0).Faces
            )
        )
        # A shorter rail retains complete standard walls instead of clipping ends.
        self.assertEqual(rail.wall_segments(290), intervals[1:-1])

    def test_accidental_bridge_between_walls_fails(self):
        from gondola.parts import rail

        bridged = rail.rail_shape().fuse(
            Part.makeBox(8, 2.5, 1, App.Vector(13, -1.25, 1.5))
        )
        self.assertFalse(rail.flex_relief_check(bridged)["passed"])

    def test_slot_limits_retain_whole_foot_and_reject_gap_positions(self):
        from gondola.cad import translated_shape
        from gondola.parts import rail

        shape = rail.rail_shape()
        self.assertEqual(len(rail.supported_slot_ranges()), 9)
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
        for x in (-119, -85, -51, -17, 17, 51, 85, 119):
            self.assertFalse(rail.attachment_position_check(x)["passed"])
        # Having no collision in a gap does not imply a valid attachment.
        self.assertFalse(
            rail.attachment_check(translated_shape(shape, x=-17))["passed"]
        )

    def test_propulsion_foot_is_supported_by_every_identical_wall(self):
        from gondola.cad import translated_shape
        from gondola.parts import rail

        shape = rail.rail_shape()
        ranges = rail.supported_slot_ranges(contact_length=24)
        self.assertEqual(len(ranges), 9)
        for (low, high), centre in zip(ranges, range(-136, 137, 34)):
            self.assertAlmostEqual(low, centre - 0.2)
            self.assertAlmostEqual(high, centre + 0.2)
            for x in (low, centre, high):
                self.assertTrue(
                    rail.attachment_position_check(x, contact_length=24)["passed"]
                )
                self.assertTrue(
                    rail.attachment_check(
                        translated_shape(shape, x=-x), contact_length=24
                    )["passed"]
                )
            self.assertFalse(
                rail.attachment_position_check(high + 0.01, contact_length=24)["passed"]
            )
        self.assertEqual(rail.supported_slot_ranges(contact_length=32), ())
        self.assertAlmostEqual(rail.mount_base_shape(length=24).BoundBox.XLength, 24)

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

        for length in (0, -1, math.nan, math.inf, True, None, "300", 10, 301):
            with self.subTest(length=length), self.assertRaises(ValueError):
                rail.rail_shape(length, ())
        for values in ((math.nan,), (True,), ("0",), None, (0, 0), (24,)):
            with self.subTest(values=values), self.assertRaises(ValueError):
                rail.rail_shape(50, values)
        for top in (8.5, 10.9, math.nan, True):
            with self.subTest(top=top), self.assertRaises(ValueError):
                rail.mount_base_shape(top)

    def test_attachment_contract_cannot_promise_an_unsupported_short_foot(self):
        from gondola.parts import rail

        existing_mount = rail.mount_base_shape()
        queries = (
            lambda length: rail.attachment_windows(contact_length=length),
            lambda length: rail.supported_slot_ranges(contact_length=length),
            lambda length: rail.attachment_position_check(0, contact_length=length),
            lambda length: rail.attachment_contract(contact_length=length),
            lambda length: rail.mount_base_shape(length=length),
            # Supplying a shape must not bypass the dimensional contract.
            lambda length: rail.attachment_check(
                mount=existing_mount, contact_length=length
            ),
        )
        for length in (1, 15.9, 0, -1, math.nan, math.inf, True, None, "16"):
            for index, query in enumerate(queries):
                with (
                    self.subTest(length=length, query=index),
                    self.assertRaises(ValueError),
                ):
                    query(length)
        # Both supported footprints retain the same nominal contact contract.
        for length, expected_windows in ((16, 9), (24, 9), (32, 0)):
            contract = rail.attachment_contract(contact_length=length)
            self.assertEqual(contract["mount_contact_length_mm"], length)
            self.assertEqual(
                len(contract["supported_bolt_axis_ranges_x_mm"]), expected_windows
            )

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
            self.assertEqual(sorted(centres), [-136, -136, 0, 0, 136, 136])
            self.assertEqual(len(rail.build_coupons(doc)["printed"]), 2)
            self.assertAlmostEqual(doc.RailFitSample.Shape.BoundBox.XLength, 50)
            for coupon in (doc.RailFitSample, doc.MountFitSample):
                contract = json.loads(coupon.RailAttachmentContract)
                self.assertEqual(contract["rail_length_mm"], 50)
                self.assertEqual(contract["wall_segments_x_mm"], [[-13, 13]])
                self.assertEqual(contract["free_base_spans_x_mm"], [])
                self.assertIsNone(contract["free_span_minimum_width_mm"])
                ranges = contract["supported_bolt_axis_ranges_x_mm"]
                self.assertEqual(len(ranges), 1)
                self.assertAlmostEqual(ranges[0][0], -4.2)
                self.assertAlmostEqual(ranges[0][1], 4.2)
            rail_contract = json.loads(doc.ContinuousRail.RailAttachmentContract)
            self.assertEqual(rail_contract["rail_length_mm"], 300)
            self.assertEqual(rail_contract["free_span_minimum_width_mm"], 5)
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
