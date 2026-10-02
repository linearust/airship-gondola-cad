"""Recessed M3 hardware, nominal support and genuine engagement failures."""

import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class RailFastenerTests(unittest.TestCase):
    def test_open_bottom_recesses_retain_closed_throats_and_axial_floors(self):
        from gondola.parts import rail

        for mount, x, head_y, nut_y, floor_y, bottom in (
            (rail.mount_base_shape(), 0, -5.25, 3.25, 1.25, 1.5),
            (
                rail.attachment_shoe_shapes(shared_drive=True)[0],
                14,
                -5.25,
                3.25,
                1.25,
                2.5,
            ),
        ):
            with self.subTest(x=x):
                # Full-width mouths open only in the shallow outside recesses.
                for width, depth, y in ((6.4, 1.9, head_y), (5.9, 1.9, nut_y)):
                    mouth = Part.makeBox(
                        width,
                        depth,
                        4.2 - bottom,
                        App.Vector(x - width / 2, y, bottom),
                    )
                    self.assertLess(abs(mouth.common(mount).Volume), 1e-7)
                # The M3 through-hole remains bounded below in both load floors.
                for y in (head_y + 2, floor_y):
                    floor = Part.makeBox(
                        3.4,
                        2,
                        0.7,
                        App.Vector(x - 1.7, y, 3.5),
                    )
                    self.assertLess(abs(floor.cut(mount).Volume), 1e-7)
        nut = rail.nut_shape()
        self.assertAlmostEqual(nut.BoundBox.XLength, 5.5)
        self.assertGreater(nut.BoundBox.ZLength, 6.3)

    def test_recessed_nut_has_continuous_side_release(self):
        from gondola.validation import rail_contact

        report = rail_contact.attachment_check()
        self.assertTrue(report["passed"], report)
        self.assertIn("face-prism", report["continuous_nut_release"]["method"])
        self.assertAlmostEqual(report["bolt_tip_beyond_nut_mm"], 1.1)
        self.assertTrue(report["full_nominal_nut_height_engaged"])
        self.assertGreater(report["nut_bearing_area_outside_bore_mm2"], 17)
        self.assertEqual(report["nut_floor_nominal_mm"], 2)
        self.assertAlmostEqual(report["missing_opposite_side_contact_mm3"], 0)
        self.assertAlmostEqual(report["missing_printed_nut_floor_mm3"], 0)
        self.assertIn("tool", report["scope"])

    def test_equal_carrier_legs_retain_partial_nut_capture_and_free_standard_nuts(self):
        from gondola.parts import rail
        from gondola.validation.rail_access import nut_capture_check

        mount = rail.mount_base_shape()
        bounds = mount.BoundBox
        self.assertAlmostEqual(bounds.YMin, -5.25)
        self.assertAlmostEqual(bounds.YMax, 5.25)
        report = nut_capture_check(0, rail.nut_shape(), mount)
        self.assertTrue(report["passed"], report)
        self.assertEqual(report["nut_recess_depth_mm"], 2)
        self.assertTrue(report["standard_nut_envelope"]["passed"])
        self.assertGreater(rail.nut_shape().BoundBox.YMax, bounds.YMax)

    def test_oversized_pocket_that_allows_small_standard_nut_rotation_is_rejected(self):
        from gondola.parts import rail
        from gondola.validation.rail_access import nut_capture_check

        mount = rail.mount_base_shape().cut(rail._nut_outer(6.2, 2.1, bearing_y=3.25))
        report = nut_capture_check(0, rail.nut_shape(), mount)
        self.assertFalse(report["standard_nut_envelope"]["passed"])
        self.assertFalse(report["passed"])

    def test_nut_can_load_with_tape_and_all_supported_slot_endpoints(self):
        from gondola.cad import translated_shape, union
        from gondola.parts import rail
        from gondola.validation import rail_contact

        section = rail.rail_shape().fuse(
            union(
                [rail.tape_shape(x, side) for x in rail.PAD_CENTRES for side in (-1, 1)]
            )
        )
        for low, high in rail.supported_slot_ranges():
            for x in (low, high):
                with self.subTest(x=x):
                    self.assertTrue(
                        rail_contact.attachment_check(translated_shape(section, x=-x))[
                            "passed"
                        ]
                    )

    def test_added_nut_side_obstacle_is_rejected(self):
        from gondola.parts import rail
        from gondola.validation import rail_contact

        section = rail.rail_shape(50, (0,)).fuse(
            Part.makeBox(4, 1, 5, App.Vector(-2, 5, 4))
        )
        report = rail_contact.attachment_check(section)
        self.assertFalse(report["passed"])
        self.assertGreater(report["continuous_nut_release"]["overlap_mm3"], 0)

    def test_missing_nut_bearing_land_rejected(self):
        from gondola.parts import rail
        from gondola.validation import rail_contact

        mount = rail.mount_base_shape().cut(
            Part.makeBox(1, 0.5, 0.3, App.Vector(-0.5, 3.24, 8.2))
        )
        report = rail_contact.attachment_check(mount=mount)
        self.assertFalse(report["passed"])
        self.assertGreater(report["missing_nut_support_mm3"], 0)

    def test_internal_nut_floor_void_cannot_pass_on_surface_contact_alone(self):
        from gondola.parts import rail
        from gondola.validation import rail_contact

        mount = rail.mount_base_shape().cut(
            Part.makeBox(1, 0.2, 0.3, App.Vector(-0.5, 2, 8.2))
        )
        report = rail_contact.attachment_check(mount=mount)
        self.assertFalse(report["passed"])
        self.assertAlmostEqual(report["missing_nut_support_mm3"], 0)
        self.assertGreater(report["missing_printed_nut_floor_mm3"], 0)

    def test_clearance_guard_cannot_substitute_for_fitted_far_leg(self):
        from gondola.parts import rail
        from gondola.validation import rail_contact

        mount = rail.mount_base_shape().cut(
            Part.makeBox(16, 0.2, 8.3, App.Vector(-8, 1.25, 2.2))
        )
        report = rail_contact.attachment_check(mount=mount)
        self.assertFalse(report["passed"])
        self.assertGreater(report["missing_opposite_side_contact_mm3"], 0)

    def test_missing_head_bearing_land_rejected(self):
        from gondola.parts import rail
        from gondola.validation import rail_contact

        mount = rail.mount_base_shape().cut(
            Part.makeBox(1, 0.5, 0.3, App.Vector(-0.5, -3.25, 8.2))
        )
        report = rail_contact.attachment_check(mount=mount)
        self.assertFalse(report["passed"])
        self.assertGreater(report["missing_head_support_mm3"], 0)

    def test_short_bolt_without_full_engagement_is_rejected(self):
        from gondola.validation import rail_contact

        report = rail_contact.attachment_check(screw_length=8)
        self.assertFalse(report["passed"])
        self.assertFalse(report["full_nominal_nut_height_engaged"])
        self.assertAlmostEqual(report["bolt_tip_beyond_nut_mm"], -0.9)

    def test_bare_nominal_engagement_without_end_margin_is_rejected(self):
        from gondola.validation import rail_contact

        report = rail_contact.attachment_check(screw_length=9)
        self.assertFalse(report["passed"])
        self.assertTrue(report["full_nominal_nut_height_engaged"])
        self.assertFalse(report["thread_projection_margin_ok"])
        self.assertAlmostEqual(report["bolt_tip_beyond_nut_mm"], 0.1)

    def test_actual_m3_design_head_envelope_and_horizontal_axis(self):
        from gondola.parts import rail

        shape = rail.attachment_screw_shape()
        bounds = shape.BoundBox
        self.assertAlmostEqual(bounds.XLength, 6.0)
        self.assertAlmostEqual(bounds.ZLength, 6.0)
        self.assertAlmostEqual(bounds.YMin, -5.25)
        self.assertAlmostEqual(bounds.YMax, 6.75)
        self.assertAlmostEqual(bounds.ZMin, 3.0)

    def test_hardware_skus_and_propulsion_offset(self):
        from gondola.parts import rail

        doc = App.newDocument("M3SideRailHardwareTest")
        try:
            group = doc.addObject("App::Part", "Host")
            for prefix, offset, shared, expected_sku in (
                ("FC", 0, False, "M3X10_BUTTON_HEAD"),
                ("Propulsion", 14.0, True, "M3X10_BUTTON_HEAD"),
            ):
                hardware = rail.build_attachment_hardware(
                    doc, group, prefix, x_offset=offset, shared_drive=shared
                )
                self.assertEqual(len(hardware), 4 if shared else 2)
                screw, nut = hardware[:2]
                if shared:
                    self.assertAlmostEqual(hardware[2].Shape.BoundBox.Center.x, -14)
                    self.assertAlmostEqual(hardware[3].Shape.BoundBox.YMin, -5.65)
                self.assertEqual(screw.HardwareSKU, expected_sku)
                self.assertEqual(nut.HardwareSKU, "M3_HEX_NUT")
                self.assertFalse(screw.PrintPart)
                self.assertFalse(nut.PrintPart)
                self.assertEqual(screw.ThreadPitch.Value, 0.5)
                self.assertAlmostEqual(screw.Shape.BoundBox.Center.x, offset)
                self.assertAlmostEqual(nut.Shape.BoundBox.YMin, 3.25)
                self.assertAlmostEqual(nut.Shape.BoundBox.YMax, 5.65)
                self.assertIn("acceptance envelope", screw.Notes)
        finally:
            App.closeDocument(doc.Name)

    def test_paired_clamp_uses_standard_shoe_floors_and_full_nut_engagement(self):
        from gondola.cad import translated_shape
        from gondola.parts import propulsion, rail
        from gondola.validation import rail_contact
        from gondola.validation.rail_mount import paired_spine_support_check

        complete_frame = propulsion.fixed_frame_shape()
        crop = Part.makeBox(16, 10.5, 12.5, App.Vector(6, -5.25, 0))
        frame = translated_shape(complete_frame.common(crop), x=-14)
        arguments = dict(mount=frame, contact_length=44, shared_drive=True)
        report = rail_contact.attachment_check(**arguments)
        self.assertTrue(report["passed"], report)
        self.assertEqual(report["support_policy"], "paired_wall_top_bearing")
        self.assertEqual(report["checked_centred_contact_length_mm"], 10)
        support = paired_spine_support_check(
            translated_shape(rail.rail_shape(), x=14), complete_frame
        )
        self.assertTrue(support["passed"], support)
        self.assertAlmostEqual(support["top_bearing_area_total_mm2"], 80)
        self.assertAlmostEqual(report["printed_grip_mm"], 6.5)
        self.assertAlmostEqual(report["bolt_tip_beyond_nut_mm"], 1.1)
        self.assertAlmostEqual(report["missing_head_support_mm3"], 0)
        self.assertAlmostEqual(report["missing_nut_support_mm3"], 0)
        self.assertAlmostEqual(report["missing_printed_nut_floor_mm3"], 0)
        short = rail_contact.attachment_check(**arguments, screw_length=8)
        self.assertFalse(short["passed"])
        self.assertAlmostEqual(short["bolt_tip_beyond_nut_mm"], -0.9)
        for y, key in (
            (-3.25, "missing_head_support_mm3"),
            (3.24, "missing_nut_support_mm3"),
        ):
            damaged = frame.cut(Part.makeBox(1, 0.5, 0.3, App.Vector(-0.5, y, 8.2)))
            failed = rail_contact.attachment_check(**{**arguments, "mount": damaged})
            self.assertFalse(failed["passed"])
            self.assertGreater(failed[key], 0)

    def test_shared_clamp_declares_common_hardware_and_coplanar_service_scope(self):
        from gondola.parts import rail

        contract = rail.attachment_contract(44, shared_drive=True)
        self.assertEqual(contract["bolt_length_mm"], 10)
        self.assertEqual(contract["head_bearing_y_mm"], -3.25)
        self.assertEqual(contract["nut_bearing_y_mm"], 3.25)
        self.assertEqual(contract["printed_grip_mm"], 6.5)
        self.assertTrue(contract["paired_propulsion_clamp"])
        self.assertEqual(contract["mount_contact_length_mm"], 44)
        self.assertEqual(contract["top_bearing_roof_length_mm"], 16)
        self.assertEqual(contract["centred_load_zone_length_mm"], 10)
        self.assertEqual(contract["shared_minimum_wall_seat_length_mm"], 14)
        self.assertEqual(contract["shared_minimum_total_seat_length_mm"], 28)
        self.assertEqual(contract["shared_usable_trim_half_range_mm"], 3)
        self.assertIsNone(contract["local_wall_tilt_screen_degrees"])
        self.assertIn("coplanar", contract["shared_joint_service"])
        self.assertIn(
            "Support the complete propulsion assembly", contract["shared_joint_service"]
        )
        screw = rail.attachment_screw_shape()
        self.assertAlmostEqual(screw.BoundBox.YMin, -5.25)
        self.assertAlmostEqual(screw.BoundBox.YMax, 6.75)
        with self.assertRaises(ValueError):
            rail.attachment_contract(shared_drive=1)

    def test_no_claim_of_automatic_alignment_or_qualified_clamping(self):
        from gondola.parts import rail
        from gondola.validation import rail_contact

        contract = rail.attachment_contract()
        self.assertFalse(contract["holding_force_verified"])
        self.assertFalse(contract["physical_fit_verified"])
        self.assertEqual(contract["support_policy"], "wall_top_bearing")
        self.assertEqual(contract["intended_bolt_half_range_mm"], 3)
        self.assertIn(
            "Seat the roof fully on the wall top and both local side faces",
            contract["assembly"],
        )
        self.assertIn(
            "Remove bolts and nuts before lifting between wall segments",
            contract["assembly"],
        )
        self.assertTrue(rail_contact.validate_mechanism()["passed"])


if __name__ == "__main__":
    unittest.main()
