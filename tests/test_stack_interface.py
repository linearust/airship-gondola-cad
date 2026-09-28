"""Native regressions for removable carbon-mounted portals and installed extraction."""

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
            stock_adapter.build_stock_adapter(cls.doc, host, kind)
        accessory = cls.doc.addObject("App::Part", "AccessoryEquipmentModule")
        accessory.Placement.Base.x = 180
        equipment_envelopes.build_equipment(
            cls.doc, cls.battery, cls.electronics, accessory
        )
        cls.kit = optical_mount.build_optical_mount(cls.doc, cls.battery)
        cls.refs, cls.reserves = optical_sensor.build_sensor(
            cls.doc, cls.kit["pitch_stage"]
        )
        cls.moving = [
            obj
            for obj in cls.kit["printed"] + cls.kit["hardware"] + cls.refs
            if obj.Name != "OpticalMountBase" and not obj.Name.startswith("OpticalFoot")
        ]
        cls.doc.recompute()

    @classmethod
    def tearDownClass(cls):
        App.closeDocument(cls.doc.Name)

    def setUp(self):
        from gondola.parts import optical_mount, stack_interface

        stack_interface.attach_to_host(self.kit["group"], self.battery)
        optical_mount.set_angles(self.doc, 0, 0)

    def test_transfer_preserves_bought_plates_and_moves_portal(self):
        from gondola.parts import stack_interface as s
        from gondola.validation.optical import tower_attachment_check

        before = {obj.Name: obj.getGlobalPlacement().Base for obj in self.moving}
        for host, dx, plate in (
            (self.electronics, 180, self.doc.StockFCAdapter),
            (self.battery, 0, self.doc.StockBatteryAdapter),
        ):
            s.attach_to_host(self.kit["group"], host)
            self.assertEqual(self.kit["group"].HostPlateName, plate.Name)
            self.assertFalse(plate.PrintPart)
            self.assertEqual(s.host_print(self.kit["group"]).Name, "OpticalMountBase")
            for obj in self.moving:
                self.assertLess(
                    (
                        obj.getGlobalPlacement().Base
                        - before[obj.Name]
                        - App.Vector(dx, 0, 0)
                    ).Length,
                    1e-7,
                )
            result = tower_attachment_check(self.doc, host)
            self.assertTrue(result["passed"], result)
            self.assertEqual(len(result["nominal_foot_axes"]), 2)

    def test_roundtrip_restores_plate_and_hardware_without_mutating_cached_templates(
        self,
    ):
        from gondola.parts import purchased_hardware as h
        from gondola.parts import stack_interface as s

        plate = self.doc.StockFCAdapter
        original = plate.Shape.copy()
        cached = {"nut": h.hex_nut_shape().copy(), "screw": h.screw_shape(6).copy()}
        original_names = {obj.Name for obj in self.doc.Objects}
        for _ in range(2):
            s.attach_to_host(self.kit["group"], self.electronics)
            self.assertTrue(plate.FCPortalInstalled)
            self.assertFalse(any(self.doc.getObject(n) for n in s.FOOT_HARDWARE_NAMES))
            s.attach_to_host(self.kit["group"], self.battery)
            self.assertFalse(plate.FCPortalInstalled)
            self.assertEqual({obj.Name for obj in self.doc.Objects}, original_names)
        for first, second in (
            (original, plate.Shape),
            (cached["nut"], h.hex_nut_shape()),
            (cached["screw"], h.screw_shape(6)),
        ):
            self.assertLess(
                abs(first.cut(second).Volume) + abs(second.cut(first).Volume), 1e-5
            )

    def test_saved_hardware_order_survives_host_roundtrip_and_reopen(self):
        import tempfile
        from pathlib import Path

        from gondola.config import BASELINE_FILE
        from gondola.parts import stack_interface as s
        from gondola.provenance import file_sha256

        source_hash = file_sha256(BASELINE_FILE)
        doc = App.openDocument(str(BASELINE_FILE), hidden=True)
        reopened = None
        try:
            group = doc.OpticalFlowModule
            self.assertEqual(group.StackHostName, "BatteryEquipmentModule")
            expected = [obj.Name for obj in doc.DesignRegistry.HardwareParts]
            feet = set(s.FOOT_HARDWARE_NAMES)
            last_foot = max(
                index for index, name in enumerate(expected) if name in feet
            )
            # The real baseline has other purchased hardware after the optical
            # block; an implementation that merely appends feet must fail here.
            self.assertLess(last_foot, len(expected) - 1)
            for _ in range(2):
                s.attach_to_host(group, doc.ElectronicsEquipmentModule)
                self.assertEqual(
                    [obj.Name for obj in doc.DesignRegistry.HardwareParts],
                    [name for name in expected if name not in feet],
                )
                s.attach_to_host(group, doc.BatteryEquipmentModule)
                actual = [obj.Name for obj in doc.DesignRegistry.HardwareParts]
                self.assertEqual(actual, expected)
                self.assertEqual(len(actual), len(set(actual)))
            with tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "roundtrip.FCStd"
                doc.saveAs(str(path))
                App.closeDocument(doc.Name)
                doc = None
                reopened = App.openDocument(str(path), hidden=True)
                self.assertEqual(
                    [obj.Name for obj in reopened.DesignRegistry.HardwareParts],
                    expected,
                )
                self.assertEqual(
                    reopened.OpticalFlowModule.StackHostName,
                    "BatteryEquipmentModule",
                )
        finally:
            if doc is not None:
                App.closeDocument(doc.Name)
            if reopened is not None:
                App.closeDocument(reopened.Name)
            self.assertEqual(file_sha256(BASELINE_FILE), source_hash)

    def test_straight_top_beam_has_two_open_carbon_attachment_feet(self):
        from gondola.parts import stack_interface as s

        tower = s.tower_shape()
        self.assertEqual(len(tower.Solids), 1)
        for x, y in s.FOOT_CENTRES:
            bore = Part.makeCylinder(
                s.FOOT_HOLE_DIAMETER / 2,
                s.ROOT_ARM_THICKNESS,
                App.Vector(x, y, s.LEG_BOTTOM_Z),
            )
            self.assertLess(tower.common(bore).Volume, 1e-5)
        tower.rotate(App.Vector(), App.Vector(0, 0, 1), -45)
        half = (
            math.hypot(*s.ANCHOR_CENTRES[0]) + s.FIXED_LEG_INNER + s.FIXED_LEG_THICKNESS
        )
        expected = Part.makeBox(
            2 * half,
            s.LEG_WIDTH,
            s.TOP_BEAM_THICKNESS,
            App.Vector(-half, -s.LEG_WIDTH / 2, 0),
        )
        top = tower.common(Part.makeBox(200, 200, 10, App.Vector(-100, -100, 0)))
        self.assertLess(
            abs(top.cut(expected).Volume) + abs(expected.cut(top).Volume), 1e-5
        )
        self.assertEqual(len(self.kit["printed"]), 3)
        self.assertEqual(len(self.kit["hardware"]), 8)

    def test_missing_root_material_is_rejected(self):
        from gondola.parts import stack_interface as s
        from gondola.validation.optical import tower_attachment_check

        base = self.doc.OpticalMountBase
        original = base.Shape.copy()
        try:
            base.Shape = original.cut(
                dict(s.structural_component_shapes())["root_arm_0"]
            )
            self.assertFalse(tower_attachment_check(self.doc, self.battery)["passed"])
        finally:
            base.Shape = original

    def test_missing_bought_host_is_rejected_without_transfer(self):
        from gondola.parts import stack_interface as s

        plate = self.doc.StockFCAdapter
        self.electronics.removeObject(plate)
        try:
            with self.assertRaises(ValueError):
                s.attach_to_host(self.kit["group"], self.electronics)
            self.assertEqual(self.kit["group"].getParentGeoFeatureGroup(), self.battery)
        finally:
            self.electronics.addObject(plate)

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
                    "StockFCAdapter": world_shape(self.doc.StockFCAdapter),
                    "Unknown": Part.makeBox(1, 1, 1),
                },
            )
            self.assertIn("StockFCAdapter", kept)
            self.assertIn("StockBatteryAdapter", kept)
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
        self.assertEqual(self.kit["group"].HostPlateName, "StockBatteryAdapter")


if __name__ == "__main__":
    unittest.main()
