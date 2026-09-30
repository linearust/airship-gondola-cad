"""Actual saved rail checks reject missing support, displaced bolts and bad bindings."""

import json
import unittest
from unittest.mock import patch

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class SavedRailValidationTests(unittest.TestCase):
    def setUp(self):
        from gondola.cad import set_property
        from gondola.parts import equipment_mounts, propulsion, rail

        self.doc = App.newDocument("SavedSideSlotRailTest")
        self.root = self.doc.addObject("App::Part", "Root")
        built = rail.build_rail(self.doc)
        self.root.addObject(built["group"])
        self.root.addObject(self.doc.TapeAttachmentReference)
        coupons = rail.build_coupons(self.doc)
        modules, prints, hardware, mounts = [], list(built["printed"]), [], []
        specs = (
            ("BatteryMount", "BatteryEquipmentModule", "battery", 100, 0, 0),
            (
                "ElectronicsMount",
                "ElectronicsEquipmentModule",
                "electronics",
                -70,
                180,
                0,
            ),
            ("AccessoryMount", "AccessoryEquipmentModule", "accessory", -140, 180, 0),
            ("PropulsionFixedFrame", "MainPropulsionModule", None, -5, 0, 12.5),
        )
        for name, parent, kind, x, yaw, offset in specs:
            module = self.doc.addObject("App::Part", parent)
            self.root.addObject(module)
            module.Placement = App.Placement(
                App.Vector(x, 0, 0), App.Rotation(App.Vector(0, 0, 1), yaw)
            )
            set_property(
                module,
                "RailAttachmentContract",
                json.dumps(
                    rail.attachment_contract(32 if kind is None else 16), sort_keys=True
                ),
            )
            obj = self.doc.addObject("Part::Feature", name)
            module.addObject(obj)
            obj.Shape = (
                equipment_mounts.mount_shape(kind)
                if kind
                else propulsion.fixed_frame_shape()
            )
            hardware.extend(
                rail.build_attachment_hardware(
                    self.doc, module, parent, x_offset=offset
                )
            )
            modules.append(module)
            prints.append(obj)
            if kind:
                mounts.append(obj)
        registry = self.doc.addObject("App::FeaturePython", "DesignRegistry")
        for key, values in (
            ("RailSegments", built["printed"]),
            ("Modules", modules),
            ("PrintedParts", prints + coupons["printed"]),
            ("EquipmentMounts", mounts),
            ("HardwareParts", hardware),
            ("RailLocks", hardware),
            ("TapeReferences", built["tapes"]),
        ):
            registry.addProperty("App::PropertyLinkList", key)
            setattr(registry, key, values)
        self.doc.recompute()
        self.addCleanup(lambda: App.closeDocument(self.doc.Name))

    def check(self):
        from gondola.cad import world_shape
        from gondola.validation.rail_mount import rail_check

        shapes = {
            obj.Name: world_shape(obj)
            for obj in self.doc.Objects
            if hasattr(obj, "Shape")
        }
        return rail_check(self.doc.DesignRegistry, shapes)

    def test_actual_four_mounts_pass_in_common_rigid_frame(self):
        self.root.Placement = App.Placement(
            App.Vector(20, -10, 7), App.Rotation(App.Vector(1, 2, 3), 37)
        )
        self.doc.recompute()
        report = self.check()
        self.assertTrue(report["passed"], report)
        actual = sorted(
            row["attachment_axis_x_mm"]
            for row in report["rails"][0]["installed_mounts"]
        )
        for value, expected in zip(actual, (-140, -70, 7.5, 100)):
            self.assertAlmostEqual(value, expected)

    def test_gap_position_is_rejected_even_without_a_collision(self):
        self.doc.BatteryEquipmentModule.Placement.Base = App.Vector(85, 0, 0)
        report = self.check()
        self.assertFalse(report["passed"])
        row = next(
            row
            for row in report["rails"][0]["installed_mounts"]
            if row["module"] == "BatteryEquipmentModule"
        )
        self.assertFalse(row["supported_slot_position"]["passed"])

    def test_propulsion_origin_is_distinct_from_its_attachment_axis(self):
        self.doc.MainPropulsionModule.Placement.Base = App.Vector(0, 0, 0)
        report = self.check()
        row = next(
            row
            for row in report["rails"][0]["installed_mounts"]
            if row["module"] == "MainPropulsionModule"
        )
        self.assertAlmostEqual(row["attachment_axis_x_mm"], 12.5)
        self.assertFalse(row["passed"])

    def test_shifted_saved_bolt_and_wrong_sku_are_rejected(self):
        obj = self.doc.BatteryEquipmentModuleRailMountScrew
        obj.Placement.Base = App.Vector(0.1, 0, 0)
        report = self.check()
        self.assertFalse(report["passed"])
        obj.Placement.Base = App.Vector()
        obj.HardwareSKU = "M2X6_BUTTON_HEAD"
        self.assertFalse(self.check()["passed"])

    def test_independently_displaced_print_is_rejected(self):
        self.doc.BatteryMount.Placement.Base = App.Vector(0, 0, 1)
        report = self.check()
        self.assertFalse(report["passed"])
        row = next(
            row
            for row in report["saved_integral_mounts"]
            if row["part"] == "BatteryMount"
        )
        self.assertFalse(row["part_local_placement_identity"])

    def test_missing_hardware_registry_entry_is_rejected(self):
        registry = self.doc.DesignRegistry
        registry.RailLocks = list(registry.RailLocks)[1:]
        self.assertFalse(self.check()["passed"])

    def test_base_puncture_between_attachment_axes_is_rejected(self):
        obj = self.doc.ContinuousRail
        obj.Shape = obj.Shape.cut(Part.makeCylinder(0.3, 2, App.Vector(25, 0, -0.1)))
        report = self.check()
        self.assertFalse(report["passed"])
        self.assertGreater(report["rails"][0]["missing_unbroken_base_witness_mm3"], 0.4)

    def test_filled_waist_is_rejected_even_if_generator_has_the_same_defect(self):
        obj = self.doc.ContinuousRail
        obj.Shape = obj.Shape.fuse(
            Part.makeBox(8, 6, 1.5, App.Vector(51, -3, 0))
        ).removeSplitter()
        with patch(
            "gondola.validation.rail_mount.rail.rail_shape", return_value=obj.Shape
        ):
            report = self.check()
        self.assertFalse(report["passed"])
        row = report["rails"][0]
        self.assertLess(row["source_comparison"]["difference_mm3"], 1e-5)
        self.assertGreater(row["filled_flexure_relief_mm3"], 8.9)
        self.assertAlmostEqual(row["missing_unbroken_base_witness_mm3"], 0, places=6)

    def test_missing_unused_wall_is_rejected_independently_of_generator(self):
        obj = self.doc.ContinuousRail
        obj.Shape = obj.Shape.cut(Part.makeBox(20, 2.5, 8, App.Vector(31, -1.25, 1.5)))
        with patch(
            "gondola.validation.rail_mount.rail.rail_shape", return_value=obj.Shape
        ):
            report = self.check()
        row = report["rails"][0]
        self.assertFalse(report["passed"])
        self.assertLess(row["source_comparison"]["difference_mm3"], 1e-5)
        self.assertFalse(row["independent_wall_top_sections"]["passed"])
        self.assertTrue(all(mount["passed"] for mount in row["installed_mounts"]))

    def test_thinned_waist_is_rejected_even_if_generator_has_the_same_defect(self):
        obj = self.doc.ContinuousRail
        obj.Shape = obj.Shape.cut(
            Part.makeBox(1, 4.5, 0.2, App.Vector(54.5, -2.25, 1.3))
        )
        with patch(
            "gondola.validation.rail_mount.rail.rail_shape", return_value=obj.Shape
        ):
            report = self.check()
        self.assertFalse(report["passed"])
        row = report["rails"][0]
        self.assertLess(row["source_comparison"]["difference_mm3"], 1e-5)
        self.assertGreater(row["missing_unbroken_base_witness_mm3"], 0.89)
        self.assertAlmostEqual(row["filled_flexure_relief_mm3"], 0, places=6)

    def test_long_propulsion_foot_cannot_claim_the_short_carrier_travel(self):
        from gondola.parts import rail

        self.doc.MainPropulsionModule.RailAttachmentContract = json.dumps(
            rail.attachment_contract(16)
        )
        report = self.check()
        self.assertFalse(report["passed"])
        row = next(
            row
            for row in report["native_attachment_annotations"]
            if row["object"] == "MainPropulsionModule"
        )
        self.assertFalse(row["matches_current_attachment_contract"])

    def test_saved_contract_and_tape_inventory_are_not_inferred(self):
        self.doc.MountFitSample.RailAttachmentContract = "{}"
        self.assertFalse(self.check()["passed"])
        from gondola.parts import rail

        self.doc.MountFitSample.RailAttachmentContract = json.dumps(
            rail.attachment_contract(length=50)
        )
        self.assertTrue(self.check()["passed"])
        tapes = list(self.doc.DesignRegistry.TapeReferences)
        self.doc.DesignRegistry.TapeReferences = tapes[:-1]
        self.assertFalse(self.check()["passed"])

    def test_coupon_cannot_claim_full_rail_adjustment_ranges(self):
        from gondola.parts import rail

        for name in ("RailFitSample", "MountFitSample"):
            with self.subTest(coupon=name):
                obj = self.doc.getObject(name)
                original = obj.RailAttachmentContract
                obj.RailAttachmentContract = json.dumps(rail.attachment_contract())
                report = self.check()
                self.assertFalse(report["passed"])
                row = next(
                    row
                    for row in report["native_attachment_annotations"]
                    if row["object"] == name
                )
                self.assertFalse(row["matches_current_attachment_contract"])
                obj.RailAttachmentContract = original


if __name__ == "__main__":
    unittest.main()
