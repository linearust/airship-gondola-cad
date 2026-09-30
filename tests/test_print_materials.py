"""Order-facing process labels must not change control identities or geometry."""

import tempfile
import unittest
from pathlib import Path

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class PrintMaterialTests(unittest.TestCase):
    def setUp(self):
        from gondola.cad import create_printed_part, set_print_sku

        self.existing = set(App.listDocuments())
        self.doc = App.newDocument("PrintMaterialRegression")
        parent = self.doc.addObject("App::Part", "CarrierModule")
        self.shape = Part.makeBox(20, 10, 2)
        self.part = create_printed_part(
            self.doc,
            parent,
            "BatteryMount",
            "PRINT | Universal carrier | battery",
            self.shape.copy(),
            App.Rotation(),
            "Test print",
        )
        set_print_sku(self.part, "UniversalEquipmentCarrier")

    def tearDown(self):
        for name in set(App.listDocuments()) - self.existing:
            App.closeDocument(name)

    def test_visible_process_and_material_preserve_native_identity_and_shape(self):
        self.assertEqual(self.part.Name, "BatteryMount")
        self.assertEqual(self.part.PrintSKU, "UniversalEquipmentCarrier")
        self.assertEqual(
            self.part.Label,
            "SLS/MJF | PA12 unfilled | PRINT | Universal carrier | battery",
        )
        self.assertEqual(self.part.PrintProcess, "SLS/MJF")
        self.assertEqual(self.part.MaterialSelection, "PA12 (unfilled)")
        self.assertLess(self.part.Shape.cut(self.shape).Volume, 1e-8)
        self.assertLess(self.shape.cut(self.part.Shape).Volume, 1e-8)

    def test_order_files_manifest_and_overview_agree(self):
        from gondola.print_export import (
            export_print_parts,
            print_entry_manufacturing_check,
        )

        with tempfile.TemporaryDirectory() as directory:
            manifest = export_print_parts(
                self.doc,
                [self.part],
                [],
                directory,
                "material",
            )
            from gondola.print_materials import PRINT_METADATA, print_metadata_matches

            layout_path = str(Path(directory) / "material_print_parts.FCStd")
            overview = next(
                doc
                for doc in App.listDocuments().values()
                if doc.FileName == layout_path
            )
            App.closeDocument(overview.Name)
            overview = App.openDocument(layout_path)
            item = overview.getObject("UniversalEquipmentCarrier")
            self.assertTrue(item.PrintPart)
            self.assertEqual(item.PrintSKU, self.part.PrintSKU)
            self.assertTrue(print_metadata_matches(item))
            for key in PRINT_METADATA:
                self.assertEqual(getattr(item, key), getattr(self.part, key))
            self.assertEqual(item.SourceObjectNames, [self.part.Name])
            self.assertEqual(
                (item.Quantity, item.InstalledQuantity, item.CouponQuantity), (1, 1, 0)
            )
            entry = manifest["parts"][0]
            folder = Path(directory) / "material_print_parts"
            self.assertEqual(
                entry["file"],
                "SLS-MJF_PA12__universal_equipment_carrier.stl",
            )
            self.assertEqual(entry["step_file"], entry["file"].replace(".stl", ".step"))
            self.assertTrue((folder / entry["file"]).is_file())
            self.assertTrue((folder / entry["step_file"]).is_file())
            self.assertEqual(entry["manufacturing"], manifest["manufacturing"])
            self.assertEqual(entry["manufacturing"]["process_category"], "SLS/MJF")
            self.assertIsNone(entry["manufacturing"]["fdm_infill_percent"])
            self.assertFalse(entry["manufacturing"]["process_grade_finish_confirmed"])
            self.assertTrue(print_entry_manufacturing_check(entry, [self.part]))
            for field, replacement in (
                ("manufacturing", {"process_category": "FDM"}),
                ("file", "unmarked.stl"),
                ("step_file", "unmarked.step"),
            ):
                with self.subTest(field=field):
                    self.assertFalse(
                        print_entry_manufacturing_check(
                            {**entry, field: replacement},
                            [self.part],
                        )
                    )

    def test_unmarked_or_wrong_material_native_print_cannot_export(self):
        from gondola.print_export import export_print_parts

        for field, replacement in (
            ("Label", "Missing process label"),
            ("PrintProcess", "FDM"),
            ("MaterialSelection", "PA12 carbon filled"),
            ("PrintInfill", "15%"),
        ):
            original = getattr(self.part, field)
            try:
                setattr(self.part, field, replacement)
                with self.subTest(field=field), tempfile.TemporaryDirectory() as folder:
                    with self.assertRaisesRegex(RuntimeError, "print specification"):
                        export_print_parts(self.doc, [self.part], [], folder, "bad")
            finally:
                setattr(self.part, field, original)


if __name__ == "__main__":
    unittest.main()
