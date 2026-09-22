"""Functional regressions for headed rail bolts and finished hex capture."""

import unittest

try:
    import FreeCAD as App
except ImportError:
    App = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class RailFastenerTests(unittest.TestCase):
    def test_headed_clamp_fits_both_approach_sides_and_retains_the_rail(self):
        from gondola.parts import rail

        self.assertTrue(rail.validate_mechanism()["passed"])

    def test_six_mm_headed_bolt_bottoms_on_wall_but_eight_mm_clears(self):
        from gondola.parts import purchased_hardware, rail

        shoe = rail.shoe_shape()
        short = purchased_hardware.screw_shape(6).copy()
        short.Placement = App.Placement(
            App.Vector(0, rail.HEAD_WIDTH / 2 - rail.CLAMP_SHIFT_Y + 6, rail.CLAMP_Z),
            App.Rotation(App.Vector(0, 0, 1), App.Vector(0, -1, 0)),
        )
        self.assertGreater(abs(short.common(shoe).Volume), 0.01)
        self.assertLess(abs(rail.clamp_screw_shape().common(shoe).Volume), 1e-6)

    def test_finished_hex_seat_accepts_insertion_but_blocks_rotation(self):
        from gondola.parts import rail

        result = rail.hex_nut_capture_check()
        self.assertTrue(result["passed"], result)
        self.assertFalse(result["as_printed_capture_guaranteed"])
        self.assertFalse(result["physical_fit_verified"])

    def test_old_wide_slot_allowance_cannot_capture_the_hex_nut(self):
        from gondola.parts import rail

        oversize_shoe = rail.shoe_shape(4.9)
        nut = rail.nut_shape(rail.fasteners.HEX_NUT_MIN_AF)
        nut.rotate(App.Vector(0, 0, rail.CLAMP_Z), App.Vector(0, 1, 0), 30)
        self.assertLess(abs(nut.common(oversize_shoe).Volume), 1e-6)

    def test_integral_frame_clears_head_long_key_and_continuous_hex_insertion(self):
        from gondola.parts import propulsion
        from gondola.validation.propulsion import _record_rail_fit_checks

        frame = propulsion.fixed_frame_shape()
        report = {}
        _record_rail_fit_checks(report, frame, {"PropulsionFixedFrame": frame})
        for name, value in report.items():
            if name.endswith("_overlap_mm3"):
                self.assertLess(value, 1e-6, (name, value))
        for row in report["continuous_nut_loading"]:
            self.assertTrue(row["passed"], row)
            self.assertIn("face-prism", row["segments"][0]["method"])

    def test_nut_insertion_audit_rejects_material_in_its_loading_port(self):
        import Part

        from gondola.parts import propulsion, rail
        from gondola.validation.propulsion import _record_rail_fit_checks

        frame = propulsion.fixed_frame_shape()
        obstruction = Part.makeBox(
            1,
            rail.NUT_POCKET_DEPTH,
            rail.NUT_POCKET_AF,
            App.Vector(6, rail.NUT_POCKET_Y, rail.CLAMP_Z - rail.NUT_POCKET_AF / 2),
        )
        frame = frame.fuse(obstruction)
        report = {}
        _record_rail_fit_checks(report, frame, {"PropulsionFixedFrame": frame})
        self.assertFalse(report["continuous_nut_loading"][0]["passed"])

    def test_complete_clamp_loosening_sweep_clears_integral_frame_both_sides(self):
        from gondola.parts import propulsion, rail
        from gondola.validation.geometry import translation_sweep
        from gondola.validation.manufacturing import planar_wall_regions

        frame = propulsion.fixed_frame_shape()
        self.assertTrue(frame.isValid())
        self.assertEqual(len(frame.Solids), 1)
        for side in (1, -1):
            with self.subTest(side=side):
                screw = rail.clamp_screw_shape()
                if side < 0:
                    screw = rail.half_turn(screw)
                swept, method = translation_sweep(
                    screw, (0, side * rail.RELEASE_TRAVEL, 0)
                )
                self.assertIn("face-prism", method)
                self.assertLess(abs(swept.common(frame).Volume), 1e-6)
        for region in planar_wall_regions(frame):
            self.assertGreaterEqual(region["material_thickness_mm"], 1.5 - 1e-5)


if __name__ == "__main__":
    unittest.main()
