"""Literal braced guard, keyed shaft root and preserved OEM motor datums."""

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

    def test_motor_plate_and_inboard_web_retain_three_mm_backing(self):
        self.assertTrue(self.carrier.isValid())
        self.assertEqual(len(self.carrier.Solids), 1)
        # Keep the motor disk and the retained inboard beam, avoiding the
        # central clip hole, three radial slots and outer R0.5 edge rounds.
        for y, z in ((-12, -3), (5, -1), (-1, 5)):
            witness = Part.makeBox(3, 2, 2, App.Vector(-8, y, z))
            self.assertLess(witness.cut(self.carrier).Volume, 1e-6)
        for x in (-8.2, -4.99):
            outside = Part.makeBox(0.1, 2, 2, App.Vector(x, 5, -1))
            self.assertLess(outside.common(self.carrier).Volume, 1e-6)
        triangular_core = Part.makeBox(2, 3, 6, App.Vector(-4, -19, -3))
        self.assertLess(triangular_core.cut(self.carrier).Volume, 1e-6)

    def test_handed_carriers_have_one_keyed_root_and_a_far_guard_return(self):
        from gondola.cad import mirrored_y
        from gondola.parts import propulsion

        starboard = propulsion.moving_carrier_shape(-1)
        reflected = mirrored_y(self.carrier, -1)
        self.assertLess(starboard.cut(reflected).Volume, 1e-6)
        self.assertLess(reflected.cut(starboard).Volume, 1e-6)
        root = Part.makeBox(5, 10, 6, App.Vector(-7, -30.5, -3))
        rear_bridge = Part.makeBox(3, 17.8, 8, App.Vector(-8, 8.2, -4))
        outer_return = Part.makeBox(19, 3, 8, App.Vector(-8, 23, -4))
        # Keep the complete rectangular witness inside the R23 circular
        # opening, including its Z=+/-4 corners.
        opening = Part.makeBox(12.9, 14.5, 8, App.Vector(-3.9, 8, -4))
        for carrier, sign in ((self.carrier, 1), (starboard, -1)):
            self.assertLess(mirrored_y(root, sign).cut(carrier).Volume, 1e-6)
            self.assertLess(mirrored_y(rear_bridge, sign).cut(carrier).Volume, 1e-6)
            self.assertLess(mirrored_y(outer_return, sign).cut(carrier).Volume, 1e-6)
            self.assertLess(mirrored_y(opening, sign).common(carrier).Volume, 1e-6)
        self.assertLess(self.carrier.Solids[0].CenterOfMass.y, -1)
        self.assertAlmostEqual(
            self.carrier.Solids[0].CenterOfMass.y, -starboard.Solids[0].CenterOfMass.y
        )

    def test_three_oem_motor_screw_axes_still_pass_through_the_full_plate(self):
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
            self.assertAlmostEqual(guard.BoundBox.XMax, 11)
            self.assertEqual(contract["guard_axial_range_mm"], [8, 11])
            self.assertEqual(contract["guard_inner_outer_radius_mm"], [23, 26])
            self.assertEqual(contract["guard_root_fan_height_mm"], 12)
            # The supplier's positive body-length tolerance must also clear
            # the print, independently of the nominal display body.
            maximum_body = Part.makeCylinder(
                6.8, 8.9, App.Vector(-5, 0, 0), App.Vector(1, 0, 0)
            )
            self.assertLess(maximum_body.common(self.carrier).Volume, 1e-6)
        finally:
            App.closeDocument(doc.Name)

    @staticmethod
    def root_witnesses(shape):
        # Literal D opening covers the complete10mm grip plus the retained
        # shaft tip beyond the root. The flat land is away from the radial jack.
        socket = Part.makeCylinder(
            1.5, 10.6, App.Vector(0, -30.6, 0), App.Vector(0, 1, 0)
        ).cut(Part.makeBox(3, 10.8, 4, App.Vector(1.05, -30.7, -2)))
        key = Part.makeBox(0.2, 1, 0.6, App.Vector(1.05, -29.5, -0.3))
        closed_root = Part.makeBox(3, 2, 0.6, App.Vector(2, -30, -0.3))
        guard_join = Part.makeBox(1.8, 0.8, 1, App.Vector(8.1, -23.9, 2))
        ring_top = Part.makeBox(3, 0.2, 2.8, App.Vector(8, -0.1, 23.1))
        root_fan = (
            Part.makeBox(3, 10, 12, App.Vector(8, -30.5, -6))
            .cut(Part.makeCylinder(23, 5, App.Vector(7, 0, 0), App.Vector(1, 0, 0)))
            .cut(
                Part.makeCylinder(
                    1.1, 12.2, App.Vector(0.9, -25.5, 0), App.Vector(1, 0, 0)
                )
            )
        )
        rear_bridge = Part.makeBox(3, 17.8, 8, App.Vector(-8, 8.2, -4))
        outer_return = Part.makeBox(19, 3, 8, App.Vector(-8, 23, -4))
        return_root = Part.makeBox(1, 1, 8, App.Vector(-5, 22, -4)).cut(
            Part.makeCylinder(1, 8, App.Vector(-4, 22, -4))
        )
        return {
            "blocked_socket": socket.common(shape).Volume,
            "missing_key": key.cut(shape).Volume,
            "missing_closed_root": closed_root.cut(shape).Volume,
            "missing_guard_join": guard_join.cut(shape).Volume,
            "missing_guard_top": ring_top.cut(shape).Volume,
            "missing_root_fan": root_fan.cut(shape).Volume,
            "missing_rear_bridge": rear_bridge.cut(shape).Volume,
            "missing_outer_return": outer_return.cut(shape).Volume,
            "missing_return_root": return_root.cut(shape).Volume,
        }

    def test_d_socket_and_solid_root_join_preserve_the_guard(self):
        result = self.root_witnesses(self.carrier)
        self.assertTrue(all(volume < 1e-6 for volume in result.values()), result)

    def test_literal_root_witnesses_detect_plug_key_loss_and_reopened_split(self):
        cases = (
            (
                "blocked_socket",
                self.carrier.fuse(
                    Part.makeBox(2, 0.5, 0.5, App.Vector(-1.8, -29, -0.25))
                ),
            ),
            (
                "missing_key",
                self.carrier.cut(
                    Part.makeCylinder(
                        1.5, 10, App.Vector(0, -30.5, 0), App.Vector(0, 1, 0)
                    )
                ),
            ),
            (
                "missing_closed_root",
                self.carrier.cut(Part.makeBox(10, 10, 0.8, App.Vector(1, -30.5, -0.4))),
            ),
            (
                "missing_guard_join",
                self.carrier.cut(Part.makeBox(2, 1, 1.2, App.Vector(8, -24, 1.9))),
            ),
            (
                "missing_guard_top",
                self.carrier.cut(Part.makeBox(1, 1, 3, App.Vector(10, -0.5, 23))),
            ),
            (
                "missing_root_fan",
                self.carrier.cut(Part.makeBox(3, 2, 1, App.Vector(8, -29, 5))),
            ),
            (
                "missing_rear_bridge",
                self.carrier.cut(Part.makeBox(1, 3, 8, App.Vector(-8, 14, -4))),
            ),
            (
                "missing_outer_return",
                self.carrier.cut(Part.makeBox(4, 1, 8, App.Vector(0, 23, -4))),
            ),
            (
                "missing_return_root",
                self.carrier.cut(Part.makeBox(1, 1, 8, App.Vector(-5, 22, -4))),
            ),
        )
        for field, damaged in cases:
            with self.subTest(defect=field):
                self.assertGreater(self.root_witnesses(damaged)[field], 0.1)

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
