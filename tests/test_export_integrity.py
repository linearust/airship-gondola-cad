"""Verify hardware BOM and print-manifest integrity without FreeCAD."""

import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from gondola import procurement

try:
    import FreeCAD as NativeApp
    import Part as NativePart
except ImportError:
    NativeApp = NativePart = None


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ExportIntegrityTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="gondola-bom-")
        self.addCleanup(directory.cleanup)
        self.output = Path(directory.name)
        root = Path(__file__).resolve().parents[1]
        modules = {
            "FreeCAD": Mock(),
            "Part": Mock(),
            "MeshPart": Mock(),
            "gondola.parts.equipment_envelopes": Mock(),
            "gondola.parts.optical_sensor": Mock(),
            "gondola.parts.stack_interface": Mock(),
            "gondola.validation.optical": Mock(),
            "gondola.validation.wiring": Mock(),
            "gondola.parts.equipment_mounts": Mock(),
            "gondola.contracts.equipment_interfaces": Mock(),
            "gondola.cad": types.SimpleNamespace(world_shape=Mock()),
            "gondola.validation.geometry": types.SimpleNamespace(
                intersection_volume=Mock(),
                local_shape=Mock(),
                belongs_to_group=Mock(),
                translation_sweep=Mock(),
            ),
        }
        with patch.dict(sys.modules, modules):
            self.print_export = load_module(
                "gondola._print_export_under_test", root / "gondola/print_export.py"
            )
            self.equipment = load_module(
                "gondola.validation._equipment_under_test",
                root / "gondola/validation/equipment.py",
            )
        self.print_export.source_fingerprint = Mock(return_value="current source")
        patcher = patch.object(
            procurement, "source_fingerprint", return_value="current source"
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.equipment.source_fingerprint = Mock(return_value="current source")
        self.hardware = []
        for sku, quantity in self.equipment.PURCHASED_HARDWARE_QUANTITIES.items():
            for index in range(quantity):
                self.hardware.append(
                    types.SimpleNamespace(
                        Name=f"{sku}_{index}",
                        Label=sku,
                        HardwareSKU=sku,
                        MaterialSelection=self.equipment.HARDWARE_MATERIALS[sku],
                        ThreadStandard="M2 x 0.4; right-hand",
                        SourceURL="https://example.com/first-journal",
                        PurchaseSearchQuery=f"Buy {sku}",
                        PurchaseSearchURL=f"https://example.com/search/{sku}",
                        PurchaseRequirements=f"Verified dimensions for {sku}",
                        PurchaseCandidateURL="",
                        PurchaseEvidenceNotes="Specification only; no purchased lot verified.",
                        PurchasingStatus="Specification only",
                        PrintPart=False,
                    )
                )
        nuts = [
            obj for obj in self.hardware if obj.HardwareSKU == "M2_SQUARE_NUT_DIN562"
        ]
        # One purchase specification has different native evidence and wording
        # across rail, journal and optical instances. It must remain one BOM row.
        for obj in nuts[2:]:
            obj.ThreadStandard = "ISO metric coarse M2 x 0.4, right hand"
            obj.SourceURL = "https://example.com/journal-nuts"
        self.document = types.SimpleNamespace(
            DesignRegistry=types.SimpleNamespace(
                HardwareParts=self.hardware,
                PrintedParts=[],
                SourceFingerprint="current source",
            )
        )
        self.source = self.output / "gondola.FCStd"
        self.bom_path = self.output / "gondola_hardware_bom.json"

    def export(self):
        return procurement.export_hardware_bom(self.hardware, self.output, "gondola")

    def test_mixed_native_evidence_stays_in_one_valid_purchase_group(self):
        bom = self.export()
        expected = self.equipment.PURCHASED_HARDWARE_QUANTITIES
        self.assertEqual(bom["purchased_hardware_quantity"], sum(expected.values()))
        self.assertEqual(bom["unique_purchase_spec_count"], len(expected))
        self.assertEqual(len(bom["items"]), len(expected))
        self.assertEqual(bom["purchase_scope"], procurement.hardware_bom_scope())
        self.assertFalse(bom["purchase_scope"]["complete_gondola_purchase_list"])
        nuts = next(row for row in bom["items"] if row["sku"] == "M2_SQUARE_NUT_DIN562")
        self.assertEqual(nuts["quantity"], expected["M2_SQUARE_NUT_DIN562"])
        self.assertEqual(
            nuts["sources"],
            ["https://example.com/first-journal", "https://example.com/journal-nuts"],
        )
        self.assertEqual(
            nuts["thread_descriptions"],
            ["ISO metric coarse M2 x 0.4, right hand", "M2 x 0.4; right-hand"],
        )
        self.assertNotIn("source", nuts)
        self.assertNotIn("thread", nuts)
        self.assertEqual(json.loads(self.bom_path.read_text()), bom)
        audit = self.equipment.hardware_check(self.document, self.source)
        self.assertTrue(audit["passed"])
        self.assertTrue(audit["bom_each_instance_exactly_once"])
        self.assertTrue(audit["not_printed"])

    def test_shared_sku_keeps_all_role_notes_and_is_order_independent(self):
        nuts = [
            obj for obj in self.hardware if obj.HardwareSKU == "M2_SQUARE_NUT_DIN562"
        ]
        for index, part in enumerate(nuts):
            part.Label = "Rail nut" if index < 3 else "Journal / optical nut"
            part.Notes = (
                "Captive clamp pocket"
                if index < 3
                else "Hold exposed nut while tightening"
            )
        first = self.export()
        row = next(
            row for row in first["items"] if row["sku"] == "M2_SQUARE_NUT_DIN562"
        )
        self.assertEqual(row["labels"], ["Journal / optical nut", "Rail nut"])
        self.assertEqual(
            row["notes"], ["Captive clamp pocket", "Hold exposed nut while tightening"]
        )
        self.assertNotIn("label", row)
        self.assertTrue(
            self.equipment.hardware_check(self.document, self.source)["passed"]
        )
        self.hardware.reverse()
        self.assertEqual(first, self.export())

    def test_bom_rejects_unverified_material_grades_and_duplicate_instances(self):
        part = self.hardware[0]
        original = part.MaterialSelection
        for material in ("Nylon", "Nylon PA6", "A2 or PA66", "Unspecified"):
            with self.subTest(material=material):
                part.MaterialSelection = material
                with self.assertRaisesRegex(ValueError, "hardware material"):
                    self.export()
        part.MaterialSelection = original
        self.hardware.append(part)
        with self.assertRaisesRegex(ValueError, "more than once"):
            self.export()

    def test_audit_rejects_hex_nut_substitution_for_square_rail_nuts(self):
        for obj in self.hardware:
            if obj.HardwareSKU == "M2_SQUARE_NUT_DIN562":
                obj.HardwareSKU = "M2_HEX_NUT"
        self.export()
        audit = self.equipment.hardware_check(self.document, self.source)
        self.assertFalse(audit["passed"])
        self.assertTrue(audit["bom_each_instance_exactly_once"])

    def test_audit_rejects_missing_or_fabricated_group_evidence(self):
        for key in ("sources", "thread_descriptions", "labels", "notes"):
            for operation in ("remove", "add", "omit"):
                with self.subTest(field=key, operation=operation):
                    bom = self.export()
                    nuts = next(
                        row
                        for row in bom["items"]
                        if row["sku"] == "M2_SQUARE_NUT_DIN562"
                    )
                    if operation == "remove":
                        nuts[key].pop()
                    elif operation == "add":
                        nuts[key] = sorted(nuts[key] + ["unmodeled evidence"])
                    else:
                        del nuts[key]
                    self.bom_path.write_text(json.dumps(bom))
                    audit = self.equipment.hardware_check(self.document, self.source)
                    self.assertFalse(audit["passed"])
                    self.assertFalse(
                        next(
                            row
                            for row in audit["bom_rows"]
                            if row["sku"] == "M2_SQUARE_NUT_DIN562"
                        )["matches_native_instances"]
                    )

    def test_export_rejects_conflicting_or_missing_purchase_requirements(self):
        part = self.hardware[0]
        for replacement in ("", "different nominal length"):
            with self.subTest(requirements=replacement):
                part.PurchaseRequirements = replacement
                with self.assertRaisesRegex(ValueError, "PurchaseRequirements"):
                    self.export()

    def test_audit_rejects_changed_or_omitted_procurement_fields(self):
        fields = (
            *procurement.PURCHASE_METADATA_FIELDS,
            "labels",
            "notes",
            "purchase_code",
        )
        for field in fields:
            for operation in ("alter", "omit"):
                with self.subTest(field=field, operation=operation):
                    bom = self.export()
                    row = bom["items"][0]
                    if operation == "alter":
                        row[field] = "unsupported replacement"
                    else:
                        del row[field]
                    self.bom_path.write_text(json.dumps(bom))
                    audit = self.equipment.hardware_check(self.document, self.source)
                    self.assertFalse(audit["passed"])
                    self.assertFalse(audit["bom_rows"][0]["matches_native_instances"])

    def test_audit_rejects_incorrect_purchase_scope(self):
        for scope in (None, {"complete_gondola_purchase_list": True}):
            with self.subTest(scope=scope):
                bom = self.export()
                bom["purchase_scope"] = scope
                self.bom_path.write_text(json.dumps(bom))
                audit = self.equipment.hardware_check(self.document, self.source)
                self.assertFalse(audit["passed"])
                self.assertFalse(audit["bom_purchase_scope_matches_contract"])

    def test_equipment_report_rejects_bom_changes_during_validation(self):
        self.export()
        self.source.write_bytes(b"native CAD")
        self.document.Name = "TestDocument"
        self.document.DesignRegistry.ReferenceParts = []
        self.document.DesignRegistry.TapeReferences = []
        self.document.getObject = Mock(
            return_value=types.SimpleNamespace(PropertiesList=[])
        )
        self.equipment.App.openDocument.return_value = self.document
        original_check = self.equipment.hardware_check

        def audit_then_change_bom(*args):
            result = original_check(*args)
            self.bom_path.write_text(self.bom_path.read_text() + "\n")
            return result

        with (
            patch.object(
                self.equipment.wiring_validation,
                "reserve_checks",
                return_value=([], []),
            ),
            patch.object(
                self.equipment, "mtf_sensor_check", return_value={"passed": True}
            ),
            patch.object(
                self.equipment, "mounting_check", return_value={"passed": True}
            ),
            patch.object(
                self.equipment, "hardware_check", side_effect=audit_then_change_bom
            ),
            patch("builtins.print"),
        ):
            report = self.equipment.validate(self.source)
        self.assertTrue(report["hardware"]["passed"])
        self.assertTrue(report["source_unchanged"])
        self.assertFalse(report["hardware_bom_unchanged"])
        self.assertNotEqual(
            report["hardware_bom_sha256_before"], report["hardware_bom_sha256_after"]
        )
        self.assertFalse(report["passed"])

    def test_print_roles_cannot_be_exchanged_while_preserving_totals(self):
        installed = types.SimpleNamespace(
            Name="BatteryMount", PrintSKU="BatteryMount", PrintPart=True
        )
        coupon = types.SimpleNamespace(
            Name="RailFitSample", PrintSKU="RailFitSample", PrintPart=True
        )
        for part, installed_count in ((installed, 1), (coupon, 0)):
            entry = {
                "sku": part.PrintSKU,
                "instances": [part.Name],
                "quantity": 1,
                "installed_quantity": installed_count,
                "coupon_quantity": 1 - installed_count,
            }
            check = self.print_export.print_entry_inventory_check(
                entry, [installed], [coupon]
            )
            self.assertTrue(check["passed"])
            entry["installed_quantity"], entry["coupon_quantity"] = (
                entry["coupon_quantity"],
                entry["installed_quantity"],
            )
            check = self.print_export.print_entry_inventory_check(
                entry, [installed], [coupon]
            )
            self.assertFalse(check["passed"])
            self.assertFalse(check["quantities_match_native_roles"])

    def test_print_manifest_is_bound_to_native_sku_and_print_flag(self):
        part = types.SimpleNamespace(
            Name="BatteryMount", PrintSKU="BatteryMount", PrintPart=True
        )
        entry = {
            "sku": "BatteryMount",
            "instances": [part.Name],
            "quantity": 1,
            "installed_quantity": 1,
            "coupon_quantity": 0,
        }
        for attribute, replacement in (
            ("PrintSKU", "RailFitSample"),
            ("PrintPart", False),
            ("Name", "UnregisteredPrint"),
        ):
            with self.subTest(attribute=attribute):
                original = getattr(part, attribute)
                setattr(part, attribute, replacement)
                result = self.print_export.print_entry_inventory_check(
                    entry, [part], []
                )
                self.assertFalse(result["passed"])
                setattr(part, attribute, original)

    def test_diagonal_print_rotation_cannot_hide_an_overlong_member(self):
        check = self.print_export.print_size_check([400, 1, 1], [284, 284, 1])
        self.assertFalse(check["local_part_within_limit"])
        self.assertTrue(check["oriented_part_within_limit"])
        self.assertTrue(all(check["within_published_fabrication_size"].values()))
        self.assertFalse(check["passed"])
        self.assertTrue(
            self.print_export.print_size_check([340, 32, 7], [264, 264, 7])["passed"]
        )

    def test_export_limit_and_supplier_envelopes_are_independent(self):
        too_wide = self.print_export.print_size_check([300, 300, 7], [350, 350, 7])
        self.assertFalse(too_wide["oriented_part_within_limit"])
        too_tall = self.print_export.print_size_check([281, 2, 2], [2, 2, 281])
        self.assertTrue(too_tall["oriented_part_within_limit"])
        self.assertTrue(too_tall["within_published_fabrication_size"]["SLS"])
        self.assertFalse(too_tall["within_published_fabrication_size"]["MJF"])
        self.assertFalse(too_tall["passed"])

    def test_invalid_dimension_axes_fail_closed(self):
        for axes in (
            None,
            [],
            [1, 2],
            [1, 2, 3, 4],
            [0, 1, 1],
            [-1, 1, 1],
            [float("nan"), 1, 1],
            [1, float("inf"), 1],
            [True, 1, 1],
            ["3", 1, 1],
        ):
            for local, exported in ((axes, [2, 2, 2]), ([2, 2, 2], axes)):
                with self.subTest(local=local, exported=exported):
                    check = self.print_export.print_size_check(local, exported)
                    self.assertFalse(check["dimensions_valid"])
                    self.assertFalse(check["passed"])

    def test_size_declaration_cannot_hide_an_instance_or_actual_stl_violation(self):
        local = {"First": [340, 32, 7], "Second": [32, 340, 7]}
        exported = {name: [264, 264, 7] for name in local}
        entry = {
            "local_sizes_mm": {name: list(size) for name, size in local.items()},
            "size_mm": [264, 264, 7],
            "size_checks": {
                "all_native_instances_within_limit": True,
                "all_oriented_instances_within_limit": True,
                "within_published_fabrication_size": {"SLS": True, "MJF": True},
                "passed": True,
            },
        }
        check = self.print_export.print_size_declaration_check
        self.assertTrue(check(entry, local, exported, [264, 264, 7])["passed"])
        for field in ("local_sizes_mm", "size_mm", "size_checks"):
            stale = {key: value for key, value in entry.items() if key != field}
            self.assertFalse(check(stale, local, exported, [264, 264, 7])["passed"])
        actual_local = {**local, "Second": [32, 400, 7]}
        result = check(entry, actual_local, exported, [264, 264, 7])
        self.assertFalse(result["local_sizes_match_manifest"])
        self.assertFalse(result["native_size_checks"]["passed"])
        self.assertFalse(result["passed"])
        result = check(entry, local, exported, [341, 264, 7])
        self.assertTrue(result["size_checks_match_manifest"])
        self.assertFalse(result["actual_stl_size_checks"]["passed"])
        self.assertFalse(result["passed"])


@unittest.skipIf(NativeApp is None, "Requires the FreeCAD Python runtime")
class NativePrintSizeTests(unittest.TestCase):
    def test_overlong_installed_part_and_coupon_are_rejected_before_export(self):
        from gondola.print_export import (
            export_print_parts,
            local_part_dimensions,
            print_shape,
        )

        for coupon in (False, True):
            with (
                self.subTest(coupon=coupon),
                tempfile.TemporaryDirectory() as directory,
            ):
                existing = set(NativeApp.listDocuments())
                try:
                    doc = NativeApp.newDocument("OverlongPrintRegression")
                    obj = doc.addObject("Part::Feature", "LongMember")
                    obj.Shape = NativePart.makeBox(400, 1, 1)
                    obj.addProperty("App::PropertyRotation", "PrintRotation")
                    obj.PrintRotation = NativeApp.Rotation(
                        NativeApp.Vector(0, 0, 1), 45
                    )
                    self.assertAlmostEqual(local_part_dimensions(obj)[0], 400)
                    bb = print_shape(obj).optimalBoundingBox(False, False)
                    self.assertLess(max(bb.XLength, bb.YLength, bb.ZLength), 340)
                    with self.assertRaisesRegex(RuntimeError, "dimension limits"):
                        export_print_parts(
                            doc,
                            [] if coupon else [obj],
                            [obj] if coupon else [],
                            directory,
                            "overlong",
                        )
                finally:
                    for name in set(NativeApp.listDocuments()) - existing:
                        NativeApp.closeDocument(name)


if __name__ == "__main__":
    unittest.main()
