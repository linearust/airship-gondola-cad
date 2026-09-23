"""Open connector plate, broad load paths and installed fastener regressions."""

import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class ServoBridgeShapeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.parts import propulsion

        cls.doc = App.newDocument("OpenServoConnectorPlate")
        cls.module = propulsion.build_propulsion_module(cls.doc)

    @classmethod
    def tearDownClass(cls):
        App.closeDocument(cls.doc.Name)

    def check_mount(self, prefix, bridge=None):
        from gondola.cad import world_shape
        from gondola.validation.propulsion import clamp_fastener_check

        if bridge is None:
            bridge = world_shape(self.doc.ServoDriveBridge)
        clamp = Part.makeCompound([world_shape(self.doc.PropulsionFixedFrame), bridge])
        return clamp_fastener_check(
            clamp,
            world_shape(self.doc.getObject("ServoBridge" + prefix + "Bolt")),
            world_shape(self.doc.getObject("ServoBridge" + prefix + "Nut")),
        )

    def test_both_counterbores_retain_existing_m2x8_clamping_stack(self):
        for prefix in ("Port", "Starboard"):
            with self.subTest(side=prefix):
                bolt = self.doc.getObject("ServoBridge" + prefix + "Bolt")
                self.assertEqual(bolt.HardwareSKU, "M2X8_BUTTON_HEAD")
                result = self.check_mount(prefix)
                self.assertTrue(result["passed"], result)

    def test_unused_side_regions_are_open_to_the_plate_edges(self):
        from gondola.parts import servo_bridge

        bridge = self.doc.ServoDriveBridge.Shape
        # Two large open-edge regions on each side expose the underlying
        # frame without retaining a thin outer ring around a viewing hole.
        openings = (
            Part.makeBox(17.3, 15, 2, App.Vector(-13.4, 11, 11.4)),
            Part.makeBox(6.1, 34, 2, App.Vector(-19.5, -8, 11.4)),
        )
        for opening in openings:
            for side in (opening, servo_bridge.opposite(opening)):
                self.assertLess(bridge.common(side).Volume, 1e-7)
        self.assertTrue(bridge.isValid())
        self.assertEqual(len(bridge.Solids), 1)

    def test_each_mounting_arm_has_a_broad_continuous_connection(self):
        from gondola.parts import servo_bridge

        bridge = self.doc.ServoDriveBridge.Shape
        # The full 9.5 mm attachment breadth continues from the central stock
        # into each foot; the necessary bolt counterbores are farther outward.
        link = Part.makeBox(9.5, 6, 2, App.Vector(3.9, 8, 11.4))
        for side in (link, servo_bridge.opposite(link)):
            self.assertLess(side.cut(bridge).Volume, 1e-7)

    def test_blocked_head_counterbore_cannot_pass_the_installed_stack_check(self):
        from gondola.cad import world_shape
        from gondola.parts import servo_bridge

        bridge = world_shape(self.doc.ServoDriveBridge)
        origin = App.Vector(
            servo_bridge.BOLT_X,
            servo_bridge.BOLT_Y,
            servo_bridge.MOUNT_BOLT_SEAT_Z,
        )
        fill = Part.makeCylinder(3, 2.7, origin).cut(
            Part.makeCylinder(1.1, 2.7, origin)
        )
        result = self.check_mount("Port", bridge.fuse(fill))
        self.assertFalse(result["passed"], result)
        self.assertGreater(result["fastener_clamp_overlap_mm3"], 1)


if __name__ == "__main__":
    unittest.main()
