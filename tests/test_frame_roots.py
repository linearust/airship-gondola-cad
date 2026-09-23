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

    def test_central_shoe_roof_reaches_the_common_servo_wall_plate(self):
        from gondola.parts import rail, servo_bridge

        frame = self.doc.PropulsionFixedFrame.Shape
        bridge = self.doc.ServoDriveBridge.Shape
        support = Part.makeBox(
            18,
            22,
            servo_bridge.CONNECTOR_PLATE_BOTTOM_Z - rail.TOP_Z,
            App.Vector(-9, -11, rail.TOP_Z),
        )
        contact = Part.makePlane(
            18,
            22,
            App.Vector(-9, -11, servo_bridge.CONNECTOR_PLATE_BOTTOM_Z),
        )
        self.assertLess(support.cut(frame).Volume, 1e-7)
        self.assertAlmostEqual(contact.common(frame).Area, 396, places=5)
        self.assertAlmostEqual(contact.common(bridge).Area, 396, places=5)
        self.assertLess(frame.common(bridge).Volume, 1e-7)

    def test_raised_head_clears_bridge_and_intact_two_mm_foot_floor(self):
        from gondola.contracts import fasteners
        from gondola.parts import rail

        frame = self.doc.PropulsionFixedFrame.Shape
        bridge = self.doc.ServoDriveBridge.Shape
        head_start = rail.HEAD_WIDTH / 2 - rail.CLAMP_SHIFT_Y + rail.SCREW_LENGTH
        head = Part.makeCylinder(
            fasteners.SCREW_HEAD_DIAMETER / 2,
            fasteners.SCREW_HEAD_HEIGHT,
            App.Vector(0, head_start, rail.CLAMP_Z),
            App.Vector(0, 1, 0),
        )
        floor = Part.makeBox(6.4, 6, 2, App.Vector(-3.2, 11.1, rail.SHOE_BOTTOM))
        for sign in (1, -1):
            side_head = head if sign > 0 else rail.half_turn(head)
            side_floor = floor if sign > 0 else rail.half_turn(floor)
            with self.subTest(side=sign):
                self.assertLess(side_floor.cut(frame).Volume, 1e-7)
                # The circular 4.5 mm design head clears the continuous floor
                # by 0.45 mm and the plain seating feet by at least 1.6 mm.
                self.assertGreaterEqual(side_head.distToShape(frame)[0], 0.45 - 1e-7)
                self.assertGreaterEqual(side_head.distToShape(bridge)[0], 1.6 - 1e-7)

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
