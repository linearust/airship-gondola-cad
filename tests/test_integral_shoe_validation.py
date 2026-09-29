"""Exact saved five-shoe capture with the bounded central carrier nut pocket."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class IntegralShoeValidationTests(unittest.TestCase):
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
        from gondola.validation.assembly import saved_integral_shoe_checks

        return saved_integral_shoe_checks(self.doc, registry or self.doc.DesignRegistry)

    def test_saved_five_integral_shoes_match_exact_allowed_geometry(self):
        rows = self.checks()
        self.assertEqual(
            {row["part"] for row in rows},
            {
                "BatteryMount",
                "ElectronicsMount",
                "AccessoryMount",
                "PropulsionFixedFrame",
                "OpticalMountBase",
            },
        )
        self.assertEqual(len(rows), 5)
        self.assertTrue(all(row["passed"] for row in rows), rows)
        for row in rows:
            self.assertEqual(
                row["declared_central_nut_pocket"],
                row["part"] in ("BatteryMount", "ElectronicsMount", "AccessoryMount"),
            )
            self.assertLess(row["difference_mm3"], 1e-5)
            self.assertLess(
                row["protected_capture_at_or_below_z10"]["difference_mm3"], 1e-5
            )

    def test_extra_upper_cut_is_rejected_on_every_shoe_including_optical(self):
        # Outside the declared nut port, but within the same upper 0.8-mm
        # band. A broad top-of-shoe exemption would wrongly accept this cut.
        cut = Part.makeBox(1, 1, 0.4, App.Vector(3, 3, 10.2))
        for name in (
            "BatteryMount",
            "ElectronicsMount",
            "AccessoryMount",
            "PropulsionFixedFrame",
            "OpticalMountBase",
        ):
            with self.subTest(part=name):
                obj = self.doc.getObject(name)
                original = obj.Shape.copy()
                try:
                    changed = original.cut(cut)
                    self.assertGreater(original.Volume - changed.Volume, 0.39)
                    obj.Shape = changed
                    row = next(row for row in self.checks() if row["part"] == name)
                    self.assertFalse(row["passed"], row)
                    self.assertGreater(row["difference_mm3"], 0.39)
                finally:
                    obj.Shape = original

    def test_missing_blind_floor_is_rejected_for_every_central_carrier(self):
        cut = Part.makeCylinder(0.45, 1.6, App.Vector(0, 0, 8.45))
        for name in ("BatteryMount", "ElectronicsMount", "AccessoryMount"):
            with self.subTest(part=name):
                obj = self.doc.getObject(name)
                original = obj.Shape.copy()
                try:
                    changed = original.cut(cut)
                    self.assertGreater(original.Volume - changed.Volume, 0.9)
                    obj.Shape = changed
                    row = next(row for row in self.checks() if row["part"] == name)
                    self.assertFalse(row["passed"], row)
                    self.assertGreater(
                        row["protected_capture_at_or_below_z10"]["difference_mm3"], 0.9
                    )
                finally:
                    obj.Shape = original

    def test_added_material_in_the_rail_channel_is_rejected(self):
        # Bridge to the existing roof while filling part of the clear T-head
        # channel. Missing-material-only comparison would wrongly accept this.
        obj = self.doc.BatteryMount
        original = obj.Shape.copy()
        added = Part.makeBox(2, 2, 1, App.Vector(-1, -1, 7.8))
        obj.Shape = original.fuse(added)
        self.assertGreater(obj.Shape.Volume - original.Volume, 2.7)
        row = next(row for row in self.checks() if row["part"] == obj.Name)
        self.assertFalse(row["passed"], row)
        self.assertGreater(
            row["protected_capture_at_or_below_z10"]["difference_mm3"], 2.7
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
        without_optical = [
            obj for obj in registry.PrintedParts if obj.Name != "OpticalMountBase"
        ]
        rows = self.checks(
            SimpleNamespace(EquipmentMounts=mounts, PrintedParts=without_optical)
        )
        optical = next(row for row in rows if row["part"] == "OpticalMountBase")
        self.assertFalse(optical["registered_once_as_print"])
        self.assertFalse(optical["passed"])

    def test_missing_optical_part_and_wrong_parent_fail_exact_binding(self):
        optical = self.doc.OpticalMountBase
        self.doc.OpticalFlowModule.removeObject(optical)
        self.doc.BatteryEquipmentModule.addObject(optical)
        row = next(row for row in self.checks() if row["part"] == optical.Name)
        self.assertFalse(row["parent_matches"])
        self.assertFalse(row["passed"])
        self.doc.removeObject(optical.Name)
        rows = self.checks()
        self.assertEqual(len(rows), 5)
        optical = next(row for row in rows if row["part"] == "OpticalMountBase")
        self.assertFalse(optical["passed"])
        self.assertEqual(optical["error"], "Missing integral shoe")

    def test_bidirectional_gate_requires_the_complete_capture_result(self):
        from gondola.validation import assembly

        rows = self.checks()
        self.assertTrue(all(row["passed"] for row in rows))
        # Keep native controls, bindings, all32 approach combinations, restoration
        # and the final gate real. Only collision/service work is mocked here;
        # separate native geometry tests above exercise every capture result.
        with (
            patch.object(assembly, "neutral_check", return_value={"passed": True}),
            patch.object(assembly, "module_service", return_value={"passed": True}),
            patch.object(assembly, "saved_integral_shoe_checks", return_value=rows),
        ):
            passed = assembly.bidirectional_service(
                self.doc, self.doc.DesignRegistry, []
            )
            self.assertTrue(passed["passed"], passed)
            self.assertEqual(len(passed["native_approach_combinations"]), 32)
            self.assertEqual(len(passed["full_service_sequences"]), 2)
            self.assertEqual(len(passed["saved_integral_shoes_match_source"]), 5)
            # A failed binding/protected-floor result must reject the assembly
            # even if the legacy top-level shape difference fields still pass.
            rows[0]["passed"] = False
            failed = assembly.bidirectional_service(
                self.doc, self.doc.DesignRegistry, []
            )
            self.assertFalse(failed["passed"])


if __name__ == "__main__":
    unittest.main()
