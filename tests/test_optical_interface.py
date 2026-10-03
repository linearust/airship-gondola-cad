"""Integral optical support has no detachable printed-joint registration play."""

import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires FreeCAD")
class OpticalInstrumentInterfaceTests(unittest.TestCase):
    def new_mount(self):
        from gondola.parts import instrument_mount, optical_mount

        doc = App.newDocument("OpticalInstrumentInterface")
        self.addCleanup(App.closeDocument, doc.Name)
        module = doc.addObject("App::Part", "ElectronicsEquipmentModule")
        instrument = instrument_mount.build_mount(doc, module)
        optical_mount.build_optical_mount(doc, instrument["pitch_stage"])
        return doc

    def test_integral_support_has_one_identity_frame_and_no_secondary_hardware(self):
        from gondola.parts import optical_interface

        doc = self.new_mount()
        self.assertTrue(doc.OpticalFlowModule.Placement.isSame(App.Placement(), 1e-7))
        self.assertTrue(doc.OpticalSensorFrame.Placement.isSame(App.Placement(), 1e-7))
        contract = optical_interface.interface_contract()
        self.assertEqual(contract["support_part"], "ElectronicsMount")
        self.assertEqual(contract["pad_top_in_stage_mm"], 44)
        self.assertFalse(contract["industry_standard_claimed"])
        self.assertNotIn("foot_bolt_centres_xy_mm", contract)

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

    def test_registration_copy_does_not_invent_a_detachable_tolerance_stack(self):
        from gondola.parts import optical_interface, optical_sensor

        shape = optical_sensor.envelope_shape()
        result = optical_interface.registration_bound(shape)
        self.assertLess(result.cut(shape).Volume, 1e-7)
        self.assertLess(shape.cut(result).Volume, 1e-7)
        result.translate(App.Vector(10, 0, 0))
        self.assertGreater(shape.cut(result).Volume, 1)
        self.assertIn(
            "Adhesive placement", optical_interface.interface_contract()["registration"]
        )

    def test_integral_pad_matches_both_selected_sensor_back_footprints(self):
        from gondola.contracts.optical_sensors import SENSOR_PROFILES
        from gondola.parts import optical_sensor

        for profile in SENSOR_PROFILES.values():
            sensor = optical_sensor.envelope_shape(profile)
            support = Part.makeBox(18, 12, 2, App.Vector(-9, -6, 42))
            self.assertAlmostEqual(support.distToShape(sensor)[0], 1)
            self.assertGreaterEqual(sensor.BoundBox.XLength, 18)
            self.assertGreaterEqual(sensor.BoundBox.YLength, 12)
