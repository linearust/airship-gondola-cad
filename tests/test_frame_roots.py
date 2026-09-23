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
                    App.Vector(-3.2, propulsion.PIVOT_HALF_SPAN + 26.5, 4),
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
                # The circular 4.5 mm conservative head envelope clears the
                # 1.5 mm roof corner by 0.495 mm nominally, before print errors.
                self.assertGreaterEqual(side_head.distToShape(frame)[0], 0.45 - 1e-7)
                self.assertGreaterEqual(side_head.distToShape(bridge)[0], 0.45 - 1e-7)

    def test_open_tool_recess_keeps_ring_and_broad_cradle_seats(self):
        from gondola.parts import rail, servo_bridge
        from gondola.validation.servo_module import bridge_joint_check

        bridge = self.doc.ServoDriveBridge.Shape
        bar = Part.makeBox(
            6.4,
            2,
            2,
            App.Vector(-3.2, 21, servo_bridge.RING_BOTTOM_Z),
        )
        for shape in (bar, rail.half_turn(bar)):
            self.assertLess(shape.cut(bridge).Volume, 1e-7)
        self.assertEqual(len(bridge.Solids), 1)
        result = bridge_joint_check(self.doc, self.module)
        self.assertTrue(result["passed"], result)


if __name__ == "__main__":
    unittest.main()
