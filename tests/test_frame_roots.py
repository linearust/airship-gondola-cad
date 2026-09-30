"""Native regressions for solid bearing roots and the side M2 rail foot."""

import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class FrameRootTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.parts import propulsion

        cls.doc = App.newDocument("SolidBearingRoots")
        cls.module = propulsion.build_propulsion_module(cls.doc)

    @classmethod
    def tearDownClass(cls):
        App.closeDocument(cls.doc.Name)

    def test_all_four_roots_have_a_complete_load_path(self):
        from gondola.validation.propulsion import bearing_post_roots_check

        rows = bearing_post_roots_check(self.doc)
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(row["passed"] for row in rows), rows)

    def test_reopened_low_corridor_fails_saved_geometry_root_check(self):
        from gondola.parts import propulsion
        from gondola.validation.propulsion import bearing_post_roots_check

        frame = self.doc.PropulsionFixedFrame
        original = frame.Shape.copy()
        try:
            corridor = Part.makeBox(
                6.4,
                propulsion.BEARING_POST_DEPTH,
                4,
                App.Vector(
                    -3.2,
                    propulsion.PIVOT_HALF_SPAN + propulsion.BEARING_GUIDE_START_Y,
                    propulsion.BASE_Z + propulsion.FOOT_THICKNESS,
                ),
            )
            removed_volume = original.common(corridor).Volume
            self.assertGreater(removed_volume, 90)
            self.assertAlmostEqual(removed_volume, corridor.Volume, places=6)
            frame.Shape = original.cut(corridor)
            self.doc.recompute()
            self.assertTrue(frame.Shape.isValid())
            self.assertEqual(len(frame.Shape.Solids), 1)
            rows = bearing_post_roots_check(self.doc)
            failed = [row for row in rows if not row["passed"]]
            self.assertEqual(len(failed), 1, rows)
            self.assertEqual(failed[0]["side"], 1)
            self.assertGreater(failed[0]["post_local_y_mm"], 0)
            self.assertAlmostEqual(
                failed[0]["missing_root_material_mm3"], removed_volume, places=6
            )
        finally:
            frame.Shape = original
            self.doc.recompute()

    def test_long_output_feet_are_full_width_three_mm_plates(self):
        from gondola.parts import propulsion

        frame = self.doc.PropulsionFixedFrame.Shape
        outer_y = (
            propulsion.PIVOT_HALF_SPAN
            + propulsion.BEARING_SHOULDER_Y
            + propulsion.BEARING_SHOULDER_THICKNESS
            + 0.5
        )
        self.assertAlmostEqual(frame.BoundBox.YMin, -outer_y, places=6)
        self.assertAlmostEqual(frame.BoundBox.YMax, outer_y, places=6)
        for start_y in (20, -outer_y):
            with self.subTest(start_y=start_y):
                solid_foot = Part.makeBox(
                    18,
                    outer_y - 20,
                    3,
                    App.Vector(-9, start_y, propulsion.BASE_Z),
                )
                self.assertLess(solid_foot.cut(frame).Volume, 1e-7)

    def test_central_seat_is_complete_and_cannot_be_hollowed_for_side_access(self):
        from gondola.parts import rail, servo_bridge

        frame = self.doc.PropulsionFixedFrame.Shape
        bridge = self.doc.ServoDriveBridge.Shape
        support = Part.makeBox(
            18,
            22,
            servo_bridge.SEAT_Z - rail.WEB_TOP_Z,
            App.Vector(-9, -11, rail.WEB_TOP_Z),
        )
        contact = Part.makePlane(18, 22, App.Vector(-9, -11, servo_bridge.SEAT_Z))
        self.assertLess(support.cut(frame).Volume, 1e-7)
        self.assertAlmostEqual(contact.common(frame).Area, 396, places=5)
        self.assertAlmostEqual(contact.common(bridge).Area, 396, places=5)
        self.assertLess(frame.common(bridge).Volume, 1e-7)

    def test_standard_side_foot_has_broad_overlap_with_central_support(
        self,
    ):
        from gondola.parts import propulsion, rail

        frame = self.doc.PropulsionFixedFrame.Shape
        offset = propulsion.RAIL_BOLT_OFFSET_X
        length = propulsion.RAIL_CONTACT_LENGTH
        foot = rail.mount_base_shape(length=length)
        foot.translate(App.Vector(offset, 0, 0))
        self.assertLess(foot.cut(frame).Volume, 1e-7)
        self.assertAlmostEqual(offset - length / 2, 0.5)
        self.assertGreater(offset + length / 2, 0)
        self.assertAlmostEqual(length, 24)
        connection = Part.makeBox(8.5, 2.5, 9.2, App.Vector(0.5, -3.75, 2.2))
        self.assertLess(connection.cut(frame).Volume, 1e-7)

    def test_side_bore_fill_does_not_fill_the_web_passage_and_frame_lifts(self):
        from gondola.parts import propulsion, rail
        from gondola.validation.propulsion import (
            frame_rail_bore_filled,
            vertical_frame_release_check,
        )

        frame = self.doc.PropulsionFixedFrame.Shape
        filled = frame_rail_bore_filled(frame)
        rail_shape = rail.rail_shape()
        rail_shape.translate(App.Vector(propulsion.RAIL_BOLT_OFFSET_X, 0, 0))
        self.assertLess(frame.cut(filled).Volume, 1e-7)
        self.assertLess(filled.common(rail_shape).Volume, 1e-7)
        result = vertical_frame_release_check(frame, rail_shape)
        self.assertTrue(result["passed"], result)
        self.assertEqual(
            result["lower_frame_path"]["segments"][0]["method"],
            "continuous planar/coaxial-cylinder face-prism union",
        )

    def test_connector_plate_keeps_bulkhead_support_and_shared_clamp(self):
        from gondola.parts import servo_bridge
        from gondola.validation.servo_module import bridge_joint_check

        bridge = self.doc.ServoDriveBridge.Shape
        centre = Part.makeBox(
            26.8,
            5,
            2,
            App.Vector(-13.4, -2.5, servo_bridge.CONNECTOR_PLATE_BOTTOM_Z),
        )
        self.assertLess(centre.cut(bridge).Volume, 1e-7)
        self.assertEqual(len(bridge.Solids), 1)
        result = bridge_joint_check(self.doc, self.module)
        self.assertTrue(result["passed"], result)


if __name__ == "__main__":
    unittest.main()
