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
            "gondola.parts.equipment_mounts": Mock(),
            "gondola.parts.mounting_interfaces": Mock(),
            "gondola.cad": types.SimpleNamespace(world_shape=Mock()),
            "gondola.validation.geometry": types.SimpleNamespace(
                intersection_volume=Mock(), local_shape=Mock()
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
                        MaterialSelection="A2 stainless steel",
                        ThreadStandard="M2 x 0.4; right-hand",
                        SourceURL="https://example.com/first-journal",
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
        self.assertEqual(bom["purchased_hardware_quantity"], 22)
        self.assertEqual(bom["unique_purchase_spec_count"], 5)
        self.assertEqual(len(bom["items"]), 5)
        nuts = next(row for row in bom["items"] if row["sku"] == "M2_HEX_NUT")
        self.assertEqual(nuts["quantity"], 4)
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
        for obj in self.hardware:
            if obj.HardwareSKU == "M2_SQUARE_NUT_DIN562":
                obj.HardwareSKU = "M2_HEX_NUT"
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


try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires FreeCAD")
class MountingPadGeometryTests(unittest.TestCase):
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
