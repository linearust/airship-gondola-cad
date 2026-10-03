"""Literal stock and void witnesses for protected PA12 edge blends."""

import math
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
            propulsion,
        )

        cls.motor = propulsion.moving_carrier_shape()
        cls.frame = propulsion.fixed_frame_shape()
        cls.cap = bearing_retention.cap_shape()
        cls.equipment = equipment_mounts.mount_shape("battery")

    def solid(self, shape, point):
        self.assertTrue(shape.isInside(App.Vector(*point), 1e-7, False), point)

    def empty(self, shape, point):
        self.assertFalse(shape.isInside(App.Vector(*point), 1e-7, False), point)

    def test_motor_root_has_rounded_edges_and_retains_motor_clearance(self):
        # The exterior 0.5 mm rounds remove only the two long root edges.
        for z in (-1, 1):
            self.empty(self.motor, (-7.99, -20, z * 3.99))
            self.solid(self.motor, (-7.4, -20, z * 3.4))
        ring = Part.makeBox(3, 0.2, 2.8, App.Vector(8, -0.1, 23.1))
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

    def test_integrated_frame_roots_retain_full_post_cores(self):
        for y in (-34.5, 34.5):
            core = Part.makeBox(18, 19, 12.5, App.Vector(-9, y - 9.5, 29.5))
            self.assertLess(core.cut(self.frame).Volume, 1e-6)
        for sign in (-1, 1):
            self.solid(self.frame, (0, sign * 24.9, 29.6))
            self.empty(self.frame, (0, sign * 23.51, 30.99))
            self.solid(self.frame, (sign * 8.99, 20, 24.51))

    def test_input_wing_roots_add_literal_quarter_circle_stock_below_the_bed(self):
        root = Part.makeBox(1.5, 8, 1.5, App.Vector(9, 29, 40.5)).cut(
            Part.makeCylinder(1.5, 8, App.Vector(10.5, 29, 40.5), App.Vector(0, 1, 0))
        )
        self.assertAlmostEqual(root.Volume, 8 * 1.5**2 * (1 - math.pi / 4))
        for sign in (-1, 1):
            witness = root.copy()
            if sign < 0:
                witness.rotate(App.Vector(), App.Vector(0, 0, 1), 180)
            self.assertLess(abs(witness.cut(self.frame).Volume), 1e-6)
            self.solid(self.frame, (sign * 9.1, sign * 33, 41.9))
            self.empty(self.frame, (sign * 10.4, sign * 33, 40.6))

    def test_cap_upper_rounds_preserve_three_head_annuli_and_split_lands(self):
        self.empty(self.cap, (26.49, 5, 4.49))
        self.solid(self.cap, (26.15, 5, 4.15))
        for x, y in ((-5.5, 6.5), (6.25, 11.5), (23, 5)):
            annulus = Part.makeCylinder(2.25, 0.01, App.Vector(x, y, 4.49)).cut(
                Part.makeCylinder(1.1, 0.03, App.Vector(x, y, 4.48))
            )
            self.assertLess(abs(annulus.cut(self.cap).Volume), 1e-6)
        # Free side lands on the split plane remain rectangular, including
        # the new input-bearing wing; no edge rounding reaches the mating face.
        for x, y, dx, dy in ((-8.8, 4, 2, 1), (3.5, 9, 2, 1), (20, 2, 2, 1)):
            land = Part.makeBox(dx, dy, 0.01, App.Vector(x, y, 0))
            self.assertLess(abs(land.cut(self.cap).Volume), 1e-6)
        from gondola.validation.manufacturing import planar_wall_regions

        for shape in (self.cap, self.frame):
            walls = planar_wall_regions(shape)
            self.assertTrue(walls)
            self.assertGreaterEqual(
                min(row["material_thickness_mm"] for row in walls), 1.5 - 1e-5
            )

    def test_optical_roots_and_lower_round_keep_seating_datums(self):
        from gondola.parts import optical_mount

        base = optical_mount.base_shape()
        tray = optical_mount.sensor_tray_shape()
        self.solid(base, (0, -2.1, 2.1))
        self.empty(base, (0, -2.49, 2.49))
        # The buttress toe is obtuse, so its quarter-circle stock differs
        # from the right-angle front root.
        self.solid(base, (0, 2.05, 2.05))
        foot_floor = Part.makeBox(1, 1, 1.5, App.Vector(2.8, 7.5, 0))
        self.assertLess(foot_floor.cut(base).Volume, 1e-6)
        # Independent R1 plan outline: overlapping rectangles and four full
        # circles, without the production fillet selector. Above the R0.5
        # underside round, the entire pad retains 1.5 mm of flat seating stock.
        pad = Part.makeBox(16, 12, 1.5, App.Vector(-8, -6, 9)).fuse(
            Part.makeBox(18, 10, 1.5, App.Vector(-9, -5, 9))
        )
        for x in (-8, 8):
            for y in (-5, 5):
                pad = pad.fuse(Part.makeCylinder(1, 1.5, App.Vector(x, y, 9)))
        self.assertAlmostEqual(pad.Volume, (18 * 12 - (4 - math.pi)) * 1.5)
        self.assertLess(pad.cut(tray).Volume, 1e-6)
        top_band = Part.makeBox(20, 14, 1.5, App.Vector(-10, -7, 9))
        self.assertLess(tray.common(top_band).cut(pad).Volume, 1e-6)
        above_seat = Part.makeBox(20, 14, 1, App.Vector(-10, -7, 10.5))
        self.assertLess(tray.common(above_seat).Volume, 1e-6)
        # A literal oversized R2 corner loses required R1 seating stock.
        wrong_corner = Part.makeBox(2, 2, 1.5, App.Vector(7, 4, 9)).cut(
            Part.makeCylinder(2, 1.5, App.Vector(7, 4, 9))
        )
        damaged = tray.cut(wrong_corner)
        self.assertGreater(pad.cut(damaged).Volume, 0.1)
        self.empty(tray, (8.99, 0, 8.51))
        self.solid(tray, (8.4, 0, 8.6))


if __name__ == "__main__":
    unittest.main()
