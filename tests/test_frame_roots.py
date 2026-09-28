"""Native regressions for solid bearing roots and bounded rail-key access."""

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
            frame.Shape = frame.Shape.cut(
                Part.makeBox(
                    6.4,
                    4,
                    4,
                    App.Vector(
                        -3.2,
                        propulsion.PIVOT_HALF_SPAN + 26.5,
                        propulsion.BASE_Z + propulsion.FOOT_THICKNESS,
                    ),
                )
            )
            self.doc.recompute()
            rows = bearing_post_roots_check(self.doc)
            self.assertEqual(sum(not row["passed"] for row in rows), 1, rows)
            self.assertGreater(
                max(row["missing_root_material_mm3"] for row in rows), 90
            )
        finally:
            frame.Shape = original
            self.doc.recompute()

    def test_long_output_feet_are_full_width_three_mm_plates(self):
        from gondola.parts import propulsion

        frame = self.doc.PropulsionFixedFrame.Shape
        outer_y = propulsion.PIVOT_HALF_SPAN + 33
        for start_y in (20, -outer_y):
            with self.subTest(start_y=start_y):
                solid_foot = Part.makeBox(
                    18,
                    outer_y - 20,
                    3,
                    App.Vector(-9, start_y, propulsion.BASE_Z),
                )
                self.assertLess(solid_foot.cut(frame).Volume, 1e-7)

    def test_central_web_reaches_only_the_actual_common_servo_wall(self):
        from gondola.parts import propulsion, servo_bridge

        frame = self.doc.PropulsionFixedFrame.Shape
        bridge = self.doc.ServoDriveBridge.Shape
        bottom = propulsion.BASE_Z + propulsion.RAIL_FOOT_THICKNESS
        support = Part.makeBox(
            26.8,
            5,
            servo_bridge.CONNECTOR_PLATE_BOTTOM_Z - bottom,
            App.Vector(-13.4, -2.5, bottom),
        )
        contact = Part.makePlane(
            26.8, 5, App.Vector(-13.4, -2.5, servo_bridge.CONNECTOR_PLATE_BOTTOM_Z)
        )
        self.assertLess(support.cut(frame).Volume, 1e-7)
        self.assertAlmostEqual(contact.common(frame).Area, 134, places=5)
        self.assertAlmostEqual(contact.common(bridge).Area, 134, places=5)
        self.assertLess(frame.common(bridge).Volume, 1e-7)

    def test_vertical_clamps_clear_frame_and_bridge_without_a_shoe(self):
        from gondola.parts import propulsion, rail

        frame = self.doc.PropulsionFixedFrame.Shape
        bridge = self.doc.ServoDriveBridge.Shape
        rows = rail.clamp_rows(
            plate_thickness_mm=3, parent_z_mm=propulsion.MODULE_Z_OFFSET
        )
        for row in rows:
            with self.subTest(joint=row["suffix"]):
                self.assertLess(row["shape"].common(frame).Volume, 1e-7)
                self.assertLess(row["shape"].common(bridge).Volume, 1e-7)
                if row["kind"] == "screw":
                    self.assertEqual(row["sku"], "M2X8_BUTTON_HEAD")
                    self.assertAlmostEqual(row["bearing_z_mm"], propulsion.BASE_Z + 3)
        self.assertFalse(self.doc.PropulsionFixedFrame.IntegratedRailShoe)

    def test_module_raise_preserves_local_mechanism_and_seats_foot_at_rail_top(self):
        from gondola.cad import world_shape
        from gondola.parts import propulsion, rail
        from gondola.validation.servo_module import bridge_joint_check

        group = self.module["group"]
        original = App.Placement(group.Placement)
        relative = App.Placement(self.doc.ServoDriveBridge.Placement)
        try:
            group.Placement.Base.z = propulsion.MODULE_Z_OFFSET
            self.doc.recompute()
            self.assertAlmostEqual(
                world_shape(self.doc.PropulsionFixedFrame).BoundBox.ZMin, rail.TOP_Z
            )
            self.assertTrue(self.doc.ServoDriveBridge.Placement.isSame(relative, 1e-7))
            self.assertTrue(bridge_joint_check(self.doc, self.module)["passed"])
            self.assertLess(
                world_shape(self.doc.PropulsionFixedFrame)
                .common(rail.rail_shape())
                .Volume,
                1e-7,
            )
        finally:
            group.Placement = original
            self.doc.recompute()

    def test_open_connector_plate_keeps_bulkhead_support_and_mounting_seats(self):
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
