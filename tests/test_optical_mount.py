"""Literal load paths and clearances of the integral FC/optical carrier."""

import json
import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires FreeCAD")
class OpticalMountTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.parts import instrument_mount, optical_mount, optical_sensor

        cls.doc = App.newDocument("OpticalMountRegression")
        module = cls.doc.addObject("App::Part", "ElectronicsEquipmentModule")
        cls.instrument = instrument_mount.build_mount(cls.doc, module)
        cls.host = cls.instrument["pitch_stage"]
        cls.module = optical_mount.build_optical_mount(cls.doc, cls.host)
        optical_sensor.build_sensor(cls.doc, cls.module["sensor_frame"])
        cls.doc.recompute()

    @classmethod
    def tearDownClass(cls):
        App.closeDocument(cls.doc.Name)

    def setUp(self):
        from gondola.parts.instrument_mount import set_pitch

        set_pitch(self.doc, 0)

    def test_support_is_integral_with_no_optical_print_or_foot_fasteners(self):
        self.assertEqual(self.module["printed"], [])
        self.assertEqual(self.module["hardware"], [])
        for name in (
            "OpticalSensorTray",
            "OpticalMountBase",
            "OpticalPitchStage",
            "OpticalFootBolt1",
            "OpticalFootBolt2",
            "OpticalFootNut1",
            "OpticalFootNut2",
        ):
            self.assertIsNone(self.doc.getObject(name))
        self.assertEqual(
            self.doc.ElectronicsMount.getParentGeoFeatureGroup(), self.host
        )
        self.assertEqual(
            self.doc.OpticalFlowModule.getParentGeoFeatureGroup(), self.host
        )
        self.assertEqual(
            self.doc.OpticalSensorFrame.getParentGeoFeatureGroup(),
            self.doc.OpticalFlowModule,
        )
        self.assertFalse(self.doc.OpticalSensorFrame.ExpressionEngine)
        self.assertNotIn("Pitch", self.doc.OpticalSensorFrame.PropertiesList)
        self.assertTrue(self.doc.ElectronicsMount.Shape.isValid())
        self.assertEqual(len(self.doc.ElectronicsMount.Shape.Solids), 1)
        contract = json.loads(self.doc.OpticalFlowModule.OpticalMountContract)
        self.assertEqual(contract["adjustment_degrees_of_freedom"], 0)
        self.assertEqual(contract["support_part"], "ElectronicsMount")
        for key in (
            "holding_torque_verified",
            "self_levelling",
            "physical_angle_stops_modeled",
        ):
            self.assertFalse(contract[key])

    def test_balanced_posts_diagonal_roof_and_pad_have_continuous_stock(self):
        from gondola.validation.optical import _rigid_interface_checks

        result = _rigid_interface_checks(self.doc)
        self.assertTrue(result["passed"], result)
        shape = self.doc.ElectronicsMount.Shape
        upper = shape.common(Part.makeBox(70, 70, 26, App.Vector(-35, -35, 19)))
        reflected = upper.copy()
        reflected.rotate(App.Vector(), App.Vector(0, 0, 1), 180)
        self.assertLess(upper.cut(reflected).Volume, 1e-5)
        self.assertLess(reflected.cut(upper).Volume, 1e-5)
        self.assertAlmostEqual(upper.BoundBox.ZMax, 44)
        self.assertAlmostEqual(self.doc.ModuleMTF02PEnvelope.Shape.BoundBox.ZMin, 45)

    def test_underbody_and_service_channel_remain_open(self):
        from gondola.validation.optical import _rigid_interface_checks

        result = _rigid_interface_checks(self.doc)
        self.assertLess(result["fc_underbody_intrusion_mm3"], 1e-5)
        self.assertLess(result["fc_connector_and_wire_intrusion_mm3"], 1e-5)
        self.assertLess(result["central_channel_intrusion_mm3"], 1e-5)
        part = self.doc.ElectronicsMount
        original = part.Shape.copy()
        try:
            part.Shape = part.Shape.fuse(Part.makeBox(1, 1, 2, App.Vector(0, 0, 25)))
            self.assertFalse(_rigid_interface_checks(self.doc)["passed"])
        finally:
            part.Shape = original

    def test_missing_load_path_or_pad_is_rejected(self):
        from gondola.validation.optical import _rigid_interface_checks

        part = self.doc.ElectronicsMount
        original = part.Shape.copy()
        for origin in ((-31, -31, 27), (9, 9, 41), (-1, -1, 42)):
            try:
                part.Shape = original.cut(Part.makeBox(2, 3, 2, App.Vector(*origin)))
                self.assertFalse(_rigid_interface_checks(self.doc)["passed"], origin)
            finally:
                part.Shape = original

    def test_manufacturing_probes_measure_integral_saved_stock(self):
        from gondola.parts.optical_interface import manufacturing_wall_probes
        from gondola.validation.manufacturing import material_length_on_line

        for name, part, start, end, expected in manufacturing_wall_probes():
            self.assertEqual(part, "ElectronicsMount")
            self.assertAlmostEqual(
                material_length_on_line(self.doc.ElectronicsMount.Shape, start, end),
                expected,
                places=5,
                msg=name,
            )

    def test_sensor_support_transform_is_fixed_over_common_pitch(self):
        from gondola.parts.instrument_mount import set_pitch

        expected = (
            self.doc.ElectronicsMount.getGlobalPlacement()
            .inverse()
            .multiply(self.doc.OpticalSensorFrame.getGlobalPlacement())
        )
        for angle in (-20, 0, 20):
            set_pitch(self.doc, angle)
            actual = (
                self.doc.ElectronicsMount.getGlobalPlacement()
                .inverse()
                .multiply(self.doc.OpticalSensorFrame.getGlobalPlacement())
            )
            self.assertTrue(actual.isSame(expected, 1e-7))

    def test_both_sensor_bodies_fields_and_connectors_clear_the_fixed_support(self):
        from gondola.contracts.optical_sensors import SENSOR_PROFILES
        from gondola.parts import equipment_envelopes, optical_sensor, wiring_reserves

        for profile in SENSOR_PROFILES.values():
            for factory in (
                optical_sensor.envelope_shape,
                optical_sensor.optical_reserve_shape,
                optical_sensor.connector_reserve_shape,
            ):
                shape = factory(profile)
                for obstacle in (
                    self.doc.ElectronicsMount.Shape,
                    equipment_envelopes.fc_envelope_shape(),
                    wiring_reserves.reserve_shapes()["FCWiringClearanceReserve"],
                ):
                    self.assertLess(
                        abs(shape.common(obstacle).Volume),
                        1e-5,
                        (profile.key, factory.__name__),
                    )


if __name__ == "__main__":
    unittest.main()
