"""Native regressions for the declared pack placement and stock column gap."""

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
        from gondola.parts import equipment_envelopes, equipment_mounts, stack_interface

        cls.doc = App.newDocument("BatteryPlacementRegression")
        cls.host = cls.doc.addObject("App::Part", "BatteryEquipmentModule")
        cls.host.Placement.Base.x = -90
        electronics = cls.doc.addObject("App::Part", "ElectronicsEquipmentModule")
        electronics.Placement.Base.x = 90
        mount = equipment_mounts.build_mount(cls.doc, cls.host, "battery")
        references, _ = equipment_envelopes.build_equipment(
            cls.doc, cls.host, electronics
        )
        stack = cls.doc.addObject("App::Part", "OpticalFlowModule")
        stack_interface.attach_to_host(stack, cls.host)
        hardware = stack_interface.build_stack_hardware(cls.doc, stack)
        cls.column_centres = stack_interface.HOLE_CENTRES
        cls.battery = cls.doc.ModuleBatteryEnvelope
        cls.objects = [mount, *references, *hardware]
        cls.doc.recompute()

    @classmethod
    def tearDownClass(cls):
        App.closeDocument(cls.doc.Name)

    def check(self, objects=None):
        from gondola.validation.assembly import battery_check

        return battery_check(self.doc, self.objects if objects is None else objects)

    def test_declared_rectangle_and_continuous_envelope_clear_all_columns(self):
        before = tuple(
            getattr(self.battery, field).Value
            for field in ("Length", "Width", "Height", "CentreX", "CentreY")
        )
        result = self.check()
        self.assertTrue(result["passed"], result)
        self.assertEqual(len(result["cases"]), 18)
        self.assertEqual(
            result["continuous_translation"]["local_size_mm"], [28, 74, 17]
        )
        self.assertEqual(
            {
                row["object"]
                for row in result["continuous_translation"]["stack_column_gaps"]
            },
            {f"OpticalStackSpacer{index}" for index in range(len(self.column_centres))},
        )
        self.assertGreater(
            min(
                row["minimum_gap_mm"]
                for row in result["continuous_translation"]["stack_column_gaps"]
            ),
            3.6,
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

    def test_column_gap_fails_before_geometric_contact(self):
        spacer = self.doc.OpticalStackSpacer0
        before = App.Placement(spacer.Placement)
        # Move the wider stack's left column into the required margin, while
        # keeping its solid clear of every permitted battery placement.
        spacer.Placement.Base.x += 5
        self.doc.recompute()
        try:
            result = self.check()
            self.assertTrue(all(row["passed"] for row in result["cases"]))
            self.assertFalse(result["passed"])
            continuous = result["continuous_translation"]
            self.assertEqual(continuous["collisions"], [])
            gap = next(
                row["minimum_gap_mm"]
                for row in continuous["stack_column_gaps"]
                if row["object"] == spacer.Name
            )
            self.assertGreater(gap, 0)
            self.assertLess(gap, continuous["required_stack_column_gap_mm"])
        finally:
            spacer.Placement = before
            self.doc.recompute()
