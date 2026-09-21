"""Native integration checks for interchangeable bought-spacer optical stacks."""

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

    def test_complete_kit_reparents_and_both_spacer_ends_bear_on_each_host(self):
        from gondola.cad import world_shape
        from gondola.parts import stack_interface

        before = {obj.Name: obj.getGlobalPlacement().Base for obj in self.moving}
        for host, dx in ((self.electronics, 180), (self.battery, 0)):
            stack_interface.attach_to_host(self.kit["group"], host)
            self.assertEqual(self.kit["group"].StackHostName, host.Name)
            self.assertEqual(self.kit["group"].getParentGeoFeatureGroup(), host)
            for obj in self.moving:
                delta = obj.getGlobalPlacement().Base - before[obj.Name]
                self.assertLess((delta - App.Vector(dx, 0, 0)).Length, 1e-7)
            carrier = self.doc.getObject(stack_interface.SUPPORTED_HOSTS[host.Name])
            for obj in self.kit["hardware"]:
                if str(getattr(obj, "StackEnd", "")) != "Spacer":
                    continue
                for support in (carrier, self.doc.OpticalMountBase):
                    first, second = world_shape(obj), world_shape(support)
                    self.assertLess(first.distToShape(second)[0], 1e-7)
                    self.assertLess(abs(first.common(second).Volume), 1e-6)

    def test_fc_lifts_past_retained_columns_using_its_actual_rotated_footprint(self):
        from gondola.cad import world_shape
        from gondola.parts import stack_interface
        from gondola.validation.geometry import translation_sweep

        stack_interface.attach_to_host(self.kit["group"], self.electronics)
        body = world_shape(self.doc.ModuleFCEnvelope)
        sweep, method = translation_sweep(body, (0, 0, 32))
        self.assertIn("face-prism", method)
        bounds = body.BoundBox
        false_box = Part.makeBox(
            bounds.XLength,
            bounds.YLength,
            bounds.ZLength + 32,
            App.Vector(bounds.XMin, bounds.YMin, bounds.ZMin),
        )
        for obj in self.kit["hardware"]:
            if str(getattr(obj, "StackEnd", "")) != "Spacer":
                continue
            column = world_shape(obj)
            self.assertLess(abs(sweep.common(column).Volume), 1e-6)
            self.assertGreater(sweep.distToShape(column)[0], 8)
            self.assertGreater(abs(false_box.common(column).Volume), 200)

    def test_head_removal_keeps_columns_and_lower_screws_only(self):
        from gondola.parts.stack_interface import is_removable_head_part

        group = self.kit["group"]
        retained = {
            obj.Name for obj in self.moving if not is_removable_head_part(obj, group)
        }
        self.assertEqual(
            retained,
            {
                "OpticalStackSpacer0",
                "OpticalStackSpacer1",
                "OpticalStackLowerBolt0",
                "OpticalStackLowerBolt1",
            },
        )
        self.assertTrue(is_removable_head_part(self.doc.OpticalPitchNut, group))
        self.assertTrue(is_removable_head_part(self.doc.ModuleMTF02PEnvelope, group))
        self.assertFalse(is_removable_head_part(self.doc.BatteryMount, group))
        self.assertFalse(is_removable_head_part(self.doc.ModuleFCEnvelope, group))

    def test_stock_nylon_skus_reject_wrong_material(self):
        from gondola.parts import purchased_hardware

        for sku, shape in (
            ("M2X5_PA66_PAN_HEAD", purchased_hardware.stack_screw_shape()),
            ("M2_FF_PA66_AF4_L25", purchased_hardware.spacer_shape()),
        ):
            for wrong in ("A2 stainless steel", "PA12", "Nylon PA6"):
                with (
                    self.subTest(sku=sku, material=wrong),
                    self.assertRaises(ValueError),
                ):
                    purchased_hardware.add_hardware(
                        self.doc,
                        self.kit["group"],
                        "WrongMaterial",
                        "Wrong",
                        shape,
                        sku,
                        "Test",
                        "Test",
                        wrong,
                    )

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
