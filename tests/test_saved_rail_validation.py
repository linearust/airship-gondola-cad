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
        from gondola.parts import equipment_mounts, propulsion, rail, servo_bridge

        self.doc = App.newDocument("SavedSideSlotRailTest")
        self.root = self.doc.addObject("App::Part", "Root")
        built = rail.build_rail(self.doc)
        self.root.addObject(built["group"])
        self.root.addObject(self.doc.TapeAttachmentReference)
        coupons = rail.build_coupons(self.doc)
        modules, prints, hardware, mounts = [], list(built["printed"]), [], []
        specs = (
            ("BatteryMount", "BatteryEquipmentModule", "battery", 84, 0, 0),
            (
                "ElectronicsMount",
                "ElectronicsEquipmentModule",
                "electronics",
                -56,
                180,
                0,
            ),
            ("AccessoryMount", "AccessoryEquipmentModule", "accessory", -140, 180, 0),
            ("PropulsionFixedFrame", "MainPropulsionModule", None, 14.0, 0, 14.0),
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
                    rail.attachment_contract(
                        38 if kind is None else 16, shared_drive=kind is None
                    ),
                    sort_keys=True,
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
                    self.doc, module, parent, x_offset=offset, shared_drive=kind is None
                )
            )
            if kind is None:
                bridge = self.doc.addObject("Part::Feature", "ServoDriveBridge")
                module.addObject(bridge)
                bridge.Shape = servo_bridge.bridge_shape()
                prints.append(bridge)
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

    def test_actual_five_attachments_pass_in_common_rigid_frame(self):
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
        self.assertEqual(len(actual), 5)
        for value, expected in zip(actual, (-140, -56, 0, 28, 84)):
            self.assertAlmostEqual(value, expected)

    def test_paired_trim_extremes_preserve_real_seats_and_both_clamp_zones(self):
        for position in (11, 17):
            with self.subTest(position=position):
                self.doc.MainPropulsionModule.Placement.Base.x = position
                self.doc.recompute()
                report = self.check()
                self.assertTrue(report["passed"], report)
                shared = [
                    row
                    for row in report["rails"][0]["installed_mounts"]
                    if row["shared_servo_bridge_clamp"]
                ]
                self.assertEqual(len(shared), 2)
                for row in shared:
                    self.assertAlmostEqual(
                        row["paired_spine_support"]["wall_overlap_length_total_mm"], 20
                    )
                    self.assertEqual(
                        row["saved_lower_mount_attachment"][
                            "checked_centred_contact_length_mm"
                        ],
                        10,
                    )
        self.doc.MainPropulsionModule.Placement.Base.x = 17.01
        self.assertFalse(self.check()["passed"])

    def test_gap_position_is_rejected_even_without_a_collision(self):
        self.doc.BatteryEquipmentModule.Placement.Base = App.Vector(98, 0, 0)
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
        self.assertAlmostEqual(row["attachment_axis_x_mm"], 14.0)
        self.assertFalse(row["passed"])

    def test_missing_opposite_pair_cannot_pass_as_a_single_propulsion_clamp(self):
        for suffix in ("RailMountScrew", "RailMountNut"):
            self.doc.removeObject("MainPropulsionModuleOpposite" + suffix)
        self.doc.recompute()
        report = self.check()
        self.assertFalse(report["passed"])
        self.assertFalse(report["rail_lock_inventory_matches"])
        rows = [
            row
            for row in report["rails"][0]["installed_mounts"]
            if row["module"] == "MainPropulsionModule"
        ]
        self.assertEqual(len(rows), 2)
        self.assertTrue(rows[0]["passed"], rows[0])
        self.assertFalse(rows[1]["passed"])
        self.assertTrue(
            all(not item["passed"] for item in rows[1]["installed_hardware"])
        )

    def test_opposite_foot_requires_its_own_complete_rail_support(self):
        obj = self.doc.ContinuousRail
        obj.Shape = obj.Shape.cut(Part.makeBox(20, 2.5, 8, App.Vector(-10, -1.25, 1.5)))
        with patch(
            "gondola.validation.rail_mount.rail.rail_shape", return_value=obj.Shape
        ):
            report = self.check()
        rows = [
            row
            for row in report["rails"][0]["installed_mounts"]
            if row["module"] == "MainPropulsionModule"
        ]
        self.assertTrue(rows[0]["saved_lower_mount_attachment"]["passed"], rows[0])
        self.assertFalse(rows[1]["saved_lower_mount_attachment"]["passed"])
        self.assertTrue(all(not row["paired_spine_support"]["passed"] for row in rows))
        self.assertTrue(all(not row["passed"] for row in rows))

    def test_opposite_leg_defect_is_rejected_even_if_source_has_same_defect(self):
        frame = self.doc.PropulsionFixedFrame
        frame.Shape = frame.Shape.cut(
            Part.makeBox(12, 4, 8.3, App.Vector(-21, 1.25, 2.2))
        )
        with patch(
            "gondola.validation.rail_mount.propulsion.fixed_frame_shape",
            return_value=frame.Shape,
        ):
            report = self.check()
        row = next(
            row for row in report["saved_integral_mounts"] if row["part"] == frame.Name
        )
        self.assertLess(row["source_comparison"]["difference_mm3"], 1e-5)
        self.assertLess(
            row["attachment_sites"][0]["independent_lower_mount_comparison"][
                "difference_mm3"
            ],
            1e-5,
        )
        self.assertGreater(
            row["attachment_sites"][1]["independent_lower_mount_comparison"][
                "difference_mm3"
            ],
            100,
        )
        self.assertFalse(row["passed"])

    def test_shifted_saved_bolt_and_wrong_sku_are_rejected(self):
        obj = self.doc.BatteryEquipmentModuleRailMountScrew
        obj.Placement.Base = App.Vector(0.1, 0, 0)
        report = self.check()
        self.assertFalse(report["passed"])
        obj.Placement.Base = App.Vector()
        obj.HardwareSKU = "M2X6_BUTTON_HEAD"
        self.assertFalse(self.check()["passed"])

    def test_shared_joint_rejects_old_short_screw_and_missing_bridge_head_land(self):
        from gondola.cad import translated_shape
        from gondola.parts import rail

        screw = self.doc.MainPropulsionModuleRailMountScrew
        original_shape, original_sku = screw.Shape.copy(), screw.HardwareSKU
        screw.Shape = translated_shape(rail.attachment_screw_shape(), x=14)
        screw.HardwareSKU = "M3X8_BUTTON_HEAD"
        self.assertFalse(self.check()["passed"])
        screw.Shape, screw.HardwareSKU = original_shape, original_sku
        bridge = self.doc.ServoDriveBridge
        bridge.Shape = bridge.Shape.cut(
            Part.makeBox(1, 0.5, 0.3, App.Vector(13.5, -9.0, 8.2))
        )
        report = self.check()
        self.assertFalse(report["passed"])
        row = next(
            row
            for row in report["rails"][0]["installed_mounts"]
            if row["module"] == "MainPropulsionModule"
        )
        self.assertGreater(
            row["saved_lower_mount_attachment"]["missing_head_support_mm3"], 0
        )

    def test_missing_positive_guard_is_rejected_independently_of_generator(self):
        from gondola.parts import equipment_mounts

        mount = self.doc.BatteryMount
        mount.Shape = mount.Shape.cut(
            Part.makeBox(16, 2.5, 8.3, App.Vector(-8, 1.45, 2.2))
        )
        original_builder = equipment_mounts.mount_shape
        with patch(
            "gondola.validation.rail_mount.equipment_mounts.mount_shape",
            side_effect=lambda kind: (
                mount.Shape if kind == "battery" else original_builder(kind)
            ),
        ):
            report = self.check()
        row = next(
            row
            for row in report["saved_integral_mounts"]
            if row["part"] == "BatteryMount"
        )
        self.assertLess(row["source_comparison"]["difference_mm3"], 1e-5)
        self.assertGreater(
            row["independent_lower_mount_comparison"]["difference_mm3"], 10
        )
        self.assertFalse(row["passed"])

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

    def test_widened_base_is_rejected_even_if_generator_has_the_same_defect(self):
        obj = self.doc.ContinuousRail
        obj.Shape = obj.Shape.fuse(
            Part.makeBox(8, 7, 1.5, App.Vector(47, -3.5, 0))
        ).removeSplitter()
        with patch(
            "gondola.validation.rail_mount.rail.rail_shape", return_value=obj.Shape
        ):
            report = self.check()
        self.assertFalse(report["passed"])
        row = report["rails"][0]
        self.assertLess(row["source_comparison"]["difference_mm3"], 1e-5)
        self.assertGreater(row["extra_base_material_mm3"], 11.9)
        self.assertAlmostEqual(row["missing_unbroken_base_witness_mm3"], 0, places=6)

    def test_missing_unused_wall_is_rejected_independently_of_generator(self):
        obj = self.doc.ContinuousRail
        obj.Shape = obj.Shape.cut(Part.makeBox(20, 2.5, 8, App.Vector(102, -1.25, 1.5)))
        with patch(
            "gondola.validation.rail_mount.rail.rail_shape", return_value=obj.Shape
        ):
            report = self.check()
        row = report["rails"][0]
        self.assertFalse(report["passed"])
        self.assertLess(row["source_comparison"]["difference_mm3"], 1e-5)
        self.assertFalse(row["independent_wall_top_sections"]["passed"])
        self.assertTrue(all(mount["passed"] for mount in row["installed_mounts"]))

    def test_thinned_straight_base_is_rejected_independently_of_generator(self):
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
        self.assertAlmostEqual(row["extra_base_material_mm3"], 0, places=6)

    def test_propulsion_contract_cannot_claim_a_single_carrier_attachment(self):
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

    def test_saved_tape_contract_cannot_misrepresent_unqualified_adhesion(self):
        obj = self.doc.ContinuousRail
        original = obj.TapeAttachmentContract
        changed = json.loads(original)
        changed["qualification"] = "Adhesion and loaded curvature verified"
        for value in (json.dumps(changed), "{}", "not JSON"):
            with self.subTest(value=value):
                obj.TapeAttachmentContract = value
                report = self.check()
                self.assertFalse(report["passed"])
                row = report["rails"][0]
                self.assertFalse(row["tape_attachment_contract_matches"])
                self.assertLess(row["source_comparison"]["difference_mm3"], 1e-5)
                self.assertTrue(all(tape["passed"] for tape in row["tape_wings"]))
        obj.TapeAttachmentContract = original
        self.assertTrue(self.check()["passed"])

    def test_missing_tape_contract_is_rejected(self):
        self.doc.ContinuousRail.removeProperty("TapeAttachmentContract")
        report = self.check()
        self.assertFalse(report["passed"])
        self.assertFalse(report["rails"][0]["tape_attachment_contract_matches"])

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
