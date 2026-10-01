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
                (-150, -130),
                (-122, -102),
                (-94, -74),
                (-66, -46),
                (-38, -18),
                (-10, 10),
                (18, 38),
                (46, 66),
                (74, 94),
                (102, 122),
                (130, 150),
            ],
        )

    def test_straight_base_and_all_supports_share_regular_geometry(self):
        from gondola.parts import rail

        shape = rail.rail_shape()
        intervals = rail.wall_segments()
        self.assertEqual([b - a for a, b in intervals], [20] * 11)
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

    def test_slot_limits_retain_whole_foot_and_reject_gap_positions(self):
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
                        report["minimum_full_foot_end_margin_mm"], 0.8 - 1e-6
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
        self.assertEqual(ranges[0], (-141.0, -138.8))
        self.assertEqual(ranges[-1], (138.8, 141.0))
        self.assertAlmostEqual(ranges[5][0], -1.2)
        self.assertAlmostEqual(ranges[5][1], 1.2)
        for x in (-141.01, 141.01):
            self.assertFalse(rail.attachment_position_check(x)["passed"])

    def test_longer_generic_foot_does_not_inherit_shared_spine_travel(self):
        from gondola.cad import translated_shape
        from gondola.parts import rail
        from gondola.validation import rail_contact

        shape = rail.rail_shape()
        ranges = rail.supported_slot_ranges(contact_length=18)
        self.assertEqual(len(ranges), 11)
        for (low, high), centre in zip(ranges, range(-140, 141, 28)):
            self.assertAlmostEqual(low, max(centre - 0.2, -140))
            self.assertAlmostEqual(high, min(centre + 0.2, 140))
            for x in (low, centre, high):
                self.assertTrue(
                    rail.attachment_position_check(x, contact_length=18)["passed"]
                )
                self.assertTrue(
                    rail_contact.attachment_check(
                        translated_shape(shape, x=-x), contact_length=18
                    )["passed"]
                )
            self.assertFalse(
                rail.attachment_position_check(high + 0.01, contact_length=18)["passed"]
            )
        self.assertEqual(rail.supported_slot_ranges(contact_length=32), ())
        self.assertAlmostEqual(rail.mount_base_shape(length=18).BoundBox.XLength, 18)

    def test_longer_slots_keep_end_ligaments_and_carrier_full_foot_limits(self):
        from gondola.parts import rail
        from gondola.validation.rail_mount import _independent_slot_sections

        shape = rail.rail_shape()
        slots = _independent_slot_sections(shape)
        self.assertTrue(slots["passed"], slots)
        self.assertEqual(slots["slot_overall_length_mm"], 9.4)
        self.assertEqual(slots["wall_end_ligament_mm"], 5.3)
        self.assertEqual(slots["upper_web_mm"], 1.8)
        self.assertEqual(slots["lower_web_mm"], 2.8)
        self.assertTrue(rail.attachment_position_check(1.2)["passed"])
        self.assertFalse(rail.attachment_position_check(1.21)["passed"])
        # A visibly open bolt slot does not authorize overhanging carrier feet.
        self.assertFalse(rail.attachment_position_check(6)["passed"])
        blocked = shape.fuse(Part.makeBox(1, 2.5, 3.4, App.Vector(2, -1.25, 4.3)))
        self.assertFalse(_independent_slot_sections(blocked)["passed"])
        thin_end = shape.cut(Part.makeBox(1, 2.5, 5, App.Vector(9, -1.25, 4)))
        self.assertFalse(_independent_slot_sections(thin_end)["passed"])

    def test_shared_spine_intersects_bolt_ranges_into_four_mm_module_trim(self):
        from gondola.cad import translated_shape
        from gondola.parts import propulsion, rail
        from gondola.validation.rail_mount import paired_spine_support_check

        frame, shape = propulsion.fixed_frame_shape(), rail.rail_shape()
        bolt_ranges = rail.supported_slot_ranges(300, 40, shared_drive=True)
        self.assertEqual(bolt_ranges[5], (-3, 3))
        module_ranges = rail.shared_module_ranges()
        self.assertEqual(len(module_ranges), 10)
        self.assertEqual(module_ranges[0], (-128, -124))
        self.assertEqual(module_ranges[-1], (124, 128))
        self.assertEqual(module_ranges[4:6], ((-16, -12), (12, 16)))
        for delta, expected in ((-2, [18, 14]), (0, [16, 16]), (2, [14, 18])):
            station = -14 + delta
            for axis in (station - 15, station + 15):
                position = rail.attachment_position_check(
                    axis, contact_length=40, shared_drive=True
                )
                self.assertTrue(position["passed"], position)
                self.assertGreaterEqual(
                    position["minimum_centred_contact_end_margin_mm"], 2
                )
            seats = paired_spine_support_check(
                translated_shape(shape, x=-station), frame
            )
            self.assertTrue(seats["passed"], seats)
            self.assertEqual(
                [row["wall_overlap_length_mm"] for row in seats["wall_supports"]],
                expected,
            )
            self.assertEqual(seats["minimum_bottom_contact_area_mm2"], 140)
        for axis in (-3.01, 3.01, 14):
            self.assertFalse(
                rail.attachment_position_check(
                    axis, contact_length=40, shared_drive=True
                )["passed"]
            )
        for obsolete in (12, 16, 24):
            with self.assertRaises(ValueError):
                rail.supported_slot_ranges(contact_length=obsolete, shared_drive=True)

    def test_shared_seat_outside_clamp_zone_cannot_be_omitted(self):
        from gondola.cad import translated_shape
        from gondola.parts import propulsion, rail
        from gondola.validation.rail_mount import paired_spine_support_check

        frame = propulsion.fixed_frame_shape()
        local_rail = translated_shape(rail.rail_shape(), x=12)  # +2mm propulsion trim
        # X-8 is between the10mm clamp zones; its lower land must still bear.
        missing_bottom = frame.cut(Part.makeBox(1, 1.75, 0.5, App.Vector(-8, -3, 1.5)))
        self.assertFalse(
            paired_spine_support_check(local_rail, missing_bottom)["passed"]
        )
        missing_wall = local_rail.cut(Part.makeBox(1, 2.5, 2, App.Vector(-8, -1.25, 8)))
        self.assertFalse(paired_spine_support_check(missing_wall, frame)["passed"])

    def test_u_saddle_seats_and_lifts_without_deflecting_ears(self):
        from gondola.validation import rail_contact

        report = rail_contact.attachment_check()
        self.assertTrue(report["passed"], report)
        self.assertIn("face-prism", report["continuous_vertical_removal"]["method"])
        self.assertTrue(all(row["passed"] for row in report["bottom_datum_contacts"]))
        self.assertAlmostEqual(report["inner_roof_clearance_mm"], 0.2)
        self.assertAlmostEqual(report["blocked_inner_roof_relief_mm3"], 0)
        self.assertAlmostEqual(report["missing_flat_side_contact_mm3"], 0)

    def test_missing_clamp_leg_and_bottom_land_are_rejected(self):
        from gondola.parts import rail
        from gondola.validation import rail_contact

        for cut in (
            Part.makeBox(2, 2.5, 1, App.Vector(3, -1.75, 3)),
            Part.makeBox(2, 1.75, 0.5, App.Vector(3, -3, 1.5)),
        ):
            with self.subTest(cut=cut.BoundBox):
                self.assertFalse(
                    rail_contact.attachment_check(
                        mount=rail.mount_base_shape().cut(cut)
                    )["passed"]
                )

    def test_bottom_datum_does_not_require_roof_contact(self):
        from gondola.parts import rail
        from gondola.validation import rail_contact

        mount = rail.mount_base_shape()
        for y in (-2.5, 2.5):
            foot = Part.makeLine(App.Vector(3, y, 1.49), App.Vector(3, y, 1.8))
            self.assertAlmostEqual(mount.common(foot).Length, 0.3)
        gap = Part.makeBox(16, 2.5, 0.2, App.Vector(-8, -1.25, 9.5))
        self.assertAlmostEqual(mount.common(gap).Volume, 0)
        self.assertAlmostEqual(
            mount.common(
                Part.makeLine(App.Vector(0, 0, 9.5), App.Vector(0, 0, 12.5))
            ).Length,
            2.8,
        )
        blocked = mount.fuse(Part.makeBox(2, 2.5, 0.1, App.Vector(3, -1.25, 9.6)))
        report = rail_contact.attachment_check(mount=blocked)
        self.assertFalse(report["passed"])
        self.assertGreater(report["blocked_inner_roof_relief_mm3"], 0)
        for side, y in ((-1, -3), (1, 1.25)):
            cut = Part.makeBox(2, 1.75, 0.1, App.Vector(3, y, 1.5))
            missing = rail_contact.attachment_check(mount=mount.cut(cut))
            self.assertFalse(missing["passed"])
            self.assertFalse(
                next(
                    row
                    for row in missing["bottom_datum_contacts"]
                    if row["side"] == side
                )["passed"]
            )

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
        for length, expected_windows in ((16, 11), (18, 11), (24, 0)):
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
                self.assertEqual(contract["wall_segments_x_mm"], [[-10, 10]])
                self.assertEqual(contract["free_base_spans_x_mm"], [])
                self.assertIsNone(contract["free_span_minimum_width_mm"])
                ranges = contract["supported_bolt_axis_ranges_x_mm"]
                self.assertEqual(len(ranges), 1)
                self.assertAlmostEqual(ranges[0][0], -1.2)
                self.assertAlmostEqual(ranges[0][1], 1.2)
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
