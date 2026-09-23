"""Installed fastener regressions for the plain paired-servo connector plate."""

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

        cls.doc = App.newDocument("PlainServoConnectorPlate")
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
