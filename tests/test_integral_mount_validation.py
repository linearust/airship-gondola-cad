"""Saved side-clamped L seats require exact geometry, registry and parent bindings."""

import unittest
from types import SimpleNamespace

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class IntegralMountValidationTests(unittest.TestCase):
    def setUp(self):
        from gondola.config import BASELINE_FILE
        from gondola.provenance import file_sha256

        self.path = BASELINE_FILE
        self.before = file_sha256(self.path)
        self.doc = App.openDocument(str(self.path), hidden=True)
        self.addCleanup(self.close_without_saving)

    def close_without_saving(self):
        from gondola.provenance import file_sha256

        App.closeDocument(self.doc.Name)
        self.assertEqual(file_sha256(self.path), self.before)

    def checks(self, registry=None):
        from gondola.validation.rail_mount import saved_integral_mount_checks

        return saved_integral_mount_checks(
            self.doc, registry or self.doc.DesignRegistry
        )

    def test_saved_four_integral_mounts_match_source_and_literal_geometry(self):
        rows = self.checks()
        self.assertEqual(
            {row["part"] for row in rows},
            {
                "BatteryMount",
                "ElectronicsMount",
                "AccessoryMount",
                "PropulsionFixedFrame",
            },
        )
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(row["passed"] for row in rows), rows)
        for row in rows:
            self.assertLess(row["source_comparison"]["difference_mm3"], 1e-5)
            self.assertLess(
                row["independent_lower_mount_comparison"]["difference_mm3"], 1e-5
            )
            self.assertLess(
                row["source_lower_mount_comparison"]["difference_mm3"], 1e-5
            )

    def test_extra_upper_cut_is_rejected_on_every_mount(self):
        # Outside the protected L-foot crop but within the actual load path.
        # Complete source comparison must catch defects above that witness.
        cuts = {
            name: Part.makeBox(1, 1, 0.4, App.Vector(4, -3, 12))
            for name in ("BatteryMount", "ElectronicsMount", "AccessoryMount")
        }
        cuts["PropulsionFixedFrame"] = Part.makeBox(1, 1, 0.4, App.Vector(0, 0, 10.5))
        for name in (
            "BatteryMount",
            "ElectronicsMount",
            "AccessoryMount",
            "PropulsionFixedFrame",
        ):
            with self.subTest(part=name):
                obj = self.doc.getObject(name)
                original = obj.Shape.copy()
                try:
                    changed = original.cut(cuts[name])
                    self.assertGreater(original.Volume - changed.Volume, 0.39)
                    obj.Shape = changed
                    row = next(row for row in self.checks() if row["part"] == name)
                    self.assertFalse(row["passed"], row)
                    self.assertGreater(row["source_comparison"]["difference_mm3"], 0.39)
                finally:
                    obj.Shape = original

    def test_flat_clamp_leg_cannot_be_omitted(self):
        obj = self.doc.PropulsionFixedFrame
        original = obj.Shape.copy()
        try:
            cut = Part.makeBox(0.5, 0.4, 0.5, App.Vector(23, -2, 5.5))
            changed = original.cut(cut)
            self.assertGreater(original.Volume - changed.Volume, 0.09)
            obj.Shape = changed
            row = next(row for row in self.checks() if row["part"] == obj.Name)
            self.assertFalse(row["passed"], row)
            self.assertGreater(row["source_comparison"]["difference_mm3"], 0.09)
            self.assertGreater(
                row["independent_lower_mount_comparison"]["difference_mm3"], 0.09
            )
        finally:
            obj.Shape = original

    def test_removed_bolt_load_path_is_rejected_for_every_carrier(self):
        cut = Part.makeCylinder(0.3, 1, App.Vector(2.4, 0, 9.6))
        for name in ("BatteryMount", "ElectronicsMount", "AccessoryMount"):
            with self.subTest(part=name):
                obj = self.doc.getObject(name)
                original = obj.Shape.copy()
                try:
                    changed = original.cut(cut)
                    self.assertGreater(original.Volume - changed.Volume, 0.28)
                    obj.Shape = changed
                    row = next(row for row in self.checks() if row["part"] == name)
                    self.assertFalse(row["passed"], row)
                    self.assertGreater(
                        row["independent_lower_mount_comparison"]["difference_mm3"],
                        0.28,
                    )
                finally:
                    obj.Shape = original

    def test_added_material_below_the_seat_is_rejected(self):
        # An added lip below the L-seat could defeat lift-off. Detect added
        # material as well as removed load-bearing material.
        obj = self.doc.BatteryMount
        original = obj.Shape.copy()
        added = Part.makeBox(2, 2, 1, App.Vector(0, -1, 6.8))
        obj.Shape = original.fuse(added)
        self.assertGreater(obj.Shape.Volume - original.Volume, 2.7)
        row = next(row for row in self.checks() if row["part"] == obj.Name)
        self.assertFalse(row["passed"], row)
        self.assertGreater(
            row["independent_lower_mount_comparison"]["difference_mm3"], 2.7
        )

    def test_missing_registry_entry_and_duplicate_cannot_hide_another_carrier(self):
        registry = self.doc.DesignRegistry
        mounts = list(registry.EquipmentMounts)
        for equipment in (mounts[:-1], [mounts[0], mounts[0], mounts[2]]):
            with self.subTest(names=[obj.Name for obj in equipment]):
                rows = self.checks(
                    SimpleNamespace(
                        EquipmentMounts=equipment,
                        PrintedParts=list(registry.PrintedParts),
                    )
                )
                self.assertFalse(any(row["equipment_registry_matches"] for row in rows))
                self.assertFalse(any(row["passed"] for row in rows))
        without_frame = [
            obj for obj in registry.PrintedParts if obj.Name != "PropulsionFixedFrame"
        ]
        rows = self.checks(
            SimpleNamespace(EquipmentMounts=mounts, PrintedParts=without_frame)
        )
        frame = next(row for row in rows if row["part"] == "PropulsionFixedFrame")
        self.assertFalse(frame["registered_once_as_print"])
        self.assertFalse(frame["passed"])

    def test_missing_frame_part_and_wrong_parent_fail_exact_binding(self):
        frame = self.doc.PropulsionFixedFrame
        self.doc.MainPropulsionModule.removeObject(frame)
        self.doc.BatteryEquipmentModule.addObject(frame)
        row = next(row for row in self.checks() if row["part"] == frame.Name)
        self.assertFalse(row["parent_matches"])
        self.assertFalse(row["passed"])
        self.doc.removeObject(frame.Name)
        rows = self.checks()
        self.assertEqual(len(rows), 4)
        frame = next(row for row in rows if row["part"] == "PropulsionFixedFrame")
        self.assertFalse(frame["passed"])
        self.assertEqual(frame["error"], "Missing integral mount")


if __name__ == "__main__":
    unittest.main()
