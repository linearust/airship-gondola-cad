"""Native integration checks for interchangeable integral optical towers."""

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
            stack_interface,
        )

        cls.doc = App.newDocument("StructuralStackRegression")
        cls.battery = cls.doc.addObject("App::Part", "BatteryEquipmentModule")
        cls.electronics = cls.doc.addObject("App::Part", "ElectronicsEquipmentModule")
        cls.battery.Placement.Base.x = -90
        cls.electronics.Placement.Base.x = 90
        for host, kind in ((cls.battery, "battery"), (cls.electronics, "electronics")):
            equipment_mounts.build_mount(cls.doc, host, kind)
        equipment_envelopes.build_equipment(cls.doc, cls.battery, cls.electronics)
        kit = optical_mount.build_optical_mount(cls.doc, cls.battery)
        kit["hardware"] += stack_interface.build_stack_hardware(cls.doc, kit["group"])
        refs, reserves = optical_sensor.build_sensor(cls.doc, kit["pitch_stage"])
        cls.kit = kit
        cls.moving = kit["printed"] + kit["hardware"] + refs + reserves
        cls.doc.recompute()

    @classmethod
    def tearDownClass(cls):
        App.closeDocument(cls.doc.Name)

    def setUp(self):
        from gondola.parts import optical_mount, stack_interface

        stack_interface.attach_to_host(self.kit["group"], self.battery)
        optical_mount.set_angles(self.doc, 0, 0)

    def test_complete_kit_reparents_and_both_integral_feet_bear_on_each_host(self):
        from gondola.parts import stack_interface
        from gondola.validation.optical import tower_attachment_check

        before = {obj.Name: obj.getGlobalPlacement().Base for obj in self.moving}
        for host, dx in ((self.electronics, 180), (self.battery, 0)):
            stack_interface.attach_to_host(self.kit["group"], host)
            self.assertEqual(self.kit["group"].StackHostName, host.Name)
            self.assertEqual(self.kit["group"].getParentGeoFeatureGroup(), host)
            for obj in self.moving:
                delta = obj.getGlobalPlacement().Base - before[obj.Name]
                self.assertLess((delta - App.Vector(dx, 0, 0)).Length, 1e-7)
            result = tower_attachment_check(self.doc, host)
            self.assertTrue(result["passed"], result)
            self.assertEqual(len(result["nominal_through_joints"]), 2)
            self.assertEqual(len(result["local_hole_spacing_mismatch"]), 6)

    def test_source_foot_support_detects_a_cut_away_foot(self):
        from gondola.parts import stack_interface
        from gondola.validation.optical import tower_attachment_check

        base = self.doc.OpticalMountBase
        original = base.Shape.copy()
        x, y = stack_interface.HOLE_CENTRES[0]
        try:
            base.Shape = base.Shape.cut(
                Part.makeCylinder(4, 2, App.Vector(x, y, -stack_interface.TOWER_HEIGHT))
            )
            self.assertFalse(tower_attachment_check(self.doc, self.battery)["passed"])
        finally:
            base.Shape = original

    def test_complete_tower_leaves_for_device_service(self):
        from gondola.parts.stack_interface import is_removable_head_part

        group = self.kit["group"]
        self.assertEqual(
            {obj.Name for obj in self.moving if not is_removable_head_part(obj, group)},
            {"OpticalStackFootBolt0", "OpticalStackFootBolt1"},
        )
        self.assertFalse(is_removable_head_part(self.doc.BatteryMount, group))
        self.assertFalse(is_removable_head_part(self.doc.ModuleFCEnvelope, group))
        names = {obj.Name for obj in self.kit["hardware"]}
        self.assertFalse(any("Spacer" in name or "UpperBolt" in name for name in names))

    def test_two_through_pairs_use_full_nuts_and_have_length_margin(self):
        from gondola.cad import world_shape
        from gondola.contracts import fasteners

        feet = [
            obj
            for obj in self.kit["hardware"]
            if getattr(obj, "StackEnd", "") == "Foot"
        ]
        self.assertEqual(len(feet), 4)
        for index in range(2):
            bolt = self.doc.getObject(f"OpticalStackFootBolt{index}")
            nut = self.doc.getObject(f"OpticalStackFootNut{index}")
            self.assertEqual(bolt.HardwareSKU, "M2X8_BUTTON_HEAD")
            self.assertEqual(nut.HardwareSKU, "M2_HEX_NUT")
            self.assertEqual(bolt.MaterialSelection, fasteners.KIT_MATERIAL)
            tip = world_shape(bolt).BoundBox.ZMax
            nut_end = world_shape(nut).BoundBox.ZMax
            self.assertAlmostEqual(tip - nut_end, 2.4, places=7)
            self.assertGreater(tip - nut_end - 0.6, 1.5)

    def test_both_hosts_have_clear_upper_nut_release(self):
        from gondola.cad import world_shape
        from gondola.parts import stack_interface
        from gondola.validation.geometry import translation_sweep

        for host in (self.battery, self.electronics):
            stack_interface.attach_to_host(self.kit["group"], host)
            obstacles = [
                host_obj
                for host_obj in self.doc.Objects
                if host_obj.TypeId != "App::Part"
                and hasattr(host_obj, "Shape")
                and not host_obj.Shape.isNull()
                and host_obj not in self.kit["hardware"]
                and host_obj.Name
                not in ("MTF02POpticalClearanceReserve", "MTF02PConnectorReserve")
            ]
            for index in range(2):
                for kind, delta in (("Nut", (0, 0, 4)),):
                    obj = self.doc.getObject(f"OpticalStackFoot{kind}{index}")
                    sweep, _ = translation_sweep(world_shape(obj), delta)
                    for obstacle in obstacles:
                        self.assertLess(
                            abs(sweep.common(world_shape(obstacle)).Volume),
                            1e-5,
                            (host.Name, obj.Name, obstacle.Name),
                        )

    def test_tower_removal_and_nut_holding_access_reject_blockers(self):
        from gondola.cad import world_shape
        from gondola.validation.optical import _tower_service_check

        fixed = {
            "BatteryMount": world_shape(self.doc.BatteryMount),
            "ModuleBatteryEnvelope": world_shape(self.doc.ModuleBatteryEnvelope),
        }
        physical_kit = (
            self.kit["printed"] + self.kit["hardware"] + [self.doc.ModuleMTF02PEnvelope]
        )
        self.assertTrue(_tower_service_check(self.doc, fixed, physical_kit)["passed"])
        nut = world_shape(self.doc.OpticalStackFootNut0).BoundBox
        flank = Part.makeSphere(
            0.2,
            App.Vector(
                (nut.XMin + nut.XMax) / 2 + 2.8,
                (nut.YMin + nut.YMax) / 2,
                (nut.ZMin + nut.ZMax) / 2,
            ),
        )
        blocked = _tower_service_check(
            self.doc, {**fixed, "NutFlankBlocker": flank}, physical_kit
        )
        row = next(
            row
            for row in blocked["foot_fastener_release"]
            if row["object"] == "OpticalStackFootNut0"
        )
        self.assertFalse(row["passed"])
        self.assertEqual(
            row["axial_tool_reservation_collisions"][0]["object"], "NutFlankBlocker"
        )
        leg = self.kit["group"].getGlobalPlacement().multVec(App.Vector(26, 26, 3))
        blocked = _tower_service_check(
            self.doc,
            {**fixed, "TowerLiftBlocker": Part.makeSphere(0.2, leg)},
            physical_kit,
        )
        base = next(
            row
            for row in blocked["whole_tower_lift"]
            if row["object"] == "OpticalMountBase"
        )
        self.assertFalse(base["passed"])
        self.assertEqual(base["collisions"][0]["object"], "TowerLiftBlocker")
        self.assertLess(base["actual_shape_outside_service_envelope_mm3"], 1e-5)

    def test_unsupported_host_is_rejected_without_moving_the_kit(self):
        from gondola.parts import stack_interface

        unknown = self.doc.addObject("App::Part", "UnsupportedHost")
        try:
            with self.assertRaises(ValueError):
                stack_interface.attach_to_host(self.kit["group"], unknown)
            self.assertEqual(self.kit["group"].getParentGeoFeatureGroup(), self.battery)
        finally:
            self.doc.removeObject(unknown.Name)


if __name__ == "__main__":
    unittest.main()
