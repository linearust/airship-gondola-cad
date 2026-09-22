"""Full-orbit bounds cover intermediate poses and retain the supplied datum."""

import math
import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires FreeCAD")
class RotationEnvelopeTests(unittest.TestCase):
    def test_offset_axis_and_placed_solid_remain_contained(self):
        from gondola.validation.rotation_envelope import full_orbit_envelope

        origin = App.Vector(8, 17, -9)
        body = Part.makeBox(2, 3, 4, App.Vector(11, -3, -10))
        body.rotate(App.Vector(11, -3, -10), App.Vector(1, 0, 0), 27)
        envelope, evidence = full_orbit_envelope(body, origin)
        self.assertEqual(evidence["axis_origin_mm"], list(origin))
        self.assertEqual(
            evidence["axial_bounds_mm"], [body.BoundBox.YMin, body.BoundBox.YMax]
        )
        self.assertAlmostEqual(envelope.BoundBox.YMin, body.BoundBox.YMin)
        self.assertAlmostEqual(envelope.BoundBox.YMax, body.BoundBox.YMax)
        self.assertAlmostEqual(envelope.CenterOfMass.x, origin.x)
        self.assertAlmostEqual(envelope.CenterOfMass.z, origin.z)
        for angle in (-179, -93, -17, 0, 31, 137, 180, 359):
            with self.subTest(angle=angle):
                rotated = body.copy()
                rotated.rotate(origin, App.Vector(0, 1, 0), angle)
                self.assertLess(abs(rotated.cut(envelope).Volume), 1e-7)

    def test_an_intermediate_collision_is_not_cleared_by_safe_endpoints(self):
        from gondola.validation.rotation_envelope import full_orbit_envelope

        body = Part.makeBox(1, 1, 1, App.Vector(3, -0.5, -0.5))
        obstacle = Part.makeBox(0.2, 0.2, 0.2, App.Vector(-0.1, -0.1, -3.6))
        opposite = body.copy()
        opposite.rotate(App.Vector(), App.Vector(0, 1, 0), 180)
        self.assertGreater(body.distToShape(obstacle)[0], 1)
        self.assertGreater(opposite.distToShape(obstacle)[0], 1)
        intermediate = body.copy()
        intermediate.rotate(App.Vector(), App.Vector(0, 1, 0), 90)
        self.assertGreater(intermediate.common(obstacle).Volume, 0)
        envelope, _ = full_orbit_envelope(body, (0, 0, 0))
        self.assertGreater(envelope.common(obstacle).Volume, 0)

    def test_envelope_distance_is_a_lower_clearance_bound(self):
        from gondola.validation.rotation_envelope import full_orbit_envelope

        body = Part.makeBox(1, 2, 1, App.Vector(2, 4, -0.5))
        envelope, evidence = full_orbit_envelope(body, (0, 100, 0))
        self.assertAlmostEqual(evidence["radius_mm"], math.hypot(3, 0.5))
        obstacle = Part.makeBox(20, 1, 20, App.Vector(-10, 6.7, -10))
        bound = envelope.distToShape(obstacle)[0]
        self.assertAlmostEqual(bound, 0.7)
        for angle in (-151, -45, 0, 38, 179):
            rotated = body.copy()
            rotated.rotate(App.Vector(), App.Vector(0, 1, 0), angle)
            self.assertGreaterEqual(rotated.distToShape(obstacle)[0], bound - 1e-7)

    def test_invalid_axis_or_non_solid_geometry_is_rejected(self):
        from gondola.validation.rotation_envelope import full_orbit_envelope

        body = Part.makeBox(1, 1, 1)
        for origin in ((0, 0), (0, 0, 0, 0), (0, math.nan, 0), None):
            with self.subTest(origin=origin):
                with self.assertRaises(ValueError):
                    full_orbit_envelope(body, origin)
        for shape in (Part.Shape(), Part.makeLine(App.Vector(), App.Vector(1, 0, 0))):
            with self.subTest(shape=shape):
                with self.assertRaises(ValueError):
                    full_orbit_envelope(shape, (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
