"""Compact foot reuses the common carrier slot and follows its native parent."""

import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires FreeCAD")
class OpticalCarrierInterfaceTests(unittest.TestCase):
    def test_component_proxies_enclose_compact_base(self):
        from gondola.parts import optical_interface, optical_mount

        shape = optical_mount.base_shape()
        proxies = Part.makeCompound(
            [s for _, s in optical_interface.base_component_proxies()]
        )
        self.assertLess(abs(shape.cut(proxies).Volume), 1e-5)
        self.assertEqual(len(optical_interface.base_component_proxies()), 3)
        self.assertEqual((shape.BoundBox.XLength, shape.BoundBox.YLength), (8, 16))

    def test_both_sides_reuse_existing_slot_without_intersecting_plate(self):
        from gondola.parts import mounting_plate, optical_interface, optical_mount

        plate = mounting_plate.shape()
        for side in optical_interface.SIDES:
            pose = optical_interface.placement(side)
            base = optical_mount.base_shape()
            base.Placement = pose
            self.assertLess(abs(base.common(plate).Volume), 1e-5)
            self.assertAlmostEqual(abs(pose.Base.x), 27)
            self.assertAlmostEqual(pose.Base.y, 0)
            for x, y in optical_interface.CLAMP_CENTRES:
                drill = Part.makeCylinder(1.25, 4, App.Vector(x, y, -3))
                drill.Placement = pose
                self.assertLess(abs(drill.common(plate).Volume), 1e-5)

    def test_registration_bound_encloses_rotated_and_shifted_sensor(self):
        import math

        from gondola.contracts.optical_sensors import get_sensor_profile
        from gondola.parts import optical_interface, optical_sensor

        shape = optical_sensor.envelope_shape(get_sensor_profile("MTF01P"))
        bound = optical_interface.registration_bound(shape)
        for fraction in (-1, -0.5, 0, 0.5, 1):
            for sign in (-1, 1):
                actual = shape.copy()
                actual.rotate(
                    App.Vector(),
                    App.Vector(0, 0, 1),
                    math.degrees(fraction * optical_interface.MAX_REGISTRATION_YAW_RAD),
                )
                actual.translate(
                    App.Vector(
                        sign * optical_interface.MAX_REGISTRATION_X,
                        -sign * optical_interface.MAX_REGISTRATION_Y,
                        0,
                    )
                )
                self.assertLess(abs(actual.cut(bound).Volume), 1e-5)

    def test_native_side_changes_and_reparenting_move_entire_mount(self):
        from gondola.parts import optical_interface, optical_mount

        doc = App.newDocument("OpticalCarrierInterface")
        try:
            hosts = [
                doc.addObject("App::Part", name)
                for name in optical_interface.SUPPORTED_HOSTS
            ]
            hosts[1].Placement.Base = App.Vector(-54, -0.1, 0)
            kit = optical_mount.build_optical_mount(doc, hosts[0])
            optical_interface.attach_to_host(kit["group"], hosts[1], "NegativeX")
            self.assertEqual(kit["group"].getParentGeoFeatureGroup(), hosts[1])
            self.assertEqual(kit["group"].CarrierHostName, hosts[1].Name)
            self.assertEqual(
                tuple(kit["pitch_stage"].getGlobalPlacement().Base), (-81, -0.1, 35)
            )
            self.assertNotIn("RailPositionX", kit["group"].PropertiesList)
            kit["group"].MountSide = "PositiveX"
            doc.recompute()
            self.assertAlmostEqual(kit["pitch_stage"].getGlobalPlacement().Base.x, -27)
            with self.assertRaises(ValueError):
                optical_interface.placement("Unknown")
            other = doc.addObject("App::Part", "NotACarrier")
            with self.assertRaises(ValueError):
                optical_interface.attach_to_host(kit["group"], other)
        finally:
            App.closeDocument(doc.Name)
