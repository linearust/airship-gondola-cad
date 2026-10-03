"""Native geometry checks for the rigid common-platform optical bracket."""

import itertools
import json
import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class OpticalMountTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.parts import optical_mount

        cls.doc = App.newDocument("OpticalMountRegression")
        cls.host = cls.doc.addObject("App::Part", "InstrumentPitchStage")
        cls.module = optical_mount.build_optical_mount(cls.doc, cls.host)

    @classmethod
    def tearDownClass(cls):
        App.closeDocument(cls.doc.Name)

    def setUp(self):
        self.host.Placement = App.Placement()
        self.doc.recompute()

    def test_one_rigid_print_and_two_common_fastener_pairs(self):
        from gondola.contracts import fasteners

        self.assertEqual(len(self.module["printed"]), 1)
        self.assertEqual(len(self.module["hardware"]), 4)
        for absent in (
            "OpticalMountBase",
            "OpticalPitchStage",
            "OpticalPitchBolt",
            "OpticalRollStage",
        ):
            self.assertIsNone(self.doc.getObject(absent))
        self.assertEqual(
            self.doc.OpticalSensorFrame.getParentGeoFeatureGroup(),
            self.doc.OpticalFlowModule,
        )
        self.assertEqual(
            self.doc.OpticalFlowModule.getParentGeoFeatureGroup(), self.host
        )
        self.assertFalse(self.doc.OpticalSensorFrame.ExpressionEngine)
        self.assertNotIn("Pitch", self.doc.OpticalSensorFrame.PropertiesList)
        for obj in self.module["printed"] + self.module["hardware"]:
            self.assertTrue(obj.Shape.isValid(), obj.Name)
            self.assertEqual(len(obj.Shape.Solids), 1, obj.Name)
        for obj in self.module["hardware"]:
            self.assertFalse(obj.PrintPart)
            self.assertEqual(
                obj.HardwareSKU,
                "M2X8_BUTTON_HEAD" if "Bolt" in obj.Name else "M2_HEX_NUT",
            )
            self.assertEqual(obj.MaterialSelection, fasteners.KIT_MATERIAL)
        contract = json.loads(self.module["group"].OpticalMountContract)
        self.assertEqual(contract["adjustment_degrees_of_freedom"], 0)
        self.assertEqual(
            contract["shared_adjustment_control"], "InstrumentPitchStage.Pitch"
        )
        for key in (
            "holding_torque_verified",
            "self_levelling",
            "physical_angle_stops_modeled",
        ):
            self.assertFalse(contract[key])

    def test_two_full_height_supports_and_continuous_pad_have_real_stock(self):
        shape = self.doc.OpticalSensorTray.Shape
        for origin, size in (
            ((-25, -4, 2), (3, 8, 16.5)),
            ((22, -4, 2), (3, 8, 16.5)),
            ((-20, -2, 18.5), (40, 4, 2)),
            ((-8, -5, 18.5), (16, 10, 2)),
        ):
            witness = Part.makeBox(*size, App.Vector(*origin))
            self.assertLess(abs(witness.cut(shape).Volume), 1e-5)
        self.assertAlmostEqual(shape.BoundBox.ZMin, 0, places=6)
        self.assertAlmostEqual(shape.BoundBox.ZMax, 20.5, places=6)
        # Root rounds add real material beyond the straight stock.
        for x in (-25.25, -21.75, 21.75, 25.25):
            self.assertTrue(shape.isInside(App.Vector(x, 0, 2.03), 1e-7, False))
        self.assertFalse(shape.isInside(App.Vector(8.99, 5.99, 19.5), 1e-7, True))

    def test_front_notch_preserves_full_fc_underbody_rectangle_and_rear_bridge(self):
        from gondola.parts import optical_interface

        shape = self.doc.OpticalSensorTray.Shape.copy()
        shape.Placement = optical_interface.placement()
        # Complete published body footprint, not just the narrower wire lane.
        underbody = Part.makeBox(36, 36, 8, App.Vector(-18, -18, 19))
        underbody.rotate(App.Vector(), App.Vector(0, 0, 1), -45)
        self.assertLess(abs(shape.common(underbody).Volume), 1e-5)
        self.assertGreaterEqual(shape.distToShape(underbody)[0], 1.5 - 1e-5)
        bridge = Part.makeBox(12, 3, 2, App.Vector(-6, 1, 0))
        self.assertLess(abs(bridge.cut(self.doc.OpticalSensorTray.Shape).Volume), 1e-5)
        restored_notch = Part.makeBox(12, 5, 2, App.Vector(-6, 23, 19))
        self.assertGreater(restored_notch.common(underbody).Volume, 10)

    def test_recess_floor_and_side_wall_are_printable_with_negative_control(self):
        from gondola.validation.manufacturing import (
            material_length_on_line,
            planar_wall_regions,
        )

        shape = self.doc.OpticalSensorTray.Shape
        regions = planar_wall_regions(shape)
        self.assertTrue(regions)
        self.assertTrue(
            all(row["material_thickness_mm"] >= 1.5 - 1e-5 for row in regions), regions
        )
        for x in (-19, 19):
            self.assertAlmostEqual(
                material_length_on_line(shape, (x + 1.5, 0, -0.01), (x + 1.5, 0, 2.01)),
                1.5,
                places=6,
            )
            self.assertAlmostEqual(
                material_length_on_line(shape, (x, 2.09, 1.75), (x, 4.01, 1.75)),
                1.875,
                places=6,
            )
        damaged = shape.cut(Part.makeBox(1, 1, 0.7, App.Vector(20, -0.5, 0)))
        self.assertAlmostEqual(
            material_length_on_line(damaged, (20.5, 0, -0.01), (20.5, 0, 2.01)),
            0.8,
            places=6,
        )

    def test_all_manufacturing_probes_measure_actual_saved_stock(self):
        from gondola.parts import optical_interface
        from gondola.validation.manufacturing import material_length_on_line

        for (
            name,
            part,
            start,
            end,
            expected,
        ) in optical_interface.manufacturing_wall_probes():
            self.assertEqual(part, "OpticalSensorTray")
            self.assertAlmostEqual(
                material_length_on_line(self.doc.OpticalSensorTray.Shape, start, end),
                expected,
                places=5,
                msg=name,
            )

    def test_entire_attachment_follows_shared_host_without_relative_motion(self):
        from gondola.cad import world_shape

        objects = self.module["printed"] + self.module["hardware"]
        original = {obj.Name: world_shape(obj) for obj in objects}
        pose = App.Placement(
            App.Vector(37, -9, 19.5), App.Rotation(App.Vector(0, 1, 0), 20)
        )
        self.host.Placement = pose
        self.doc.recompute()
        for obj in objects:
            expected = original[obj.Name].copy()
            expected.Placement = pose.multiply(expected.Placement)
            self.assertLess(abs(expected.cut(world_shape(obj)).Volume), 1e-5)
            self.assertLess(abs(world_shape(obj).cut(expected).Volume), 1e-5)
        for first, second in itertools.combinations(objects, 2):
            self.assertLess(
                abs(world_shape(first).common(world_shape(second)).Volume),
                1e-5,
                (first.Name, second.Name),
            )

    def test_both_screws_engage_complete_nuts_and_clear_print(self):
        from gondola.cad import world_shape

        for index, x in ((1, -19), (2, 19)):
            bolt = self.doc.getObject(f"OpticalFootBolt{index}")
            nut = self.doc.getObject(f"OpticalFootNut{index}")
            core = Part.makeCylinder(0.8, 1.6, App.Vector(x, 0, 1.5))
            self.assertLess(abs(core.cut(bolt.Shape).Volume), 1e-5)
            self.assertAlmostEqual(nut.Shape.BoundBox.ZLength, 1.6, places=6)
            self.assertAlmostEqual(
                bolt.Shape.BoundBox.ZMax - nut.Shape.BoundBox.ZMax, 2.9, places=6
            )
            self.assertLess(
                abs(core.common(self.doc.OpticalSensorTray.Shape).Volume), 1e-5
            )
            self.assertLess(
                abs(
                    world_shape(bolt)
                    .common(world_shape(self.doc.OpticalSensorTray))
                    .Volume
                ),
                1e-5,
            )

    def test_each_sensor_and_connector_clear_shared_fc_and_wiring(self):
        from gondola.contracts.optical_sensors import SENSOR_PROFILES
        from gondola.parts import equipment_envelopes, optical_sensor, wiring_reserves

        fc = equipment_envelopes.fc_envelope_shape()
        wire = wiring_reserves.reserve_shapes()["FCWiringClearanceReserve"]
        for profile in SENSOR_PROFILES.values():
            for factory in (
                optical_sensor.envelope_shape,
                optical_sensor.optical_reserve_shape,
                optical_sensor.connector_reserve_shape,
            ):
                shape = factory(profile)
                shape.Placement = self.doc.OpticalFlowModule.Placement
                for obstacle in (fc, wire):
                    self.assertLess(abs(shape.common(obstacle).Volume), 1e-5)
                    self.assertGreaterEqual(shape.distToShape(obstacle)[0], 4.5 - 1e-5)


if __name__ == "__main__":
    unittest.main()
