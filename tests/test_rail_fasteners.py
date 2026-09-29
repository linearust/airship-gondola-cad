"""Functional regressions for headed rail bolts and finished hex capture."""

import unittest
from unittest.mock import patch

try:
    import FreeCAD as App
except ImportError:
    App = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class RailFastenerTests(unittest.TestCase):
    def test_frame_relief_changes_only_the_two_nut_entry_mouths(self):
        import Part

        from gondola.parts import propulsion, rail
        from gondola.print_export import geometry_comparison
        from gondola.validation.assembly import _fixed_frame_nut_entry_relief

        with patch.object(
            propulsion, "_chamfer_rail_nut_entries", side_effect=lambda s: s
        ):
            original = propulsion.fixed_frame_shape()
        frame = propulsion.fixed_frame_shape()
        expected = original.cut(_fixed_frame_nut_entry_relief())
        comparison = geometry_comparison(frame, expected)
        self.assertLess(comparison["difference_mm3"], 1e-6)
        self.assertAlmostEqual(original.Volume - frame.Volume, 1.584, places=6)
        # Full hex seat and nut reaction material are well inside the entrances.
        central = Part.makeBox(6, 22, 9.2, App.Vector(-3, -11, 2.2))
        self.assertLess(
            original.common(central).cut(frame.common(central)).Volume, 1e-7
        )
        # The through rail channel and its running capture surfaces stay intact.
        channel = Part.makeBox(18, 11, 9.2, App.Vector(-9, -5.5, 2.2))
        self.assertLess(
            original.common(channel).cut(frame.common(channel)).Volume, 1e-7
        )
        # Include the existing rail-entry bevel: at the very end the inner
        # lip must still be at least 1.55 mm, the outer nut wall 1.85 mm.
        for x in (8.4, 8.7, 8.99, 8.999):
            for sign in (-1, 1):
                for y0, y1, minimum in ((5.0, 6.95, 1.55), (9.15, 11.0, 1.85)):
                    probe = Part.makeLine(
                        App.Vector(sign * x, sign * y0, 6.9),
                        App.Vector(sign * x, sign * y1, 6.9),
                    )
                    self.assertGreaterEqual(frame.common(probe).Length, minimum - 1e-7)
                    self.assertAlmostEqual(
                        frame.common(probe).Length, original.common(probe).Length
                    )
        for sign in (-1, 1):
            nut = rail.nut_shape(rail.fasteners.HEX_NUT_MIN_AF)
            nut.rotate(App.Vector(0, 0, rail.CLAMP_Z), App.Vector(0, 1, 0), 30)
            if sign < 0:
                nut = rail.half_turn(nut)
            self.assertGreater(abs(frame.common(nut).Volume), 1e-5)

    def test_narrow_finishing_tool_reaches_both_throats_in_complete_bare_frame(self):
        import Part

        from gondola.parts import propulsion, rail

        frame = propulsion.fixed_frame_shape()
        # A declared 2 mm straight finishing tip reaches the nut axis from
        # outside. A 5 mm handle begins 3 mm beyond the part; this is not a
        # guarantee for the supplier's actual tool or assembled hardware.
        tip = Part.makeCylinder(1, 12, App.Vector(0, 8.05, 6.9), App.Vector(1, 0, 0))
        handle = Part.makeCylinder(
            2.5, 20, App.Vector(12, 8.05, 6.9), App.Vector(1, 0, 0)
        )
        tool = tip.fuse(handle)
        too_large = Part.makeCylinder(
            1.2, 12, App.Vector(0, 8.05, 6.9), App.Vector(1, 0, 0)
        )
        for transform in (lambda s: s, rail.half_turn):
            self.assertLess(frame.common(transform(tool)).Volume, 1e-7)
            self.assertGreater(frame.common(transform(too_large)).Volume, 0.1)
        with patch.object(
            propulsion, "_chamfer_rail_nut_entries", side_effect=lambda s: s
        ):
            original = propulsion.fixed_frame_shape()
        for angle in (-7, 7):
            inclined = tool.copy()
            inclined.rotate(App.Vector(0, 8.05, 6.9), App.Vector(0, 1, 0), angle)
            for transform in (lambda s: s, rail.half_turn):
                # The vertical approach is newly possible, while the same
                # 2 mm tip still respects the unchanged axial throat width.
                self.assertLess(frame.common(transform(inclined)).Volume, 1e-7)
                self.assertGreater(original.common(transform(inclined)).Volume, 1e-5)

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

    def test_integral_frame_clears_head_l_key_and_continuous_hex_insertion(self):
        from gondola.parts import propulsion
        from gondola.validation.propulsion import _record_rail_fit_checks

        frame = propulsion.fixed_frame_shape()
        report = {}
        _record_rail_fit_checks(report, frame, {"PropulsionFixedFrame": frame})
        for name, value in report.items():
            if name.endswith("_overlap_mm3"):
                self.assertLess(value, 1e-6, (name, value))
        for side in ("positive", "negative"):
            self.assertTrue(report[side + "_clamp_key_service"]["passed"], report)
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

    def test_l_key_service_includes_bounded_socket_insertion_and_whole_screw(self):
        from gondola.parts import rail
        from gondola.validation.rail_access import rail_key_service_check

        screw = rail.clamp_screw_shape()
        for inserted_leg in ("short", "long"):
            with self.subTest(inserted_leg=inserted_leg):
                result = rail_key_service_check(
                    {"operated_screw": screw},
                    screw=screw,
                    screw_name="operated_screw",
                    inserted_leg=inserted_leg,
                )
                self.assertTrue(result["passed"], result)
                self.assertEqual(result["socket_insertion_acceptance_mm"], [0.0, 2.0])
                self.assertEqual(
                    result["continuous_working_sector"]["axial_offset_range_mm"],
                    [-2.1, 1.2],
                )
                self.assertIn("operated_screw", result["checked_objects"])
                axial = result["continuous_working_sector"]["axial_leg_translation"]
                bent = result["continuous_working_sector"][
                    "bent_handle_rotation_and_translation"
                ]
                self.assertIn("operated_screw", axial["obstacles"])
                self.assertIn("operated_screw", bent["checked_objects"])

    def test_l_key_certificate_rejects_obstacle_between_clear_arc_endpoints(self):
        import math

        import Part

        from gondola.parts import rail
        from gondola.validation.rail_access import (
            KEY_AXIAL_CENTRELINE_MM,
            key_envelope,
            working_sector_check,
        )

        head = rail.clamp_screw_shape().BoundBox.YMax
        tool = key_envelope(head)
        radius = 30.0
        obstruction = Part.makeBox(
            1.0,
            1.0,
            1.0,
            App.Vector(
                -radius * math.cos(math.radians(30)) - 0.5,
                head + 0.1 + KEY_AXIAL_CENTRELINE_MM - 0.5,
                rail.CLAMP_Z + radius * math.sin(math.radians(30)) - 0.5,
            ),
        )
        axis = App.Vector(0, 0, rail.CLAMP_Z)
        for angle in (0, 60):
            endpoint = tool.copy()
            endpoint.rotate(axis, App.Vector(0, 1, 0), angle)
            self.assertLess(abs(endpoint.common(obstruction).Volume), 1e-6)
        result = working_sector_check(tool, {"mid_arc_block": obstruction}, axis)
        self.assertFalse(result["passed"], result)
        self.assertEqual(result["collisions"][0]["part"], "mid_arc_block")

    def test_l_key_service_rejects_lateral_exit_obstacle_outside_working_arc(self):
        import Part

        from gondola.parts import rail
        from gondola.validation.rail_access import rail_key_service_check

        obstruction = Part.makeBox(2, 2, 2, App.Vector(-61, 23, rail.CLAMP_Z - 1))
        result = rail_key_service_check({"side_exit_block": obstruction})
        self.assertTrue(result["continuous_working_sector"]["passed"], result)
        self.assertFalse(
            result["staged_key_removal_and_reverse_insertion"]["passed"], result
        )
        self.assertFalse(result["passed"], result)

    def test_l_key_certificate_cannot_pass_an_unresolved_interval(self):
        import Part

        from gondola.parts import rail
        from gondola.validation.rail_access import key_envelope, working_sector_check

        head = rail.clamp_screw_shape().BoundBox.YMax
        tool = key_envelope(head)
        result = working_sector_check(
            tool,
            {
                "near_but_clear": Part.makeBox(
                    1, 1, 1, App.Vector(-10, head + 16.2, rail.CLAMP_Z)
                )
            },
            App.Vector(0, 0, rail.CLAMP_Z),
            max_depth=0,
        )
        self.assertFalse(result["passed"], result)
        self.assertIn("could not resolve", result["error"])


if __name__ == "__main__":
    unittest.main()
