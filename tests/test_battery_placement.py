"""Native regressions for the declared pack placement and shared-platform optical bracket gap."""

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
            instrument_mount,
            optical_mount,
        )

        cls.doc = App.newDocument("BatteryPlacementRegression")
        cls.host = cls.doc.addObject("App::Part", "BatteryEquipmentModule")
        cls.host.Placement.Base.x = 90
        electronics = cls.doc.addObject("App::Part", "ElectronicsEquipmentModule")
        electronics.Placement = App.Placement(
            App.Vector(-82, 0, 0), App.Rotation(App.Vector(0, 0, 1), 180)
        )
        accessory = cls.doc.addObject("App::Part", "AccessoryEquipmentModule")
        accessory.Placement.Base.x = -140
        mount = equipment_mounts.build_mount(cls.doc, cls.host, "battery")
        instrument = instrument_mount.build_mount(cls.doc, electronics)
        stage = instrument["pitch_stage"]
        references, _ = equipment_envelopes.build_equipment(
            cls.doc, cls.host, stage, accessory
        )
        optical = optical_mount.build_optical_mount(cls.doc, stage)
        cls.battery = cls.doc.ModuleBatteryEnvelope
        cls.objects = [mount, *instrument["printed"], *optical["printed"], *references]
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
        floats = result["continuous_translation"]["tower_clamped_registration_gaps"]
        self.assertEqual(
            {row["component"] for row in floats},
            {
                "OpticalFootLeft",
                "OpticalFootRight",
                "OpticalFootRearBridge",
                "OpticalLeftSupport",
                "OpticalRightSupport",
                "OpticalCrossbar",
                "OpticalAdhesivePad",
            },
        )
        self.assertTrue(all(row["passed"] for row in floats), floats)
        self.assertEqual(
            result["continuous_translation"]["local_size_mm"], [28, 74, 17]
        )
        self.assertEqual(
            {
                row["object"]
                for row in result["continuous_translation"]["stack_tower_gaps"]
            },
            {"OpticalSensorTray"},
        )
        self.assertGreater(
            min(
                row["minimum_gap_mm"]
                for row in result["continuous_translation"]["stack_tower_gaps"]
            ),
            1.5,
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
        obstacle.Placement.Base = App.Vector(
            -0.5, -0.5, self.battery.Shape.BoundBox.ZMin + 0.5
        )
        self.doc.recompute()
        try:
            result = self.check(self.objects + [obstacle])
            self.assertFalse(result["passed"])
            self.assertIn(obstacle.Name, result["continuous_translation"]["collisions"])
        finally:
            self.doc.removeObject(obstacle.Name)
            self.doc.recompute()

    def test_tower_gap_fails_before_geometric_contact(self):
        tower = self.doc.OpticalSensorTray
        group = self.doc.OpticalFlowModule
        before = App.Placement(group.Placement)
        # Use the actual closest-point direction to preserve a positive gap
        # while making the separate minimum-clearance policy fail.
        import Part

        from gondola.cad import world_shape
        from gondola.parts import equipment_mounts

        sweep = Part.makeBox(
            28, 74, 17, App.Vector(-14, -37, equipment_mounts.SUPPORT_FACE_Z + 1)
        )
        sweep.Placement = self.host.getGlobalPlacement().multiply(sweep.Placement)
        gap, pairs, _ = world_shape(tower).distToShape(sweep)
        direction = pairs[0][1] - pairs[0][0]
        direction.normalize()
        parent_rotation = group.getParentGeoFeatureGroup().getGlobalPlacement().Rotation
        group.Placement.Base += parent_rotation.inverted().multVec(
            direction * (gap - 0.5)
        )
        self.doc.recompute()
        try:
            result = self.check()
            self.assertTrue(all(row["passed"] for row in result["cases"]))
            self.assertFalse(result["passed"])
            continuous = result["continuous_translation"]
            self.assertEqual(continuous["collisions"], [])
            gap = continuous["stack_tower_gaps"][0]["minimum_gap_mm"]
            self.assertGreater(gap, 0)
            self.assertLess(gap, continuous["required_stack_tower_gap_mm"])
        finally:
            group.Placement = before
            self.doc.recompute()

    def test_nominal_gap_does_not_replace_registration_clearance(self):
        import Part

        from gondola.cad import world_shape
        from gondola.parts import equipment_mounts

        tower = self.doc.OpticalSensorTray
        group = self.doc.OpticalFlowModule
        original = group.Placement.copy()
        sweep = Part.makeBox(
            28, 74, 17, App.Vector(-14, -37, equipment_mounts.SUPPORT_FACE_Z + 1)
        )
        sweep.Placement = self.host.getGlobalPlacement().multiply(sweep.Placement)
        gap, pairs, _ = world_shape(tower).distToShape(sweep)
        direction = pairs[0][1] - pairs[0][0]
        direction.normalize()
        try:
            parent_rotation = (
                group.getParentGeoFeatureGroup().getGlobalPlacement().Rotation
            )
            group.Placement.Base += parent_rotation.inverted().multVec(
                direction * (gap - 2)
            )
            self.doc.recompute()
            result = self.check()
            continuous = result["continuous_translation"]
            self.assertAlmostEqual(
                continuous["stack_tower_gaps"][0]["minimum_gap_mm"], 2
            )
            self.assertEqual(continuous["collisions"], [])
            self.assertFalse(
                all(
                    row["passed"]
                    for row in continuous["tower_clamped_registration_gaps"]
                )
            )
            self.assertFalse(result["passed"])
        finally:
            group.Placement = original
            self.doc.recompute()

    def test_missing_tower_cannot_pass_clearance_check(self):
        result = self.check(
            [obj for obj in self.objects if obj.Name != "OpticalSensorTray"]
        )
        self.assertFalse(result["passed"])
        self.assertEqual(result["continuous_translation"]["stack_tower_gaps"], [])
