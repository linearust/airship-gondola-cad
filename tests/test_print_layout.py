"""Saved native inspection layouts must describe the actual printable inventory."""

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class SavedPrintLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.cad import create_printed_part, set_print_sku, set_property
        from gondola.print_export import export_print_parts
        from gondola.provenance import source_fingerprint

        cls.temp = tempfile.TemporaryDirectory(prefix="gondola-native-layout-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.folder = Path(cls.temp.name)
        cls.doc = App.newDocument("PrintLayoutAuditSource")
        cls.addClassCleanup(App.closeDocument, cls.doc.Name)
        group = cls.doc.addObject("App::Part", "Installed")
        asymmetric = Part.makeBox(18, 10, 3).cut(
            Part.makeCylinder(1.1, 3, App.Vector(4, 3, 0))
        )
        specs = [
            ("First", "Plate", asymmetric),
            ("Second", "Plate", asymmetric),
            ("Rail", "Rail", Part.makeBox(300, 5, 2)),
            ("Coupon", "Coupon", Part.makeBox(60, 8, 2)),
        ]
        parts = []
        for name, sku, shape in specs:
            item = create_printed_part(
                cls.doc,
                group,
                name,
                name,
                shape,
                App.Rotation(App.Vector(1, 0, 0), 180),
                "Inspection regression specimen",
            )
            set_print_sku(item, sku)
            parts.append(item)
        cls.registry = cls.doc.addObject("App::FeaturePython", "DesignRegistry")
        set_property(cls.registry, "PrintedParts", parts[:-1], "App::PropertyLinkList")
        set_property(cls.registry, "FitCoupons", parts[-1:], "App::PropertyLinkList")
        cls.fingerprint = source_fingerprint()
        set_property(cls.registry, "SourceFingerprint", cls.fingerprint)
        cls.doc.recompute()
        cls.manifest = export_print_parts(
            cls.doc, parts[:-1], parts[-1:], cls.folder, "inspection"
        )
        cls.layout_path = cls.folder / "inspection_print_parts.FCStd"
        layout = next(
            doc
            for doc in App.listDocuments().values()
            if doc.FileName == str(cls.layout_path)
        )
        App.closeDocument(layout.Name)

    def check_saved(self, mutation=None, manifest=None):
        from gondola.print_export import saved_print_layout_check
        from gondola.provenance import file_sha256

        with tempfile.TemporaryDirectory(dir=self.folder) as directory:
            target = Path(directory) / "layout.FCStd"
            shutil.copyfile(self.layout_path, target)
            if mutation:
                doc = App.openDocument(str(target), hidden=True)
                try:
                    mutation(doc)
                    doc.recompute()
                    doc.save()
                finally:
                    App.closeDocument(doc.Name)
            before = file_sha256(target)
            with patch(
                "gondola.print_export.source_fingerprint", return_value=self.fingerprint
            ):
                result = saved_print_layout_check(
                    target, self.registry, manifest or self.manifest
                )
            self.assertEqual(file_sha256(target), before)
            return result

    def test_current_saved_layout_preserves_print_orientation_packing_and_roles(self):
        result = self.check_saved()
        self.assertTrue(result["passed"], json.dumps(result, indent=2))
        self.assertEqual(
            [row["sku"] for row in result["parts"]], ["Plate", "Rail", "Coupon"]
        )

    def test_changed_shape_is_rejected_even_with_same_volume_and_bounds(self):
        def mutate(doc):
            from gondola.print_export import print_layout_shape, print_shape

            original = self.doc.First.Shape
            moved_hole = Part.makeBox(18, 10, 3).cut(
                Part.makeCylinder(1.1, 3, App.Vector(5, 3, 0))
            )
            self.assertAlmostEqual(original.Volume, moved_hole.Volume)
            self.doc.First.Shape = moved_hole
            try:
                doc.Plate.Shape = print_layout_shape(
                    print_shape(self.doc.First), (0, 0, 0)
                )[0]
            finally:
                self.doc.First.Shape = original

        self.assertFalse(self.check_saved(mutate)["passed"])

    def test_changed_overview_placement_is_rejected(self):
        def mutate(doc):
            placement = doc.Plate.Placement
            placement.Base.x += 1
            doc.Plate.Placement = placement

        self.assertFalse(self.check_saved(mutate)["passed"])

    def test_changed_export_orientation_is_rejected(self):
        def mutate(doc):
            placement = doc.Plate.Placement
            placement.Rotation = App.Rotation(App.Vector(0, 0, 1), 90)
            doc.Plate.Placement = placement

        self.assertFalse(self.check_saved(mutate)["passed"])

    def test_wrong_count_cannot_be_endorsed_by_changing_manifest_to_match(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["parts"][0]["quantity"] = 999
        self.assertFalse(
            self.check_saved(lambda doc: setattr(doc.Plate, "Quantity", 999), manifest)[
                "passed"
            ]
        )

    def test_changed_roles_source_names_and_labels_are_rejected(self):
        mutations = {
            "SourceObjectNames": ["Second", "First"],
            "InstalledQuantity": 1,
            "CouponQuantity": 1,
            "PrintPart": False,
            "PrintSKU": "WrongSKU",
            "Role": "Purchased",
            "MaterialSelection": "PLA",
            "PrintProcess": "FDM",
            "Label": "Wrong displayed quantity",
        }
        for property_name, value in mutations.items():
            with self.subTest(property=property_name):
                self.assertFalse(
                    self.check_saved(
                        lambda doc: setattr(doc.Plate, property_name, value)
                    )["passed"]
                )

    def test_extra_missing_and_empty_features_are_rejected(self):
        def extra(doc):
            item = doc.addObject("Part::Feature", "Unlisted")
            item.Shape = Part.makeBox(1, 1, 1)

        def empty(doc):
            doc.Plate.Shape = Part.Shape()

        for mutation in (extra, empty, lambda doc: doc.removeObject("Plate")):
            with self.subTest(mutation=mutation.__name__):
                self.assertFalse(self.check_saved(mutation)["passed"])

    def test_manifest_source_and_inventory_changes_are_rejected(self):
        for key, value in (
            ("source_fingerprint", "old source"),
            ("parts", self.manifest["parts"][:-1]),
        ):
            manifest = copy.deepcopy(self.manifest)
            manifest[key] = value
            with self.subTest(field=key):
                self.assertFalse(self.check_saved(manifest=manifest)["passed"])
