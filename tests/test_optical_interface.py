"""Rigid bracket uses two existing plate slots and explicit shared parentage."""

import itertools
import math
import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires FreeCAD")
class OpticalInstrumentInterfaceTests(unittest.TestCase):
    def new_mount(self):
        from gondola.parts import mounting_plate, optical_mount

        doc = App.newDocument("OpticalInstrumentInterface")
        self.addCleanup(App.closeDocument, doc.Name)
        host = doc.addObject("App::Part", "InstrumentPitchStage")
        plate = doc.addObject("Part::Feature", "ElectronicsMount")
        plate.Shape = mounting_plate.shape()
        host.addObject(plate)
        optical_mount.build_optical_mount(doc, host)
        return doc

    def test_component_proxies_enclose_complete_bracket_and_exclude_empty_window(self):
        from gondola.cad import union
        from gondola.parts import optical_interface, optical_mount

        shape = optical_mount.sensor_tray_shape()
        proxies = union([s for _, s in optical_interface.base_component_proxies()])
        self.assertLess(abs(shape.cut(proxies).Volume), 1e-5)
        # The empty space above the foot remains available for FC wiring;
        # a single full bounding box would create a false collision here.
        inside_window = Part.makeBox(10, 4, 8, App.Vector(-5, -2, 5))
        self.assertLess(abs(inside_window.common(proxies).Volume), 1e-5)

    def test_both_existing_slots_and_both_bearing_lands_are_open(self):
        from gondola.parts import mounting_plate, optical_interface, optical_mount

        plate = mounting_plate.shape()
        shape = optical_mount.sensor_tray_shape()
        shape.Placement = optical_interface.placement()
        self.assertLess(abs(shape.common(plate).Volume), 1e-5)
        for x in (-19, 19):
            bore = Part.makeCylinder(1.1, 4, App.Vector(x, 27, 16))
            self.assertLess(abs(bore.common(plate).Volume), 1e-5)
            # Independent literal support strips on both sides of the 2.6mm slot.
            for y in (28.5, 25.1):
                land = Part.makeBox(2, 0.4, 0.2, App.Vector(x - 1, y, 17))
                self.assertLess(abs(land.cut(plate).Volume), 1e-5)
        self.assertEqual(tuple(optical_interface.placement().Base), (0.0, 27.0, 19.0))

    def test_only_common_instrument_parent_is_accepted(self):
        from gondola.contracts.optical_attachment import resolve_mount_mode
        from gondola.parts import optical_interface, optical_mount

        doc = self.new_mount()
        self.assertEqual(
            optical_interface.attachment_description(doc.OpticalFlowModule)["host"],
            "InstrumentPitchStage",
        )
        for mode in ("carrier", "rail", "", [], None):
            if mode is None:
                self.assertEqual(resolve_mount_mode(mode), "instrument")
            else:
                with self.assertRaises(ValueError):
                    resolve_mount_mode(mode)
        other = doc.addObject("App::Part", "BatteryEquipmentModule")
        with self.assertRaises(ValueError):
            optical_mount.build_optical_mount(doc, other)
        other.addObject(doc.OpticalFlowModule)
        with self.assertRaises(ValueError):
            optical_interface.attachment_description(doc.OpticalFlowModule)

    def test_registration_reserve_bounds_combined_hole_and_slot_freedom(self):
        from gondola.parts import optical_interface as interface

        per_joint = (2.9 - 1.8) / 2 + (2.5 - 1.8) / 2
        yaw = math.asin(2 * per_joint / 38)
        self.assertGreaterEqual(interface.MAX_REGISTRATION_YAW_RAD, yaw)
        self.assertGreaterEqual(interface.MAX_REGISTRATION_Y, per_joint)
        self.assertGreaterEqual(
            interface.MAX_REGISTRATION_X, per_joint + 19 * (1 - math.cos(yaw))
        )
        self.assertFalse(
            interface.interface_contract()["full_free_screw_offset_support_qualified"]
        )

    def test_registration_bound_encloses_sensor_and_complete_bracket(self):
        from gondola.contracts.optical_sensors import get_sensor_profile
        from gondola.parts import (
            optical_interface as interface,
        )
        from gondola.parts import (
            optical_mount,
            optical_sensor,
        )

        for shape in (
            optical_sensor.envelope_shape(get_sensor_profile("MTF01P")),
            optical_mount.sensor_tray_shape(),
        ):
            bound = interface.registration_bound(shape)
            for fraction, sx, sy in itertools.product(
                (-1, -0.5, 0, 0.5, 1), (-1, 1), (-1, 1)
            ):
                actual = shape.copy()
                actual.rotate(
                    App.Vector(),
                    App.Vector(0, 0, 1),
                    math.degrees(fraction * interface.MAX_REGISTRATION_YAW_RAD),
                )
                actual.translate(
                    App.Vector(
                        sx * interface.MAX_REGISTRATION_X,
                        sy * interface.MAX_REGISTRATION_Y,
                        0,
                    )
                )
                self.assertLess(abs(actual.cut(bound).Volume), 1e-5)
