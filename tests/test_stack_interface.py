"""Native regressions for integral portal carriers and real bench extraction."""

import math
import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class StackInterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.parts import (
            equipment_envelopes,
            equipment_mounts,
            optical_mount,
            optical_sensor,
            stock_adapter,
        )

        cls.doc = App.newDocument("IntegralPortalRegression")
        cls.battery = cls.doc.addObject("App::Part", "BatteryEquipmentModule")
        cls.electronics = cls.doc.addObject("App::Part", "ElectronicsEquipmentModule")
        cls.battery.Placement.Base.x = -90
        cls.electronics.Placement.Base.x = 90
        for host, kind in ((cls.battery, "battery"), (cls.electronics, "electronics")):
            equipment_mounts.build_mount(cls.doc, host, kind)
        stock_adapter.build_stock_adapter(cls.doc, cls.electronics)
        accessory = cls.doc.addObject("App::Part", "AccessoryEquipmentModule")
        accessory.Placement.Base.x = 180
        equipment_envelopes.build_equipment(
            cls.doc, cls.battery, cls.electronics, accessory
        )
        cls.kit = optical_mount.build_optical_mount(cls.doc, cls.battery)
        cls.refs, cls.reserves = optical_sensor.build_sensor(
            cls.doc, cls.kit["pitch_stage"]
        )
        cls.moving = cls.kit["printed"] + cls.kit["hardware"] + cls.refs
        cls.doc.recompute()

    @classmethod
    def tearDownClass(cls):
        App.closeDocument(cls.doc.Name)

    def setUp(self):
        from gondola.parts import optical_mount, stack_interface

        stack_interface.attach_to_host(self.kit["group"], self.battery)
        optical_mount.set_angles(self.doc, 0, 0)

    def test_transfer_selects_one_integral_carrier_and_restores_previous_low_carrier(
        self,
    ):
        from gondola.parts import equipment_mounts
        from gondola.parts import stack_interface as s
        from gondola.validation.optical import tower_attachment_check

        before = {obj.Name: obj.getGlobalPlacement().Base for obj in self.moving}
        for host, dx, old, old_kind in (
            (self.electronics, 180, self.doc.BatteryMount, "battery"),
            (self.battery, 0, self.doc.ElectronicsMount, "electronics"),
        ):
            s.attach_to_host(self.kit["group"], host)
            carrier = s.host_print(self.kit["group"])
            self.assertEqual(self.kit["group"].IntegratedCarrierName, carrier.Name)
            self.assertTrue(carrier.IntegralOpticalSupport)
            self.assertFalse(old.IntegralOpticalSupport)
            expected = equipment_mounts.mount_shape(old_kind)
            self.assertLess(
                abs(old.Shape.cut(expected).Volume)
                + abs(expected.cut(old.Shape).Volume),
                1e-5,
            )
            for obj in self.moving:
                self.assertLess(
                    (
                        obj.getGlobalPlacement().Base
                        - before[obj.Name]
                        - App.Vector(dx, 0, 0)
                    ).Length,
                    1e-7,
                )
            check = tower_attachment_check(self.doc, host)
            self.assertTrue(check["passed"], check)
            self.assertEqual(len(check["integral_roots"]), 2)

    def test_host_roundtrip_restores_exact_low_carrier_property_schema_and_values(self):
        from gondola.parts import stack_interface as s

        carrier = self.doc.ElectronicsMount
        names = tuple(carrier.PropertiesList)
        values = {key: str(getattr(carrier, key)) for key in names if key != "Shape"}
        original_shape = carrier.Shape.copy()
        s.attach_to_host(self.kit["group"], self.electronics)
        self.assertTrue(carrier.IntegralOpticalSupport)
        s.attach_to_host(self.kit["group"], self.battery)
        self.assertEqual(tuple(carrier.PropertiesList), names)
        self.assertEqual({key: str(getattr(carrier, key)) for key in values}, values)
        self.assertLess(
            abs(original_shape.cut(carrier.Shape).Volume)
            + abs(carrier.Shape.cut(original_shape).Volume),
            1e-5,
        )
        self.assertEqual(carrier.getParentGeoFeatureGroup(), self.electronics)

    def test_rectangular_portal_beams_are_flush_and_have_no_feet_or_holes(self):
        from gondola.parts import stack_interface as s

        tower = s.tower_shape()
        tower.rotate(App.Vector(), App.Vector(0, 0, 1), -45)
        half_span = (
            math.hypot(*s.ANCHOR_CENTRES[0]) + s.FIXED_LEG_INNER + s.FIXED_LEG_THICKNESS
        )
        expected = Part.makeBox(
            2 * half_span,
            s.LEG_WIDTH,
            s.TOP_BEAM_THICKNESS,
            App.Vector(-half_span, -s.LEG_WIDTH / 2, 0),
        )
        top = tower.common(Part.makeBox(200, 200, 10, App.Vector(-100, -100, 0)))
        self.assertLess(
            abs(top.cut(expected).Volume) + abs(expected.cut(top).Volume), 1e-5
        )
        self.assertEqual(len(tower.Solids), 1)
        self.assertIsNone(self.doc.getObject("OpticalMountBase"))
        self.assertFalse(any("StackFoot" in obj.Name for obj in self.doc.Objects))
        self.assertEqual(len(self.kit["printed"]), 2)
        self.assertEqual(len(self.kit["hardware"]), 4)

    def test_missing_root_material_is_rejected(self):
        from gondola.parts import stack_interface as s
        from gondola.validation.optical import tower_attachment_check

        carrier = self.doc.BatteryMount
        original = carrier.Shape.copy()
        root = dict(s.structural_component_shapes())["root_arm_0"]
        root.translate(App.Vector(0, 0, s.STACK_TOP_Z))
        try:
            carrier.Shape = original.cut(root)
            result = tower_attachment_check(self.doc, self.battery)
            self.assertFalse(result["passed"], result)
        finally:
            carrier.Shape = original

    def test_portal_cannot_be_fused_to_a_disconnected_carrier(self):
        from gondola.parts import stack_interface as s

        with self.assertRaises(ValueError):
            s.integral_portal_shape(Part.makeBox(2, 2, 2, App.Vector(90, 90, 90)))

    def _fixed(self):
        from gondola.cad import world_shape

        return {
            obj.Name: world_shape(obj)
            for obj in self.doc.Objects
            if obj.isDerivedFrom("Part::Feature")
            and obj not in self.moving + self.reserves
        }

    def test_moving_head_and_maximum_devices_escape_with_integral_portal_retained(self):
        from gondola.parts import stack_interface as s
        from gondola.validation.optical import (
            _device_service_check,
            _head_service_check,
        )

        for host in (self.battery, self.electronics):
            s.attach_to_host(self.kit["group"], host)
            head = _head_service_check(self.doc, self._fixed(), self.moving)
            self.assertTrue(head["passed"], head)
            devices = _device_service_check(self.doc, host, self._fixed())
            self.assertTrue(devices["passed"], devices)
            self.assertTrue(all(row["portal_remains"] for row in devices["devices"]))

    def test_intermediate_side_extraction_blocker_is_not_hidden_by_clear_endpoints(
        self,
    ):
        from gondola.parts import stack_interface as s
        from gondola.validation.optical import _device_service_check

        device = self.doc.ModuleBatteryEnvelope
        shape = s.device_removal_shape(device)
        point = shape.CenterOfMass + App.Vector(-30, 30, 5)
        blocker = Part.makeSphere(0.5, point)
        end = shape.copy()
        end.translate(App.Vector(-60, 60, 5))
        self.assertLess(abs(shape.common(blocker).Volume), 1e-5)
        self.assertLess(abs(end.common(blocker).Volume), 1e-5)
        result = _device_service_check(
            self.doc, self.battery, {**self._fixed(), "UnknownBenchBlocker": blocker}
        )
        self.assertFalse(result["passed"], result)
        self.assertIn(
            "UnknownBenchBlocker", result["bench_service_frame"]["retained_obstacles"]
        )

    def test_bench_filter_keeps_same_carrier_and_unknown_objects(self):
        from gondola.cad import world_shape
        from gondola.validation.optical import _bench_service_obstacles

        extra = self.doc.addObject("Part::Feature", "BenchBlocker")
        extra.Shape = Part.makeBox(1, 1, 1)
        self.battery.addObject(extra)
        try:
            kept, frame = _bench_service_obstacles(
                self.doc,
                {
                    "ElectronicsMount": world_shape(self.doc.ElectronicsMount),
                    "Unknown": Part.makeBox(1, 1, 1),
                },
            )
            self.assertNotIn("ElectronicsMount", kept)
            self.assertIn("BatteryMount", kept)
            self.assertIn(extra.Name, kept)
            self.assertIn("Unknown", kept)
            self.assertTrue(frame["valid_supported_host"])
        finally:
            self.doc.removeObject(extra.Name)

    def test_unsupported_host_rejected_without_changing_assembly(self):
        from gondola.parts import stack_interface as s

        old = self.kit["group"].getParentGeoFeatureGroup()
        with self.assertRaises(ValueError):
            s.attach_to_host(self.kit["group"], self.doc.AccessoryEquipmentModule)
        self.assertEqual(self.kit["group"].getParentGeoFeatureGroup(), old)
        self.assertTrue(self.doc.BatteryMount.IntegralOpticalSupport)


if __name__ == "__main__":
    unittest.main()
