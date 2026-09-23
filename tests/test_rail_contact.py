"""Rail clamp contact geometry and adverse material-removal regressions."""

import math
import unittest
from unittest.mock import patch

try:
    import FreeCAD as App
except ImportError:
    App = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class RailContactTests(unittest.TestCase):
    def test_flex_reliefs_are_open_through_the_entire_raised_head(self):
        from gondola.parts import rail

        for length in (48, rail.LENGTH):
            with self.subTest(length=length):
                report = rail.flex_relief_check(rail.rail_shape(length, (0,)), length)
                self.assertTrue(report["passed"], report)
                self.assertGreater(report["probe_end_z_mm"], rail.HEAD_TOP)

    def test_thin_roof_left_by_a_short_relief_cut_is_rejected(self):
        import Part

        from gondola.parts import rail

        bridged = rail.rail_shape(48, (0,)).fuse(
            Part.makeBox(
                rail.FLEX_GAP,
                rail.HEAD_WIDTH,
                0.2,
                App.Vector(
                    rail.LAND_PITCH / 2 - rail.FLEX_GAP / 2,
                    -rail.HEAD_WIDTH / 2,
                    rail.HEAD_TOP - 0.2,
                ),
            )
        )
        report = rail.flex_relief_check(bridged)
        self.assertFalse(report["passed"])
        self.assertGreater(max(row["gap_obstruction_mm3"] for row in report["gaps"]), 8)

    def test_thick_head_supports_full_tip_and_broad_opposed_jaw(self):
        from gondola.parts import rail

        report = rail.clamp_contact_check()
        self.assertTrue(report["passed"], report)
        self.assertGreaterEqual(report["tip_lower_edge_margin_mm"], 0.5 - 1e-7)
        self.assertGreaterEqual(report["tip_upper_edge_margin_mm"], 0.5 - 1e-7)
        # One pitch of head land contacts the jaw, minus its unused Ø2.8 port.
        expected_jaw_area = (rail.LAND_PITCH - rail.FLEX_GAP) * (
            rail.HEAD_TOP - rail.HEAD_BOTTOM
        ) - math.pi * 1.4**2
        for row in report["contact_cases"]:
            if row["clamp_offset_from_land_centre_mm"] == 0:
                self.assertAlmostEqual(
                    row["opposing_jaw_contact_area_mm2"], expected_jaw_area
                )
            else:
                # Both entry chamfers can shorten contact at an off-centre
                # land. Bound the real area without counting either bevel.
                self.assertGreaterEqual(
                    row["opposing_jaw_contact_area_mm2"],
                    expected_jaw_area
                    - 2 * rail.HEAD_ENTRY_CHAMFER * (rail.HEAD_TOP - rail.HEAD_BOTTOM),
                )

    def test_head_is_the_close_datum_while_web_stays_relieved(self):
        from gondola.parts import rail

        report = rail.head_fit_check()
        self.assertTrue(report["passed"], report)
        fit = report["fit_contract"]
        self.assertEqual(fit["nominal_head_total_width_gap_mm"], 0.2)
        self.assertEqual(fit["nominal_head_total_height_gap_mm"], 0.2)
        self.assertEqual(fit["nominal_web_total_width_gap_mm"], 0.9)
        self.assertEqual(rail.CLAMP_SHIFT_Y, rail.HEAD_SIDE_CLEARANCE)
        self.assertEqual(fit["size_only_raw_width_gap_range_mm"], [-0.4, 0.8])
        self.assertEqual(fit["size_only_raw_height_gap_range_mm"], [-0.4, 0.8])
        self.assertFalse(fit["as_printed_fit_guaranteed"])
        self.assertFalse(fit["physical_fit_verified"])
        self.assertFalse(fit["holding_force_verified"])

    def test_previous_loose_head_channel_is_rejected(self):
        from gondola.parts import rail

        with (
            patch.object(rail, "HEAD_SIDE_CLEARANCE", 0.45),
            patch.object(rail, "HEAD_VERTICAL_CLEARANCE", 0.45),
        ):
            loose_shoe = rail.shoe_shape()
        report = rail.head_fit_check(shoe=loose_shoe)
        self.assertFalse(report["passed"], report)
        self.assertTrue(
            all(
                row["beyond_boundary_intersection_mm3"] < 1e-6
                for row in report["boundary_probes"]
            )
        )

    def test_under_sized_channel_cannot_pass_nominal_clearance_check(self):
        from gondola.parts import rail

        with (
            patch.object(rail, "HEAD_SIDE_CLEARANCE", 0.05),
            patch.object(rail, "HEAD_VERTICAL_CLEARANCE", 0.05),
        ):
            tight_shoe = rail.shoe_shape()
        report = rail.head_fit_check(shoe=tight_shoe)
        self.assertFalse(report["passed"], report)
        self.assertTrue(
            all(
                row["boundary_intersection_mm3"] > 1e-5
                for row in report["boundary_probes"]
            )
        )

    def test_entry_bevel_preserves_solid_wall_and_exterior_envelope(self):
        from gondola.parts import rail

        shoe = rail.shoe_shape()
        self.assertEqual(len(shoe.Solids), 1)
        self.assertTrue(shoe.isValid())
        self.assertAlmostEqual(shoe.BoundBox.XLength, rail.SHOE_LENGTH)
        self.assertAlmostEqual(shoe.BoundBox.YLength, rail.SHOE_WIDTH)
        self.assertAlmostEqual(shoe.BoundBox.ZMin, rail.SHOE_BOTTOM)
        self.assertAlmostEqual(shoe.BoundBox.ZMax, rail.TOP_Z)
        cavity_side = rail.HEAD_WIDTH / 2 + rail.HEAD_SIDE_CLEARANCE
        self.assertGreaterEqual(
            rail.NUT_POCKET_Y - cavity_side - rail.HEAD_ENTRY_CHAMFER, 1.5
        )
        for side in (-1, 1):
            # The lead-in is clear at the mouth but its extension must not
            # remove the straight running face farther inside the shoe.
            mouth = App.Vector(
                side * (rail.SHOE_LENGTH / 2 - 0.05), cavity_side + 0.1, rail.CLAMP_Z
            )
            datum = App.Vector(
                side * (rail.SHOE_LENGTH / 2 - rail.HEAD_ENTRY_CHAMFER - 0.05),
                cavity_side + 0.1,
                rail.CLAMP_Z,
            )
            self.assertFalse(shoe.isInside(mouth, 1e-7, True))
            self.assertTrue(shoe.isInside(datum, 1e-7, True))

    def test_former_thin_head_is_not_accepted_as_full_face_contact(self):
        from gondola.parts import rail

        with patch.object(rail, "HEAD_TOP", 7.0), patch.object(rail, "CLAMP_Z", 6.2):
            report = rail.clamp_contact_check()
        self.assertFalse(report["passed"])
        self.assertTrue(
            all(
                row["supported_nominal_tip_area_mm2"]
                < report["nominal_screw_tip_face_area_mm2"] - 0.1
                for row in report["contact_cases"]
            )
        )

    def test_capture_without_opposed_clamp_jaw_is_rejected(self):
        import Part

        from gondola.parts import rail

        missing_jaw = rail.shoe_shape().cut(
            Part.makeBox(
                20,
                6.0,
                rail.HEAD_TOP - rail.HEAD_BOTTOM + 0.02,
                App.Vector(-10, -11, rail.HEAD_BOTTOM - 0.01),
            )
        )
        report = rail.clamp_contact_check(shoe=missing_jaw)
        self.assertFalse(report["passed"])
        self.assertTrue(
            all(
                row["opposing_jaw_contact_area_mm2"] < 1e-6
                for row in report["contact_cases"]
            )
        )

    def test_hidden_head_slot_breaking_the_force_path_is_rejected(self):
        import Part

        from gondola.parts import rail

        hollow_head = rail.rail_shape(48, (0,)).cut(
            Part.makeBox(14, 0.5, 1, App.Vector(-7, -0.25, rail.CLAMP_Z - 0.5))
        )
        report = rail.clamp_contact_check(rail_section=hollow_head)
        self.assertFalse(report["passed"])
        self.assertTrue(
            all(
                row["missing_solid_transverse_load_strip_mm3"] > 0.1
                for row in report["contact_cases"]
            )
        )


if __name__ == "__main__":
    unittest.main()
