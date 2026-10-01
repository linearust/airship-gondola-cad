"""Motor support, clean thrust-plane datum and retained local clamp interface."""

import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires FreeCAD")
class MotorCarrierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.parts import propulsion

        cls.carrier = propulsion.moving_carrier_shape()

    def test_reinforced_plate_and_crossbar_have_three_mm_solid_support(self):
        # Independent witness solids avoid the central clip passage and motor
        # mounting slots. Both transverse sides must keep the same backing.
        self.assertTrue(self.carrier.isValid())
        self.assertEqual(len(self.carrier.Solids), 1)
        for y, z in ((-12, -3), (10, -3), (-1, 5)):
            witness = Part.makeBox(3, 2, 2, App.Vector(-7, y, z))
            self.assertLess(witness.cut(self.carrier).Volume, 1e-6)
        for y in (-12, 10):
            for x in (-7.2, -3.99):
                outside = Part.makeBox(0.1, 2, 2, App.Vector(x, y, -3))
                self.assertLess(outside.common(self.carrier).Volume, 1e-6)

    def test_balanced_sides_and_full_depth_motor_holes(self):
        from gondola.cad import mirrored_y

        # The three OEM holes are120 degrees apart; compare the side struts
        # outside that pattern and check the complete carrier's lateral COM.
        positive = self.carrier.common(
            Part.makeBox(40, 30, 60, App.Vector(-10, 10, -30))
        )
        negative = self.carrier.common(
            Part.makeBox(40, 30, 60, App.Vector(-10, -40, -30))
        )
        reflected = mirrored_y(negative, -1)
        self.assertLess(positive.cut(reflected).Volume, 1e-6)
        self.assertLess(reflected.cut(positive).Volume, 1e-6)
        self.assertAlmostEqual(self.carrier.Solids[0].CenterOfMass.y, 0, places=8)
        for angle in (0, 120, 240):
            shaft = Part.makeCylinder(
                0.7, 5, App.Vector(-8, 3.3, 0), App.Vector(1, 0, 0)
            )
            shaft.rotate(App.Vector(), App.Vector(1, 0, 0), angle)
            self.assertLess(shaft.common(self.carrier).Volume, 1e-6)

    def test_guard_is_at_fifteen_mm_and_motor_stack_moves_as_one(self):
        from gondola.cad import create_group
        from gondola.parts import propulsion

        doc = App.newDocument("MotorCarrierDatum")
        try:
            pod = create_group(doc, "PortPod", "Rotating motor")
            propulsion._build_motor_references(doc, pod, "Port", 1)
            doc.recompute()
            motor = doc.PortMotor.Shape
            shaft = doc.PortShaft.Shape
            propeller = doc.PortPropellerDisk.Shape
            self.assertAlmostEqual(motor.BoundBox.XMin, -4)
            self.assertAlmostEqual(motor.BoundBox.XMax, 10)
            self.assertAlmostEqual(shaft.BoundBox.XMin, 10)
            self.assertAlmostEqual(shaft.BoundBox.XMax, 15)
            self.assertAlmostEqual(propeller.CenterOfMass.x, 15)
            self.assertAlmostEqual(
                doc.PortPropellerDisk.TiltAxisToCentrePlane.Value, 15
            )
            self.assertLess(motor.common(self.carrier).Volume, 1e-6)
            self.assertLess(propeller.common(self.carrier).Volume, 1e-6)
            guard = self.carrier.common(Part.makeBox(4, 2, 4, App.Vector(13, -1, 22)))
            self.assertAlmostEqual(guard.BoundBox.XMin, 14)
            self.assertAlmostEqual(guard.BoundBox.XMax, 16)
        finally:
            App.closeDocument(doc.Name)

    def test_original_thirty_mm_full_orbit_reserve_still_contains_carrier(self):
        reserve = Part.makeCylinder(
            30, 62.5, App.Vector(0, -31.25, 0), App.Vector(0, 1, 0)
        )
        for angle in (-180, -135, -90, -45, 0, 45, 90, 135, 180):
            rotated = self.carrier.copy()
            rotated.rotate(App.Vector(), App.Vector(0, 1, 0), angle)
            self.assertLess(rotated.cut(reserve).Volume, 1e-6)


if __name__ == "__main__":
    unittest.main()
