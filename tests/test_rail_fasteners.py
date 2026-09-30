"""Exposed M2 hardware, nominal support and genuine engagement failures."""

import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class RailFastenerTests(unittest.TestCase):
    def test_exposed_nut_has_continuous_side_release(self):
        from gondola.parts import rail

        report = rail.attachment_check()
        self.assertTrue(report["passed"], report)
        self.assertIn("face-prism", report["continuous_nut_release"]["method"])
        self.assertAlmostEqual(report["bolt_tip_beyond_nut_mm"], 1.4)
        self.assertTrue(report["full_nominal_nut_height_engaged"])
        self.assertGreater(report["nut_bearing_area_outside_slot_mm2"], 4)
        self.assertIn("tool", report["scope"])

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

        section = rail.rail_shape(50, (0,)).cut(
            Part.makeBox(1, 0.5, 0.3, App.Vector(-0.5, 0.9, 8))
        )
        report = rail.attachment_check(section)
        self.assertFalse(report["passed"])
        self.assertGreater(report["missing_nut_support_mm3"], 0)

    def test_missing_head_bearing_land_rejected(self):
        from gondola.parts import rail

        mount = rail.mount_base_shape().cut(
            Part.makeBox(1, 0.5, 0.3, App.Vector(-0.5, -3.75, 8))
        )
        report = rail.attachment_check(mount=mount)
        self.assertFalse(report["passed"])
        self.assertGreater(report["missing_head_support_mm3"], 0)

    def test_short_bolt_without_full_engagement_is_rejected(self):
        from gondola.parts import rail

        report = rail.attachment_check(screw_length=6)
        self.assertFalse(report["passed"])
        self.assertFalse(report["full_nominal_nut_height_engaged"])
        self.assertAlmostEqual(report["bolt_tip_beyond_nut_mm"], -0.6)

    def test_actual_m2_kit_head_envelope_and_horizontal_axis(self):
        from gondola.parts import rail

        shape = rail.attachment_screw_shape()
        bounds = shape.BoundBox
        self.assertAlmostEqual(bounds.XLength, 4.5)
        self.assertAlmostEqual(bounds.ZLength, 4.5)
        self.assertAlmostEqual(bounds.YMin, -5.75)
        self.assertAlmostEqual(bounds.YMax, 4.25)
        self.assertAlmostEqual(bounds.ZMin, 4.25)

    def test_hardware_skus_and_propulsion_offset(self):
        from gondola.parts import rail

        doc = App.newDocument("M2SideRailHardwareTest")
        try:
            group = doc.addObject("App::Part", "Host")
            for prefix, offset in (("FC", 0), ("Propulsion", 20)):
                screw, nut = rail.build_attachment_hardware(
                    doc, group, prefix, x_offset=offset
                )
                self.assertEqual(screw.HardwareSKU, "M2X8_BUTTON_HEAD")
                self.assertEqual(nut.HardwareSKU, "M2_HEX_NUT")
                self.assertFalse(screw.PrintPart)
                self.assertFalse(nut.PrintPart)
                self.assertEqual(screw.ThreadPitch.Value, 0.4)
                self.assertAlmostEqual(screw.Shape.BoundBox.Center.x, offset)
                self.assertAlmostEqual(nut.Shape.BoundBox.YMin, 1.25)
                self.assertAlmostEqual(nut.Shape.BoundBox.YMax, 2.85)
                self.assertIn("acceptance envelope", screw.Notes)
        finally:
            App.closeDocument(doc.Name)

    def test_no_claim_of_automatic_alignment_or_qualified_clamping(self):
        from gondola.parts import rail

        contract = rail.attachment_contract()
        self.assertFalse(contract["holding_force_verified"])
        self.assertFalse(contract["physical_fit_verified"])
        self.assertIn("no full-length", contract["assembly"])
        self.assertTrue(rail.validate_mechanism()["passed"])


if __name__ == "__main__":
    unittest.main()
