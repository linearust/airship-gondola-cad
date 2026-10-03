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

    def test_shared_cap_and_frame_keep_both_concave_t_wing_root_blends(self):
        # Independent R0.75 added stock on both plan-view reentrant corners;
        # the narrow band does not reach the shaft-jaw corridor atX14.5+.
        root = Part.makeBox(0.75, 0.75, 1, App.Vector(9, 0.25, 2)).cut(
            Part.makeCylinder(0.75, 1, App.Vector(9.75, 0.25, 2))
        )
        roots = [root, root.mirror(App.Vector(0, 5, 0), App.Vector(0, 1, 0))]
        for witness in roots:
            self.assertAlmostEqual(witness.Volume, 0.75**2 * (1 - math.pi / 4))
            self.assertLess(witness.cut(self.cap).Volume, 1e-6)
            witness.translate(App.Vector(0, 28, 44))
            self.assertLess(witness.cut(self.frame).Volume, 1e-6)
        jaw = Part.makeBox(15, 3.8, 6, App.Vector(14.5, 37.7, 47))
        self.assertLess(jaw.common(self.frame).Volume, 1e-6)

    def test_cap_upper_rounds_preserve_two_head_annuli_and_split_lands(self):
        self.empty(self.cap, (26.49, 5, 4.49))
        self.solid(self.cap, (26.15, 5, 4.15))
        for x, y in ((-5.5, 5), (23, 5)):
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

    def test_integral_optical_post_roots_have_small_protected_blends(self):
        from gondola.parts import instrument_mount

        carrier = instrument_mount.upper_shape()
        # Literal quarter-circle stock along each of eight root edges; corner
        # transitions are excluded so the witness does not assume a kernel patch.
        root = Part.makeBox(0.25, 2, 0.25, App.Vector(27.25, 28.5, 19)).cut(
            Part.makeCylinder(
                0.25, 2, App.Vector(27.25, 28.5, 19.25), App.Vector(0, 1, 0)
            )
        )
        self.assertAlmostEqual(root.Volume, 2 * 0.25**2 * (1 - math.pi / 4))
        for angle in (0, 90, 180, 270):
            positive = root.copy()
            positive.rotate(App.Vector(29.5, 29.5, 0), App.Vector(0, 0, 1), angle)
            negative = positive.copy()
            negative.rotate(App.Vector(), App.Vector(0, 0, 1), 180)
            for witness in (positive, negative):
                self.assertLess(witness.cut(carrier).Volume, 1e-6)
        pad = Part.makeBox(18, 12, 2, App.Vector(-9, -6, 42))
        self.assertLess(pad.cut(carrier).Volume, 1e-6)
        above_pad = Part.makeBox(18, 12, 1, App.Vector(-9, -6, 44))
        self.assertLess(above_pad.common(carrier).Volume, 1e-6)

    def test_servo_cradle_roots_add_stock_without_reducing_case_window(self):
        # Independent square-minus-circle witness, shortened before each end.
        root = Part.makeBox(12, 0.75, 0.75, App.Vector(10, -5.5, 29.5)).cut(
            Part.makeCylinder(
                0.75, 12, App.Vector(10, -4.75, 30.25), App.Vector(1, 0, 0)
            )
        )
        self.assertAlmostEqual(root.Volume, 12 * 0.75**2 * (1 - math.pi / 4))
        for angle in (0, 180):
            witness = root.copy()
            witness.rotate(App.Vector(), App.Vector(0, 0, 1), angle)
            self.assertLess(witness.cut(self.frame).Volume, 1e-6)
            for void in (
                Part.makeBox(7.4, 5, 20.4, App.Vector(12.3, -10.5, 34.8)),
                Part.makeCylinder(
                    1.75, 14, App.Vector(16, -5.5, 33), App.Vector(0, 1, 0)
                ),
            ):
                void.rotate(App.Vector(), App.Vector(0, 0, 1), angle)
                self.assertLess(void.common(self.frame).Volume, 1e-6)

    def test_instrument_yoke_roots_leave_the_standard_shoe_unchanged(self):
        from gondola.parts import instrument_mount, rail

        base = instrument_mount.base_shape()
        root = Part.makeBox(17, 1, 1, App.Vector(-4, 3.1, 15.5)).cut(
            Part.makeCylinder(1, 17, App.Vector(-4, 3.1, 16.5), App.Vector(1, 0, 0))
        )
        self.assertAlmostEqual(root.Volume, 17 * (1 - math.pi / 4))
        for witness in (root, root.mirror(App.Vector(), App.Vector(0, 1, 0))):
            self.assertLess(witness.cut(base).Volume, 1e-6)
        crop = Part.makeBox(50, 50, 32.5, App.Vector(-25, -25, -20))
        shoe = rail.mount_base_shape().common(crop)
        retained = base.common(crop)
        self.assertLess(shoe.cut(retained).Volume, 1e-6)
        self.assertLess(retained.cut(shoe).Volume, 1e-6)

    def test_instrument_deck_roots_preserve_centre_access_and_spare_relief(self):
        from gondola.parts import instrument_mount

        upper = instrument_mount.upper_shape()
        root = Part.makeBox(4, 0.5, 0.5, App.Vector(3.5, 4, 16.5)).cut(
            Part.makeCylinder(0.5, 4, App.Vector(3.5, 4.5, 16.5), App.Vector(1, 0, 0))
        )
        self.assertAlmostEqual(root.Volume, 4 * 0.5**2 * (1 - math.pi / 4))
        for sx in (-1, 1):
            for sy in (-1, 1):
                witness = root.copy()
                if sx < 0:
                    witness = witness.mirror(App.Vector(), App.Vector(1, 0, 0))
                if sy < 0:
                    witness = witness.mirror(App.Vector(), App.Vector(0, 1, 0))
                self.assertLess(witness.cut(upper).Volume, 1e-6)
        for origin, size in (
            ((-3, -4, 16), (6, 8, 1)),
            ((8.8, -4.1, 14.6), (7.2, 8.2, 2.4)),
        ):
            void = Part.makeBox(*size, App.Vector(*origin))
            self.assertLess(void.common(upper).Volume, 1e-6)


if __name__ == "__main__":
    unittest.main()
