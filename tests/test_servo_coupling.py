"""Regress the bought-horn fit and functional walls of its split axle clamp."""

import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires FreeCAD")
class ServoCouplingTests(unittest.TestCase):
    def test_unclosed_parts_fit_without_intersection(self):
        from gondola.parts import servo_coupling as coupling

        horn = coupling.horn_shape()
        halves = coupling.adapter_half_shapes()
        shaft = Part.makeCylinder(1.5, 26, App.Vector(0, 7.3, 0), App.Vector(0, 1, 0))
        for shape in (horn, *halves):
            self.assertTrue(shape.isValid())
            self.assertEqual(len(shape.Solids), 1)
        for half in halves:
            for purchased in (horn, shaft):
                self.assertLess(half.common(purchased).Volume, 1e-7)
                self.assertAlmostEqual(half.distToShape(purchased)[0], 0.2, places=6)
        self.assertAlmostEqual(halves[0].distToShape(halves[1])[0], 0.6, places=6)

    def test_blade_mouth_has_no_submillimetre_front_lip(self):
        from gondola.parts import servo_coupling as coupling

        # The old recessed mouth left a 0.05 mm PA12 skin. Its entire intended
        # blade-entry corridor must now stay open through the body's front.
        corridor = Part.makeBox(8, 0.4, 4, App.Vector(5, 1.5, -2))
        for half in coupling.adapter_half_shapes():
            self.assertLess(half.common(corridor).Volume, 1e-7)

    def test_recessed_nuts_keep_functional_perimeter_walls(self):
        from gondola.parts import servo_coupling as coupling

        lower, _ = coupling.adapter_half_shapes()
        # Three full 1.5 mm material strips beyond the worst-case square-pocket
        # edges prove the flange is not the former 0.35–0.55 mm remnant.
        witnesses = (
            Part.makeBox(0.2, 1.5, 1.2, App.Vector(9.9, 9.6, -4.4)),
            Part.makeBox(1.5, 0.2, 1.2, App.Vector(6.7, 11.0, -4.4)),
            Part.makeBox(1.5, 0.2, 1.2, App.Vector(0.8, 11.0, -4.4)),
        )
        for witness in witnesses:
            self.assertAlmostEqual(
                lower.common(witness).Volume, witness.Volume, places=6
            )

    def test_opposed_planar_faces_have_no_wall_below_1p5mm(self):
        from gondola.parts import servo_coupling as coupling
        from gondola.validation.manufacturing import planar_wall_regions

        for half in coupling.adapter_half_shapes():
            thin = [
                row
                for row in planar_wall_regions(half)
                if row["material_thickness_mm"] < 1.5 - 1e-6
            ]
            self.assertEqual(thin, [])


if __name__ == "__main__":
    unittest.main()
