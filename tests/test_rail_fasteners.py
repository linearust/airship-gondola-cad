"""Direct vertical clamp hardware, open nut loading and finite top-tool service."""

import unittest

try:
    import FreeCAD as App
except ImportError:
    App = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class RailFastenerTests(unittest.TestCase):
    def test_two_plate_thicknesses_use_same_nut_and_thread_tip_datums(self):
        from gondola.parts import rail

        for thickness, length, offset in ((1, 6, 0), (3, 8, 4.8)):
            rows = rail.clamp_rows(plate_thickness_mm=thickness, parent_z_mm=offset)
            self.assertEqual(len(rows), 4)
            for row in rows:
                bounds = row["shape"].BoundBox
                with self.subTest(thickness=thickness, part=row["suffix"]):
                    if row["kind"] == "screw":
                        self.assertEqual(row["bolt_length_mm"], length)
                        self.assertAlmostEqual(bounds.ZMin + offset, 2)
                        self.assertEqual(row["sku"], f"M2X{length}_BUTTON_HEAD")
                    else:
                        self.assertAlmostEqual(bounds.ZMin + offset, 3.4)
                        self.assertAlmostEqual(bounds.ZMax + offset, 5)
                        self.assertEqual(row["sku"], "M2_HEX_NUT")
                    self.assertLess(
                        abs(
                            row["shape"]
                            .common(
                                rail.bay_shape().translated(App.Vector(0, 0, -offset))
                            )
                            .Volume
                        ),
                        1e-6,
                    )

    def test_open_bottom_nut_loading_preserves_antirotation_without_capture_claim(self):
        from gondola.parts import rail
        from gondola.validation.assembly import nut_guide_service_check

        for x in (-6, 0, 6):
            result = nut_guide_service_check(rail.bay_shape(), x)
            self.assertTrue(result["passed"], result)
            self.assertFalse(result["unbolted_nut_captured"])
            self.assertFalse(result["physical_fit_verified"])
            self.assertIn("before carbon/frame and tape", result["prerequisite"])

    def test_closed_floor_blocks_actual_nut_insertion(self):
        import Part

        from gondola.parts import rail
        from gondola.validation.assembly import nut_guide_service_check

        y = rail.TRACK_CENTRES_Y[0]
        floor = Part.makeBox(12, 4.15, 0.4, App.Vector(-6, y - 4.15 / 2, 0))
        result = nut_guide_service_check(rail.bay_shape().fuse(floor))
        self.assertFalse(result["passed"], result)
        self.assertGreater(result["rows"][0]["path_overlap_mm3"], 2)

    def test_overwide_guide_cannot_stop_the_smallest_accepted_nut(self):
        from gondola.parts import rail
        from gondola.validation.assembly import nut_guide_service_check

        result = nut_guide_service_check(rail.bay_shape(guide_width=4.9))
        self.assertFalse(result["passed"], result)
        self.assertTrue(
            all(
                case["blocking_mm3"] < 1e-6
                for row in result["rows"]
                for case in row["rotation_cases"]
            )
        )

    def test_top_tool_follows_rigid_parent_pose_and_checks_whole_screw(self):
        from gondola.parts import rail
        from gondola.validation.rail_access import top_key_service_check

        for rotation in (App.Rotation(), App.Rotation(App.Vector(1, 2, 3), 39)):
            pose = App.Placement(App.Vector(8, -17, 4), rotation)
            screw = rail.clamp_rows()[0]["shape"].copy()
            screw.Placement = pose.multiply(screw.Placement)
            result = top_key_service_check(
                {"operated": screw}, screw=screw, screw_name="operated", placement=pose
            )
            self.assertTrue(result["passed"], result)
            self.assertEqual(result["socket_insertion_acceptance_mm"], [0.0, 2.0])
            self.assertGreaterEqual(result["complete_screw_removal"]["travel_mm"], 8)
            self.assertEqual(result["continuous_working_sector"]["sector_deg"], [0, 60])
            self.assertIn(
                "operated", result["continuous_working_sector"]["checked_objects"]
            )

    def test_full_socket_insertion_may_touch_carbon_plane_but_never_enter_it(self):
        import Part

        from gondola.parts import rail
        from gondola.validation.rail_access import top_key_service_check

        row = rail.clamp_rows()[0]
        screw = row["shape"]
        x, y = row["centre_xy_mm"]
        plate = Part.makeBox(8, 8, 1, App.Vector(x - 4, y - 4, 7)).cut(
            Part.makeCylinder(1, 1, App.Vector(x, y, 7))
        )
        result = top_key_service_check(
            {"operated": screw, "carbon": plate}, screw=screw, screw_name="operated"
        )
        self.assertTrue(result["passed"], result)
        axial = result["continuous_working_sector"]["axial_leg_translation"]
        self.assertIn("carbon", axial["obstacles"])
        self.assertIn("carbon", axial["outward_supporting_plane_obstacles"])
        # Material above the supporting plane cannot use the contact exemption.
        lip = Part.makeBox(0.4, 0.4, 0.1, App.Vector(x - 0.2, y - 0.2, 8))
        blocked = top_key_service_check(
            {"operated": screw, "carbon": plate.fuse(lip)},
            screw=screw,
            screw_name="operated",
        )
        self.assertFalse(blocked["passed"])
        self.assertNotIn(
            "carbon",
            blocked["continuous_working_sector"]["axial_leg_translation"][
                "outward_supporting_plane_obstacles"
            ],
        )

    def test_screw_withdrawal_cannot_ignore_a_block_above_head(self):
        import Part

        from gondola.parts import rail
        from gondola.validation.rail_access import top_key_service_check

        row = rail.clamp_rows()[0]
        screw = row["shape"]
        x, y = row["centre_xy_mm"]
        block = Part.makeBox(
            1, 1, 1, App.Vector(x - 0.5, y - 0.5, screw.BoundBox.ZMax + 3)
        )
        result = top_key_service_check(
            {"operated": screw, "block": block}, screw=screw, screw_name="operated"
        )
        self.assertFalse(result["passed"])
        self.assertFalse(result["complete_screw_removal"]["passed"])

    def test_partial_screw_release_is_not_accepted_as_complete_removal(self):
        from gondola.parts import rail
        from gondola.validation.rail_access import top_key_service_check

        screw = rail.clamp_rows()[0]["shape"]
        with self.assertRaises(ValueError):
            top_key_service_check(
                {"operated": screw},
                screw=screw,
                screw_name="operated",
                release_travel_mm=1,
            )
        with self.assertRaises(ValueError):
            top_key_service_check({}, screw=screw, screw_name="operated")

    def test_continuous_key_sector_rejects_obstacle_between_clear_endpoints(self):
        import math

        import Part

        from gondola.validation.rail_access import (
            KEY_AXIAL_CENTRELINE_MM,
            key_envelope,
            working_sector_check,
        )

        head = 10
        tool = key_envelope(head)
        radius = 30
        block = Part.makeBox(
            1,
            1,
            1,
            App.Vector(
                -radius * math.cos(math.radians(30)) - 0.5,
                head + 0.1 + KEY_AXIAL_CENTRELINE_MM - 0.5,
                radius * math.sin(math.radians(30)) - 0.5,
            ),
        )
        for angle in (0, 60):
            endpoint = tool.copy()
            endpoint.rotate(App.Vector(), App.Vector(0, 1, 0), angle)
            self.assertLess(abs(endpoint.common(block).Volume), 1e-6)
        result = working_sector_check(tool, {"mid_arc": block}, App.Vector())
        self.assertFalse(result["passed"], result)
        self.assertEqual(result["collisions"][0]["part"], "mid_arc")

    def test_unresolved_tool_interval_fails_closed(self):
        import Part

        from gondola.validation.rail_access import key_envelope, working_sector_check

        result = working_sector_check(
            key_envelope(10),
            {"near_but_clear": Part.makeBox(1, 1, 1, App.Vector(-10, 26.2, 0))},
            App.Vector(),
            max_depth=0,
        )
        self.assertFalse(result["passed"])
        self.assertIn("could not resolve", result["error"])


if __name__ == "__main__":
    unittest.main()
