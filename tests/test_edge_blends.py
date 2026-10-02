"""Literal stock and void witnesses for protected PA12 edge blends."""

import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires FreeCAD")
class EdgeBlendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.parts import (
            bearing_retention,
            equipment_mounts,
            optical_mount,
            propulsion,
            servo_bridge,
        )

        cls.motor = propulsion.moving_carrier_shape()
        cls.frame = propulsion.fixed_frame_shape()
        cls.bridge = servo_bridge.bridge_shape()
        cls.equipment = equipment_mounts.mount_shape("battery")
        cls.base = optical_mount.base_shape()
        cls.tray = optical_mount.sensor_tray_shape()
        cls.keeper = bearing_retention.keeper_shape()

    def solid(self, shape, point):
        self.assertTrue(shape.isInside(App.Vector(*point), 1e-7, False), point)

    def empty(self, shape, point):
        self.assertFalse(shape.isInside(App.Vector(*point), 1e-7, False), point)

    def test_motor_roots_add_stock_but_exposed_rounds_remove_only_corners(self):
        for sign in (-1, 1):
            self.solid(self.motor, (-4.9, sign * 21.15, 0))
            self.empty(self.motor, (-4.5, sign * 20.75, 0))
            self.empty(self.motor, (-7.99, sign * 12, 3.99))
            self.solid(self.motor, (-7.4, sign * 12, 3.4))
            self.empty(self.motor, (10.99, sign * 25, 3.99))
            self.solid(self.motor, (10.4, sign * 25, 3.4))
        # The ring retains its full 2x2 section; the motor datum is unchanged.
        ring = Part.makeBox(2, 0.2, 1.8, App.Vector(8, -0.1, 23.1))
        self.assertLess(ring.cut(self.motor).Volume, 1e-6)
        motor = Part.makeCylinder(6.8, 8.9, App.Vector(-5, 0, 0), App.Vector(1, 0, 0))
        self.assertLess(motor.common(self.motor).Volume, 1e-6)

    def test_equipment_roots_preserve_support_cores_and_full_access_corridor(self):
        for x in (-8, 3):
            core = Part.makeBox(5, 5, 4.5, App.Vector(x, -2.5, 12.5))
            self.assertLess(core.cut(self.equipment).Volume, 1e-6)
        access = Part.makeBox(6, 16, 4.5, App.Vector(-3, -8, 12.5))
        self.assertLess(access.common(self.equipment).Volume, 1e-6)
        for sign in (-1, 1):
            self.solid(self.equipment, (sign * 8.1, 0, 16.9))
            self.solid(self.equipment, (sign * 5, 2.6, 12.6))
            self.empty(self.equipment, (sign * 32.99, 0, 18.99))
            edge_band = Part.makeBox(
                0.2, 1, 1.5, App.Vector(sign * 32.8 - 0.1, 9, 17.25)
            )
            self.assertLess(edge_band.cut(self.equipment).Volume, 1e-6)

    def test_bridge_outer_rounds_preserve_complete_mating_roof(self):
        roof = Part.makeBox(38, 22, 0.1, App.Vector(-19, -11, 12.5))
        self.assertLess(roof.cut(self.bridge).Volume, 1e-6)
        for sign in (-1, 1):
            self.empty(self.bridge, (sign * 18.99, 0, 14.99))
            self.empty(self.bridge, (sign * 14.39, 2.49, 30))
            self.solid(self.bridge, (sign * 13.8, 1.9, 30))

    def test_frame_end_roots_retain_full_post_cores(self):
        for y in (-112.75, -43.25, 37.25, 106.75):
            core = Part.makeBox(13, 6, 14, App.Vector(-6.5, y, 12.5))
            self.assertLess(core.cut(self.frame).Volume, 1e-6)
        for sign in (-1, 1):
            self.solid(self.frame, (0, sign * 37.15, 12.6))
            self.empty(self.frame, (0, sign * 113.1, 12.9))

    def test_optical_roots_and_lower_round_keep_seating_datums(self):
        self.solid(self.base, (0, -2.1, 2.1))
        # The buttress toe is obtuse, so its quarter-circle stock differs
        # from the right-angle front root.
        self.solid(self.base, (0, 2.05, 2.05))
        foot_floor = Part.makeBox(1, 1, 1.5, App.Vector(2.8, 7.5, 0))
        self.assertLess(foot_floor.cut(self.base).Volume, 1e-6)
        pad = Part.makeBox(18, 12, 1.5, App.Vector(-9, -6, 5))
        self.assertLess(pad.cut(self.tray).Volume, 1e-6)
        self.empty(self.tray, (8.99, 0, 4.51))
        self.solid(self.tray, (8.4, 0, 4.6))

    def test_keeper_rounds_preserve_axial_thickness_and_seating_checks(self):
        from gondola.parts import bearing_retention

        self.assertTrue(bearing_retention.geometry_check(keeper=self.keeper)["passed"])
        self.empty(self.keeper, (4.49, -1, 4.49))
        plate = Part.makeBox(1, 1.5, 1, App.Vector(3, -2, 0))
        self.assertLess(plate.cut(self.keeper).Volume, 1e-6)


if __name__ == "__main__":
    unittest.main()
