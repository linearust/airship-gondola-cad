"""Native side-slot rail geometry, local crowned seats and segmented adjustment limits."""

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

    def test_eleven_walls_retain_ten_open_flex_spans(self):
        from gondola.parts import rail
        from gondola.validation import rail_contact

        report = rail_contact.flex_relief_check()
        self.assertTrue(report["passed"], report)
        self.assertEqual(len(report["open_spans"]), 10)
        widths = [
            row["x_range_mm"][1] - row["x_range_mm"][0] for row in report["open_spans"]
        ]
        self.assertEqual(widths, [8] * 10)
        line = Part.makeLine(App.Vector(-151, 0, 8.5), App.Vector(151, 0, 8.5))
        actual_walls = sorted(
            (edge.BoundBox.XMin, edge.BoundBox.XMax)
            for edge in rail.rail_shape().common(line).Edges
        )
        self.assertEqual(
            actual_walls,
            [
                (-149, -131),
                (-121, -103),
                (-93, -75),
                (-65, -47),
                (-37, -19),
                (-9, 9),
                (19, 37),
                (47, 65),
                (75, 93),
                (103, 121),
                (131, 149),
            ],
        )

    def test_straight_base_and_all_supports_share_regular_geometry(self):
        from gondola.parts import rail

        shape = rail.rail_shape()
        intervals = rail.wall_segments()
        self.assertEqual([b - a for a, b in intervals], [18] * 11)
        centres = [(a + b) / 2 for a, b in intervals]
        self.assertEqual([b - a for a, b in zip(centres, centres[1:])], [28] * 10)
        # Both free spans and wall roots retain the same straight base width.
        for x in (
            -126,
            -112,
            -98,
            -84,
            -70,
            -56,
            -42,
            -28,
            -14,
            14,
            28,
            42,
            56,
            70,
            84,
            98,
            112,
            126,
        ):
            with self.subTest(x=x):
                cross_section = Part.makeLine(
                    App.Vector(x, -4, 0.75), App.Vector(x, 4, 0.75)
                )
                self.assertAlmostEqual(shape.common(cross_section).Length, 6)
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
        from gondola.validation import rail_contact

        bridged = rail.rail_shape().fuse(
            Part.makeBox(8, 2.5, 1, App.Vector(10, -1.25, 1.5))
        )
        self.assertFalse(rail_contact.flex_relief_check(bridged)["passed"])

    def test_slot_limits_retain_local_contact_and_reject_gap_positions(self):
        from gondola.cad import translated_shape
        from gondola.parts import rail
        from gondola.validation import rail_contact

        shape = rail.rail_shape()
        self.assertEqual(len(rail.supported_slot_ranges()), 11)
        for low, high in rail.supported_slot_ranges():
            for x in (low, (low + high) / 2, high):
                with self.subTest(x=x):
                    report = rail.attachment_position_check(x)
                    self.assertTrue(report["passed"], report)
                    self.assertGreaterEqual(
                        report["minimum_centred_contact_end_margin_mm"], 1.0 - 1e-6
                    )
                    self.assertTrue(
                        rail_contact.attachment_check(translated_shape(shape, x=-x))[
                            "passed"
                        ]
                    )
            for x in (low - 0.01, high + 0.01):
                self.assertFalse(rail.attachment_position_check(x)["passed"])
        for x in (-126, -98, -70, -42, -14, 14, 42, 70, 98, 126):
            self.assertFalse(rail.attachment_position_check(x)["passed"])
        # Having no collision in a gap does not imply a valid attachment.
        self.assertFalse(
            rail_contact.attachment_check(translated_shape(shape, x=-14))["passed"]
        )

    def test_end_wall_travel_stops_before_base_corner_chamfers(self):
        from gondola.parts import rail

        ranges = rail.supported_slot_ranges()
        self.assertEqual(ranges[0], (-143.0, -137.0))
        self.assertEqual(ranges[-1], (137.0, 143.0))
        self.assertAlmostEqual(ranges[5][0], -3)
        self.assertAlmostEqual(ranges[5][1], 3)
        for x in (-143.01, 143.01):
            self.assertFalse(rail.attachment_position_check(x)["passed"])

    def test_longer_roof_keeps_the_same_local_contact_travel(self):
        from gondola.cad import translated_shape
        from gondola.parts import rail
        from gondola.validation import rail_contact

        shape = rail.rail_shape()
        for length in (16, 18, 32):
            ranges = rail.supported_slot_ranges(contact_length=length)
            self.assertEqual(
                ranges, tuple((x - 3, x + 3) for x in range(-140, 141, 28))
            )
            for index in (0, 5, 10):
                low, high = ranges[index]
                for x in (low, (low + high) / 2, high):
                    self.assertTrue(
                        rail_contact.attachment_check(
                            translated_shape(shape, x=-x), contact_length=length
                        )["passed"]
                    )
                self.assertFalse(
                    rail.attachment_position_check(high + 0.01, contact_length=length)[
                        "passed"
                    ]
                )
            mount = rail.mount_base_shape(length=length)
            self.assertAlmostEqual(mount.BoundBox.XLength, length)
            # Changing the upper roof never grows its lower bearing cheeks.
            section = mount.common(
                Part.makeLine(App.Vector(-20, -2.5, 8), App.Vector(20, -2.5, 8))
            )
            self.assertAlmostEqual(section.Length, 10)

    def test_longer_slots_keep_end_ligaments_and_local_contact_limits(self):
        from gondola.parts import rail
        from gondola.validation.rail_mount import _independent_slot_sections

        shape = rail.rail_shape()
        slots = _independent_slot_sections(shape)
        self.assertTrue(slots["passed"], slots)
        self.assertEqual(slots["slot_overall_length_mm"], 9.4)
        self.assertEqual(slots["wall_end_ligament_mm"], 4.3)
        self.assertEqual(slots["upper_web_mm"], 1.8)
        self.assertEqual(slots["lower_web_mm"], 2.8)
        self.assertTrue(rail.attachment_position_check(3)["passed"])
        self.assertFalse(rail.attachment_position_check(3.01)["passed"])
        # The extra 0.2mm shank clearance at the round ends is a fit allowance.
        # It does not extend the intended travel or its 1mm contact end reserve.
        self.assertFalse(rail.attachment_position_check(3.1)["passed"])
        blocked = shape.fuse(Part.makeBox(1, 2.5, 3.4, App.Vector(2, -1.25, 4.3)))
        self.assertFalse(_independent_slot_sections(blocked)["passed"])
        thin_end = shape.cut(Part.makeBox(1, 2.5, 5, App.Vector(8, -1.25, 4)))
        self.assertFalse(_independent_slot_sections(thin_end)["passed"])

    def test_shared_pitch_matches_walls_for_six_mm_module_trim(self):
        from gondola.cad import translated_shape
        from gondola.parts import propulsion, rail
        from gondola.validation.rail_mount import paired_spine_support_check

        frame, shape = propulsion.fixed_frame_shape(), rail.rail_shape()
        self.assertEqual(
            rail.supported_slot_ranges(300, 38, shared_drive=True)[5], (-3, 3)
        )
        ranges = rail.shared_module_ranges()
        self.assertEqual(len(ranges), 10)
        self.assertEqual(ranges[0], (-129, -123))
        self.assertEqual(ranges[-1], (123, 129))
        self.assertEqual(ranges[4:6], ((-17, -11), (11, 17)))
        for delta in (-3, 0, 3):
            station = -14 + delta
            for axis in (station - 14, station + 14):
                position = rail.attachment_position_check(
                    axis, contact_length=38, shared_drive=True
                )
                self.assertTrue(position["passed"], position)
                self.assertGreaterEqual(
                    position["minimum_centred_contact_end_margin_mm"], 1
                )
            seats = paired_spine_support_check(
                translated_shape(shape, x=-station), frame
            )
            self.assertTrue(seats["passed"], seats)
            self.assertEqual(len(seats["wall_supports"]), 2)
            self.assertTrue(all(row["passed"] for row in seats["wall_supports"]))
        for axis in (-3.01, 3.01, 14):
            self.assertFalse(
                rail.attachment_position_check(
                    axis, contact_length=38, shared_drive=True
                )["passed"]
            )
        for obsolete in (12, 16, 24, 40):
            with self.assertRaises(ValueError):
                rail.supported_slot_ranges(contact_length=obsolete, shared_drive=True)

    def test_each_local_crown_and_contact_zone_is_required(self):
        from gondola.cad import translated_shape
        from gondola.parts import propulsion, rail
        from gondola.validation.rail_mount import paired_spine_support_check

        frame = propulsion.fixed_frame_shape()
        local_rail = translated_shape(rail.rail_shape(), x=14)
        for axis in (-14, 14):
            missing_crown = frame.cut(
                Part.makeBox(0.5, 1, 0.4, App.Vector(axis - 0.25, -3, 1.5))
            )
            self.assertFalse(
                paired_spine_support_check(local_rail, missing_crown)["passed"]
            )
            missing_wall = local_rail.cut(
                Part.makeBox(1, 2.5, 2, App.Vector(axis - 0.5, -1.25, 8))
            )
            self.assertFalse(paired_spine_support_check(missing_wall, frame)["passed"])

    def test_u_saddle_seats_and_lifts_without_deflecting_ears(self):
        from gondola.validation import rail_contact

        report = rail_contact.attachment_check()
        self.assertTrue(report["passed"], report)
        self.assertEqual(
            report["continuous_vertical_removal"]["method"],
            "continuous upward planar-face sweep",
        )
        self.assertEqual(report["bottom_datum_contacts"], [])
        self.assertAlmostEqual(report["top_bearing"]["nominal_area_mm2"], 40)
        self.assertAlmostEqual(report["blocked_lower_clearance_mm3"], 0)
        self.assertAlmostEqual(report["missing_flat_side_contact_mm3"], 0)

    def test_missing_clamp_leg_and_top_datum_are_rejected(self):
        from gondola.parts import rail
        from gondola.validation import rail_contact

        for cut in (
            Part.makeBox(2, 2.5, 1, App.Vector(3, -1.75, 3)),
            Part.makeBox(0.5, 2.5, 0.3, App.Vector(-0.25, -1.25, 9.5)),
        ):
            with self.subTest(cut=cut.BoundBox):
                self.assertFalse(
                    rail_contact.attachment_check(
                        mount=rail.mount_base_shape().cut(cut)
                    )["passed"]
                )

    def test_plain_lower_legs_clear_roots_and_full_roof_bears_on_wall(self):
        from gondola.parts import rail
        from gondola.validation import rail_contact

        mount = rail.mount_base_shape()
        for x in (-3, -1, 0, 1, 3):
            for y in (-2.5, 2.5):
                ray = Part.makeLine(App.Vector(x, y, 1), App.Vector(x, y, 4))
                section = mount.common(ray)
                self.assertAlmostEqual(section.BoundBox.ZMin, 2.5)
                self.assertAlmostEqual(section.Length, 1.5)
        gap = Part.makeBox(16, 12, 2.5, App.Vector(-8, -6, 0))
        self.assertLess(abs(gap.common(mount).Volume), 1e-7)
        self.assertAlmostEqual(
            mount.common(
                Part.makeLine(App.Vector(0, 0, 9.5), App.Vector(0, 0, 12.5))
            ).Length,
            3,
        )
        blocked = mount.fuse(Part.makeBox(2, 1, 0.2, App.Vector(-1, 2, 2.3)))
        report = rail_contact.attachment_check(mount=blocked)
        self.assertFalse(report["passed"])
        self.assertGreater(report["blocked_lower_clearance_mm3"], 0)

    def test_added_hook_fails_continuous_vertical_release(self):
        from gondola.parts import rail
        from gondola.validation import rail_contact

        # A tongue enters the clear slot while seated but catches its ceiling.
        hook = Part.makeBox(1, 3, 0.3, App.Vector(-0.5, -1.5, 5.85))
        report = rail_contact.attachment_check(mount=rail.mount_base_shape().fuse(hook))
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
        from gondola.validation import rail_contact

        existing_mount = rail.mount_base_shape()
        queries = (
            lambda length: rail.attachment_windows(contact_length=length),
            lambda length: rail.supported_slot_ranges(contact_length=length),
            lambda length: rail.attachment_position_check(0, contact_length=length),
            lambda length: rail.attachment_contract(contact_length=length),
            lambda length: rail.mount_base_shape(length=length),
            # Supplying a shape must not bypass the dimensional contract.
            lambda length: rail_contact.attachment_check(
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
        for length, expected_windows in ((16, 11), (18, 11), (24, 11)):
            contract = rail.attachment_contract(contact_length=length)
            self.assertEqual(contract["mount_contact_length_mm"], length)
            self.assertEqual(
                len(contract["supported_bolt_axis_ranges_x_mm"]), expected_windows
            )

    def test_tape_pairs_and_process_matched_coupons(self):
        from gondola.cad import translated_shape
        from gondola.parts import rail
        from gondola.validation import rail_contact

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
                self.assertEqual(contract["wall_segments_x_mm"], [[-9, 9]])
                self.assertEqual(contract["free_base_spans_x_mm"], [])
                self.assertIsNone(contract["free_span_minimum_width_mm"])
                ranges = contract["supported_bolt_axis_ranges_x_mm"]
                self.assertEqual(len(ranges), 1)
                self.assertAlmostEqual(ranges[0][0], -3)
                self.assertAlmostEqual(ranges[0][1], 3)
            rail_contract = json.loads(doc.ContinuousRail.RailAttachmentContract)
            self.assertEqual(rail_contract["rail_length_mm"], 300)
            self.assertEqual(rail_contract["free_span_minimum_width_mm"], 6)
            self.assertTrue(
                rail_contact.attachment_check(
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
