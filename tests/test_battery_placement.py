"""Native regressions for the declared pack placement and removable portal gap."""

import json
import unittest

try:
    import FreeCAD as App
except ImportError:
    App = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class BatteryPlacementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.parts import (
            equipment_envelopes,
            equipment_mounts,
            optical_mount,
            stock_adapter,
        )

        cls.doc = App.newDocument("BatteryPlacementRegression")
        cls.host = cls.doc.addObject("App::Part", "BatteryEquipmentModule")
        cls.host.Placement.Base.x = -90
        electronics = cls.doc.addObject("App::Part", "ElectronicsEquipmentModule")
        electronics.Placement.Base.x = 90
        accessory = cls.doc.addObject("App::Part", "AccessoryEquipmentModule")
        accessory.Placement.Base.x = 180
        mount = equipment_mounts.build_mount(cls.doc, cls.host, "battery")
        stock_adapter.build_stock_adapter(cls.doc, electronics, "electronics")
        references, _ = equipment_envelopes.build_equipment(
            cls.doc, cls.host, electronics, accessory
        )
        kit = optical_mount.build_optical_mount(cls.doc, cls.host)
        cls.battery = cls.doc.ModuleBatteryEnvelope
        cls.objects = [mount, *references, *kit["printed"], *kit["hardware"]]
        cls.doc.recompute()

    @classmethod
    def tearDownClass(cls):
        App.closeDocument(cls.doc.Name)

    def check(self, objects=None):
        from gondola.validation.assembly import battery_check

        return battery_check(self.doc, self.objects if objects is None else objects)

    def test_declared_rectangle_and_continuous_envelope_clears_complete_tower(self):
        before = tuple(
            getattr(self.battery, field).Value
            for field in ("Length", "Width", "Height", "CentreX", "CentreY")
        )
        result = self.check()
        self.assertTrue(result["passed"], result)
        self.assertEqual(len(result["cases"]), 18)
        components = result["continuous_translation"]["fixed_portal_components"]
        self.assertEqual(len(components), 6)
        self.assertTrue(all(row["passed"] for row in components), components)
        self.assertEqual(
            result["continuous_translation"]["local_size_mm"], [20, 68, 17]
        )
        self.assertGreater(
            result["continuous_translation"]["fixed_portal_minimum_gap_mm"], 1.5
        )
        self.assertEqual(
            before,
            tuple(
                getattr(self.battery, field).Value
                for field in ("Length", "Width", "Height", "CentreX", "CentreY")
            ),
        )

    def test_saved_unsupported_offset_is_rejected_and_restored(self):
        self.battery.CentreX = 10
        self.doc.recompute()
        try:
            result = self.check()
            self.assertFalse(result["passed"])
            self.assertFalse(result["saved_placement"]["within_declared_centre_limits"])
            self.assertTrue(all(row["passed"] for row in result["cases"]))
            self.assertEqual(self.battery.CentreX.Value, 10)
        finally:
            self.battery.CentreX = 0
            self.doc.recompute()

    def test_native_contract_cannot_silently_expand_the_supported_range(self):
        before = self.battery.BatteryPlacementContract
        contract = json.loads(before)
        contract["centre_x_limit_mm"] = 10
        self.battery.BatteryPlacementContract = json.dumps(contract)
        try:
            result = self.check()
            self.assertFalse(result["passed"])
            self.assertFalse(result["saved_placement"]["native_contract_matches"])
        finally:
            self.battery.BatteryPlacementContract = before

    def test_interior_obstacle_is_reported_by_continuous_sweep(self):
        obstacle = self.doc.addObject("Part::Box", "BatteryInteriorBlocker")
        self.host.addObject(obstacle)
        obstacle.Length = obstacle.Width = obstacle.Height = 1
        obstacle.Placement.Base = App.Vector(-0.5, -0.5, 15)
        self.doc.recompute()
        try:
            result = self.check(self.objects + [obstacle])
            self.assertFalse(result["passed"])
            self.assertIn(obstacle.Name, result["continuous_translation"]["collisions"])
        finally:
            self.doc.removeObject(obstacle.Name)
            self.doc.recompute()

    def test_tower_gap_fails_before_geometric_contact(self):
        from unittest.mock import patch

        from gondola.parts import optical_mount, stack_interface

        # A narrower candidate portal remains separate from every pack pose but
        # loses the promised1.5mm continuous edge margin. No collision bypass.
        original = self.doc.OpticalMountBase.Shape.copy()
        try:
            with patch.object(
                stack_interface, "ANCHOR_CENTRES", ((-15, -15), (15, 15))
            ):
                self.doc.OpticalMountBase.Shape = optical_mount.base_shape()
                self.doc.recompute()
                result = self.check()
                continuous = result["continuous_translation"]
                self.assertEqual(continuous["collisions"], [])
                self.assertGreater(continuous["fixed_portal_minimum_gap_mm"], 0)
                self.assertLess(
                    continuous["fixed_portal_minimum_gap_mm"],
                    continuous["required_stack_tower_gap_mm"],
                )
                self.assertTrue(continuous["fixed_portal_present"])
                self.assertFalse(result["passed"])
        finally:
            self.doc.OpticalMountBase.Shape = original
            self.doc.recompute()

    def test_assembly_inventory_reacquires_live_feet_after_host_roundtrip(self):
        from gondola.parts import optical_mount, stack_interface, stock_adapter
        from gondola.validation.assembly import _physical_objects

        doc = App.newDocument("PhysicalInventoryRoundTrip")
        try:
            battery = doc.addObject("App::Part", "BatteryEquipmentModule")
            electronics = doc.addObject("App::Part", "ElectronicsEquipmentModule")
            hardware = stock_adapter.build_stock_adapter(doc, battery, "battery")[
                "hardware"
            ]
            hardware += stock_adapter.build_stock_adapter(
                doc, electronics, "electronics"
            )["hardware"]
            kit = optical_mount.build_optical_mount(doc, battery)
            registry = doc.addObject("App::FeaturePython", "DesignRegistry")
            for name, values in (
                ("PrintedParts", kit["printed"]),
                ("HardwareParts", hardware + kit["hardware"]),
                ("ReferenceParts", []),
                ("TapeReferences", []),
            ):
                registry.addProperty("App::PropertyLinkList", name)
                setattr(registry, name, values)
            doc.recompute()
            before = {obj.Name for obj in _physical_objects(registry)}
            stack_interface.attach_to_host(kit["group"], electronics)
            without_feet = {obj.Name for obj in _physical_objects(registry)}
            self.assertEqual(
                before - without_feet, set(stack_interface.FOOT_HARDWARE_NAMES)
            )
            stack_interface.attach_to_host(kit["group"], battery)
            after = _physical_objects(registry)
            self.assertEqual({obj.Name for obj in after}, before)
            self.assertEqual(len(after), len(before))
            self.assertTrue(
                all(
                    obj is doc.getObject(obj.Name) and obj.Shape.Volume > 0
                    for obj in after
                )
            )
        finally:
            App.closeDocument(doc.Name)

    def test_missing_fixed_portal_cannot_pass_clearance_check(self):
        result = self.check(
            [obj for obj in self.objects if obj.Name != "OpticalMountBase"]
        )
        self.assertFalse(result["passed"])
