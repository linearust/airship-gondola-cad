"""Exercise native BOM grouping and its independent audit without FreeCAD."""

import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HardwareBomTests(unittest.TestCase):
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
            "gondola.validation.optical": Mock(),
            "gondola.parts.equipment_mounts": Mock(),
            "gondola.parts.mounting_interfaces": Mock(),
            "gondola.cad": types.SimpleNamespace(world_shape=Mock()),
            "gondola.validation.geometry": types.SimpleNamespace(
                intersection_volume=Mock(),
                local_shape=Mock(),
                belongs_to_group=Mock(),
                translation_sweep=Mock(),
            ),
        }
        with patch.dict(sys.modules, modules):
            self.manufacturing = load_module(
                "gondola._manufacturing_under_test", root / "gondola/manufacturing.py"
            )
            self.equipment = load_module(
                "gondola.validation._equipment_under_test",
                root / "gondola/validation/equipment.py",
            )
        self.manufacturing.source_fingerprint = Mock(return_value="current source")
        self.equipment.source_fingerprint = Mock(return_value="current source")
        self.hardware = []
        for sku, quantity in self.equipment.EXPECTED_PURCHASE_QUANTITIES.items():
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
        nuts = [obj for obj in self.hardware if obj.HardwareSKU == "M2_HEX_NUT"]
        # One purchase specification has different native evidence and wording
        # at different journal instances. It must remain one BOM row, separate
        # from the rail's DIN 562 square nuts.
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
        return self.manufacturing.export_hardware_bom(
            self.hardware, self.output, "gondola"
        )

    def test_mixed_native_evidence_stays_in_one_valid_purchase_group(self):
        bom = self.export()
        self.assertEqual(bom["purchased_hardware_quantity"], 54)
        self.assertEqual(bom["unique_purchase_spec_count"], 9)
        self.assertEqual(len(bom["items"]), 9)
        self.assertEqual(bom["purchase_scope"], self.manufacturing.hardware_bom_scope())
        self.assertFalse(bom["purchase_scope"]["complete_gondola_purchase_list"])
        nuts = next(row for row in bom["items"] if row["sku"] == "M2_HEX_NUT")
        self.assertEqual(nuts["quantity"], 6)
        square_nuts = next(
            row for row in bom["items"] if row["sku"] == "M2_SQUARE_NUT_DIN562"
        )
        self.assertEqual(square_nuts["quantity"], 3)
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

    def test_audit_rejects_hex_nut_substitution_for_square_rail_nuts(self):
        hex_nut = next(obj for obj in self.hardware if obj.HardwareSKU == "M2_HEX_NUT")
        for obj in self.hardware:
            if obj.HardwareSKU == "M2_SQUARE_NUT_DIN562":
                obj.HardwareSKU = "M2_HEX_NUT"
                for attribute in self.manufacturing.PURCHASE_METADATA_FIELDS.values():
                    setattr(obj, attribute, getattr(hex_nut, attribute))
        self.export()
        audit = self.equipment.hardware_check(self.document, self.source)
        self.assertFalse(audit["passed"])
        self.assertTrue(audit["bom_each_instance_exactly_once"])

    def test_audit_rejects_missing_or_fabricated_group_evidence(self):
        for key in ("sources", "thread_descriptions"):
            for operation in ("remove", "add", "omit"):
                with self.subTest(field=key, operation=operation):
                    bom = self.export()
                    nuts = next(
                        row for row in bom["items"] if row["sku"] == "M2_HEX_NUT"
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
                            if row["sku"] == "M2_HEX_NUT"
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
            *self.manufacturing.PURCHASE_METADATA_FIELDS,
            "label",
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
            patch.object(self.equipment, "reserve_checks", return_value=([], [])),
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
            check = self.manufacturing.print_entry_inventory_check(
                entry, [installed], [coupon]
            )
            self.assertTrue(check["passed"])
            entry["installed_quantity"], entry["coupon_quantity"] = (
                entry["coupon_quantity"],
                entry["installed_quantity"],
            )
            check = self.manufacturing.print_entry_inventory_check(
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
                result = self.manufacturing.print_entry_inventory_check(
                    entry, [part], []
                )
                self.assertFalse(result["passed"])
                setattr(part, attribute, original)


try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires FreeCAD")
class MountingPadGeometryTests(unittest.TestCase):
    def test_native_rail_clamps_declare_m2_thread_dimensions(self):
        from gondola.cad import create_group
        from gondola.parts import rail

        document = App.newDocument("RailThreadRegressionTest")
        self.addCleanup(App.closeDocument, document.Name)
        parent = create_group(document, "ClampGroup", "Clamp hardware")
        hardware = rail.build_clamp_hardware(document, parent, "Test", "0")
        self.assertEqual(len(hardware), 2)
        for part in hardware:
            self.assertEqual(part.NominalThreadDiameter.Value, 2)
            self.assertEqual(part.ThreadPitch.Value, 0.4)
            self.assertIn("M2", part.ThreadStandard)
            self.assertNotIn("unthreaded", part.ThreadStandard.lower())

    def test_native_hardware_distinguishes_unthreaded_washers(self):
        from gondola.parts import metric_hardware as metric

        document = App.newDocument("HardwareThreadRegressionTest")
        self.addCleanup(App.closeDocument, document.Name)
        parts = (
            ("M2_WASHER_2.2_5_0.3", metric.washer_shape(), True),
            ("M3_WASHER_3.2_9_0.8", metric.journal_retaining_washer_shape(), True),
            ("M2_HEX_NUT", metric.nut_shape(), False),
            ("M2X14_SOCKET_CAP", metric.screw_shape(14), False),
        )
        for index, (sku, shape, is_washer) in enumerate(parts):
            with self.subTest(sku=sku):
                obj = metric.add_hardware(
                    document, None, f"Hardware{index}", sku, shape, sku, "Test only"
                )
                self.assertEqual(obj.NominalThreadDiameter.Value, 0 if is_washer else 2)
                self.assertEqual(obj.ThreadPitch.Value, 0 if is_washer else 0.4)
                self.assertEqual("unthreaded" in obj.ThreadStandard.lower(), is_washer)
                if not is_washer:
                    self.assertNotIn("washer", obj.ThreadStandard.lower())

    def test_native_print_factory_sets_explicit_print_flag(self):
        from gondola.cad import create_group, create_printed_part

        document = App.newDocument("PrintFactoryRegressionTest")
        self.addCleanup(App.closeDocument, document.Name)
        parent = create_group(document, "PrintGroup", "Printed test parts")
        part = create_printed_part(
            document,
            parent,
            "PrintedPart",
            "Printed factory test",
            Part.makeBox(2, 3, 4),
            App.Rotation(),
            "Test only",
        )
        self.assertIn("PrintPart", part.PropertiesList)
        self.assertTrue(part.PrintPart)
        self.assertEqual(part.getTypeIdOfProperty("PrintPart"), "App::PropertyBool")

    def test_saved_mount_has_complete_bearing_annuli_and_clear_bores(self):
        from gondola.parts import equipment_mounts as mounts
        from gondola.validation.equipment import mounting_pad_check

        shape = mounts.mount_shape("electronics").copy()
        for centre in mounts.FC_HOLE_CENTRES + mounts.PAS_HOLE_CENTRES:
            result = mounting_pad_check(
                shape,
                centre,
                bottom=mounts.DECK_BOTTOM_Z,
                thickness=mounts.DECK_THICKNESS,
                hole_diameter=mounts.MOUNT_HOLE_DIAMETER,
                pad_diameter=mounts.MOUNT_PAD_DIAMETER,
            )
            self.assertTrue(result["passed"], result)

    def test_partial_bearing_or_filled_bore_is_rejected(self):
        from gondola.parts import equipment_mounts as mounts
        from gondola.validation.equipment import mounting_pad_check

        shape = mounts.mount_shape("electronics").copy()
        centre = mounts.FC_HOLE_CENTRES[0]
        x, y = centre
        bottom, thickness = mounts.DECK_BOTTOM_Z, mounts.DECK_THICKNESS
        missing_edge = shape.cut(
            Part.makeBox(1, 1, thickness + 2, App.Vector(x - 3.3, y - 0.5, bottom - 1))
        )
        blocked_bore = shape.fuse(
            Part.makeCylinder(0.4, thickness, App.Vector(x, y, bottom))
        )
        for changed in (missing_edge, blocked_bore):
            result = mounting_pad_check(
                changed,
                centre,
                bottom=bottom,
                thickness=thickness,
                hole_diameter=mounts.MOUNT_HOLE_DIAMETER,
                pad_diameter=mounts.MOUNT_PAD_DIAMETER,
            )
            self.assertFalse(result["passed"], result)


if __name__ == "__main__":
    unittest.main()
