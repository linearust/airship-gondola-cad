"""Recessed M3 hardware, nominal support and genuine engagement failures."""

import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class RailFastenerTests(unittest.TestCase):
    def test_recessed_nut_has_continuous_side_release(self):
        from gondola.parts import rail

        report = rail.attachment_check()
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

        section = rail.rail_shape().fuse(
            union(
                [rail.tape_shape(x, side) for x in rail.PAD_CENTRES for side in (-1, 1)]
            )
        )
        for low, high in rail.supported_slot_ranges():
            for x in (low, high):
                with self.subTest(x=x):
                    self.assertTrue(
                        rail.attachment_check(translated_shape(section, x=-x))["passed"]
                    )

    def test_added_nut_side_obstacle_is_rejected(self):
        from gondola.parts import rail

        section = rail.rail_shape(50, (0,)).fuse(
            Part.makeBox(4, 1, 5, App.Vector(-2, 5, 4))
        )
        report = rail.attachment_check(section)
        self.assertFalse(report["passed"])
        self.assertGreater(report["continuous_nut_release"]["overlap_mm3"], 0)

    def test_missing_nut_bearing_land_rejected(self):
        from gondola.parts import rail

        mount = rail.mount_base_shape().cut(
            Part.makeBox(1, 0.5, 0.3, App.Vector(-0.5, 3.24, 9.2))
        )
        report = rail.attachment_check(mount=mount)
        self.assertFalse(report["passed"])
        self.assertGreater(report["missing_nut_support_mm3"], 0)

    def test_internal_nut_floor_void_cannot_pass_on_surface_contact_alone(self):
        from gondola.parts import rail

        mount = rail.mount_base_shape().cut(
            Part.makeBox(1, 0.2, 0.3, App.Vector(-0.5, 2, 9.2))
        )
        report = rail.attachment_check(mount=mount)
        self.assertFalse(report["passed"])
        self.assertAlmostEqual(report["missing_nut_support_mm3"], 0)
        self.assertGreater(report["missing_printed_nut_floor_mm3"], 0)

    def test_clearance_guard_cannot_substitute_for_fitted_far_leg(self):
        from gondola.parts import rail

        mount = rail.mount_base_shape().cut(
            Part.makeBox(16, 0.2, 8.3, App.Vector(-8, 1.25, 2.2))
        )
        report = rail.attachment_check(mount=mount)
        self.assertFalse(report["passed"])
        self.assertGreater(report["missing_opposite_side_contact_mm3"], 0)

    def test_missing_head_bearing_land_rejected(self):
        from gondola.parts import rail

        mount = rail.mount_base_shape().cut(
            Part.makeBox(1, 0.5, 0.3, App.Vector(-0.5, -3.25, 9.2))
        )
        report = rail.attachment_check(mount=mount)
        self.assertFalse(report["passed"])
        self.assertGreater(report["missing_head_support_mm3"], 0)

    def test_short_bolt_without_full_engagement_is_rejected(self):
        from gondola.parts import rail

        report = rail.attachment_check(screw_length=8)
        self.assertFalse(report["passed"])
        self.assertFalse(report["full_nominal_nut_height_engaged"])
        self.assertAlmostEqual(report["bolt_tip_beyond_nut_mm"], -0.9)

    def test_bare_nominal_engagement_without_end_margin_is_rejected(self):
        from gondola.parts import rail

        report = rail.attachment_check(screw_length=9)
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
        self.assertAlmostEqual(bounds.ZMin, 4.0)

    def test_hardware_skus_and_propulsion_offset(self):
        from gondola.parts import rail

        doc = App.newDocument("M3SideRailHardwareTest")
        try:
            group = doc.addObject("App::Part", "Host")
            for prefix, offset, shared, expected_sku in (
                ("FC", 0, False, "M3X10_BUTTON_HEAD"),
                ("Propulsion", 17.0, True, "M3X20_BUTTON_HEAD"),
            ):
                hardware = rail.build_attachment_hardware(
                    doc, group, prefix, x_offset=offset, shared_drive=shared
                )
                self.assertEqual(len(hardware), 4 if shared else 2)
                screw, nut = hardware[:2]
                if shared:
                    self.assertAlmostEqual(hardware[2].Shape.BoundBox.Center.x, -17)
                    self.assertAlmostEqual(hardware[3].Shape.BoundBox.YMin, -10.4)
                self.assertEqual(screw.HardwareSKU, expected_sku)
                self.assertEqual(nut.HardwareSKU, "M3_HEX_NUT")
                self.assertFalse(screw.PrintPart)
                self.assertFalse(nut.PrintPart)
                self.assertEqual(screw.ThreadPitch.Value, 0.5)
                self.assertAlmostEqual(screw.Shape.BoundBox.Center.x, offset)
                self.assertAlmostEqual(nut.Shape.BoundBox.YMin, 8 if shared else 3.25)
                self.assertAlmostEqual(
                    nut.Shape.BoundBox.YMax, 10.4 if shared else 5.65
                )
                self.assertIn("acceptance envelope", screw.Notes)
        finally:
            App.closeDocument(doc.Name)

    def test_shared_clamp_bears_on_actual_bridge_and_engages_full_nut(self):
        from gondola.cad import translated_shape
        from gondola.parts import propulsion, rail, servo_bridge
        from gondola.validation.rail_mount import paired_spine_support_check

        complete_frame = propulsion.fixed_frame_shape()
        crop = Part.makeBox(12, 22, 11, App.Vector(11, -11, 1.5))
        frame = translated_shape(complete_frame.common(crop), x=-17)
        bridge = translated_shape(servo_bridge.bridge_shape().common(crop), x=-17)
        arguments = dict(
            mount=frame,
            head_support=bridge,
            contact_length=58,
            shared_drive=True,
            screw_length=20,
            head_face_y=-9,
            nut_bearing_y=8,
            nut_outer_y=11,
            frame_contact_y=6,
        )
        report = rail.attachment_check(**arguments)
        self.assertTrue(report["passed"], report)
        self.assertEqual(report["support_policy"], "paired_spine_clamp_zone")
        self.assertEqual(report["checked_centred_contact_length_mm"], 12)
        support = paired_spine_support_check(
            translated_shape(rail.rail_shape(), x=17), complete_frame
        )
        self.assertTrue(support["passed"], support)
        self.assertEqual(support["wall_overlap_length_total_mm"], 50)
        self.assertAlmostEqual(report["printed_grip_mm"], 17)
        self.assertAlmostEqual(report["bolt_tip_beyond_nut_mm"], 0.6)
        self.assertAlmostEqual(report["missing_head_support_mm3"], 0)
        self.assertTrue(report["shared_head_support_supplied"])
        self.assertEqual(len(report["frame_saddle_contact_faces"]), 2)
        self.assertTrue(
            all(row["passed"] for row in report["frame_saddle_contact_faces"])
        )
        short = rail.attachment_check(**{**arguments, "screw_length": 12})
        self.assertFalse(short["passed"])
        self.assertAlmostEqual(short["bolt_tip_beyond_nut_mm"], -7.4)
        missing = rail.attachment_check(**{**arguments, "head_support": None})
        self.assertFalse(missing["passed"])
        self.assertGreater(missing["missing_head_support_mm3"], 0)
        far_cheek_removed = bridge.cut(
            Part.makeBox(12, 5, 10.3, App.Vector(-6, 6, 2.2))
        )
        bypassed = rail.attachment_check(
            **{**arguments, "head_support": far_cheek_removed}
        )
        self.assertFalse(bypassed["passed"])
        self.assertAlmostEqual(bypassed["missing_head_support_mm3"], 0)
        self.assertGreater(bypassed["missing_nut_support_mm3"], 0)
        self.assertFalse(bypassed["frame_saddle_contact_faces"][1]["passed"])

    def test_shared_clamp_declares_distinct_hardware_and_service_scope(self):
        from gondola.parts import rail

        contract = rail.attachment_contract(58, shared_drive=True)
        self.assertEqual(contract["bolt_length_mm"], 20)
        self.assertEqual(contract["head_bearing_y_mm"], -9)
        self.assertEqual(contract["nut_bearing_y_mm"], 8)
        self.assertEqual(contract["printed_grip_mm"], 17)
        self.assertTrue(contract["shared_servo_bridge_clamp"])
        self.assertEqual(contract["mount_contact_length_mm"], 58)
        self.assertEqual(contract["centred_load_zone_length_mm"], 12)
        self.assertEqual(contract["shared_minimum_wall_seat_length_mm"], 19)
        self.assertEqual(contract["shared_minimum_total_seat_length_mm"], 45)
        self.assertEqual(contract["shared_usable_trim_half_range_mm"], 6)
        self.assertIn("Support both", contract["shared_joint_service"])
        screw = rail.attachment_screw_shape(20, head_face_y=-9)
        self.assertAlmostEqual(screw.BoundBox.YMin, -11)
        self.assertAlmostEqual(screw.BoundBox.YMax, 11)
        with self.assertRaises(ValueError):
            rail.attachment_contract(shared_drive=1)

    def test_no_claim_of_automatic_alignment_or_qualified_clamping(self):
        from gondola.parts import rail

        contract = rail.attachment_contract()
        self.assertFalse(contract["holding_force_verified"])
        self.assertFalse(contract["physical_fit_verified"])
        self.assertIn("no full-length", contract["assembly"])
        self.assertTrue(rail.validate_mechanism()["passed"])


if __name__ == "__main__":
    unittest.main()
