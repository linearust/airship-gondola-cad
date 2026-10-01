"""Printed motor datum, uncertain propeller seating and open shaft clamps."""

import json
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
            witness = Part.makeBox(3, 2, 2, App.Vector(-8, y, z))
            self.assertLess(witness.cut(self.carrier).Volume, 1e-6)
        for y in (-12, 10):
            for x in (-8.2, -4.99):
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
                0.7, 5, App.Vector(-9, 3.3, 0), App.Vector(1, 0, 0)
            )
            shaft.rotate(App.Vector(), App.Vector(1, 0, 0), angle)
            self.assertLess(shaft.common(self.carrier).Volume, 1e-6)

    def test_motor_face_is_exact_and_propeller_seating_is_explicitly_unverified(self):
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
            self.assertAlmostEqual(motor.BoundBox.XMin, -5)
            self.assertAlmostEqual(motor.BoundBox.XMax, 3.8)
            self.assertAlmostEqual(shaft.BoundBox.XMin, 3.8)
            self.assertAlmostEqual(shaft.BoundBox.XMax, 7.8)
            self.assertAlmostEqual(propeller.CenterOfMass.x, 6.3)
            self.assertAlmostEqual(
                doc.PortPropellerDisk.TiltAxisToCentrePlane.Value, 6.3
            )
            contract = json.loads(doc.PortMotor.RotorGeometryContract)
            self.assertEqual(contract["motor_body_length_tolerance_mm"], [0, 0.1])
            self.assertEqual(contract["motor_rear_projection_derived_nominal_mm"], 1.2)
            self.assertIsNone(contract["actual_hub_seating_offset_mm"])
            self.assertIsNone(contract["actual_blade_axial_envelope_mm"])
            self.assertFalse(doc.PortPropellerDisk.PhysicalSeatingVerified)
            self.assertLess(motor.common(self.carrier).Volume, 1e-6)
            self.assertLess(propeller.common(self.carrier).Volume, 1e-6)
            guard = self.carrier.common(Part.makeBox(4, 2, 4, App.Vector(7, -1, 22)))
            self.assertAlmostEqual(guard.BoundBox.XMin, 8)
            self.assertAlmostEqual(guard.BoundBox.XMax, 10)
            # The supplier's positive body-length tolerance must also clear
            # the print, independently of the nominal display body.
            maximum_body = Part.makeCylinder(
                6.8, 8.9, App.Vector(-5, 0, 0), App.Vector(1, 0, 0)
            )
            self.assertLess(maximum_body.common(self.carrier).Volume, 1e-6)
        finally:
            App.closeDocument(doc.Name)

    def test_integrated_guard_cannot_refill_shaft_clamp_openings(self):
        # Independent witnesses cover the ring/clamp intersection that formerly
        # refilled the split when a guard was united after cutting the clamp.
        for sign in (-1, 1):
            y = 21.3 if sign > 0 else -31.2
            split = Part.makeBox(10.9, 9.9, 0.78, App.Vector(0.01, y, -0.39))
            bore = Part.makeCylinder(
                1.59, 9.9, App.Vector(0, y, 0), App.Vector(0, 1, 0)
            )
            self.assertLess(split.common(self.carrier).Volume, 1e-6)
            self.assertLess(bore.common(self.carrier).Volume, 1e-6)

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
