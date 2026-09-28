"""Export coordinates preserve shape while reducing STL float32 rounding."""

import tempfile
import unittest
from pathlib import Path

try:
    import FreeCAD as App
    import Mesh
    import Part
except ImportError:
    App = Mesh = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class PrintOriginTests(unittest.TestCase):
    def setUp(self):
        self.existing = set(App.listDocuments())
        self.doc = App.newDocument("PrintOriginRegression")

    def tearDown(self):
        for name in set(App.listDocuments()) - self.existing:
            App.closeDocument(name)

    def part(self, name, shape, angle=0):
        obj = self.doc.addObject("Part::Feature", name)
        obj.Shape = shape
        obj.addProperty("App::PropertyRotation", "PrintRotation")
        obj.PrintRotation = App.Rotation(App.Vector(0, 0, 1), angle)
        return obj

    def test_export_centres_xy_and_seats_z_without_mutating_native_part(self):
        from gondola.print_export import print_shape

        obj = self.part(
            "OffsetBox", Part.makeBox(40, 20, 3, App.Vector(200, -80, 7)), 45
        )
        original = obj.Shape.copy()
        exported = print_shape(obj)
        bounds = exported.optimalBoundingBox(False, False)
        self.assertAlmostEqual(bounds.XMin + bounds.XMax, 0)
        self.assertAlmostEqual(bounds.YMin + bounds.YMax, 0)
        self.assertAlmostEqual(bounds.ZMin, 0)
        self.assertAlmostEqual(exported.Volume, original.Volume)
        rotated = original.copy()
        rotated.rotate(App.Vector(), App.Vector(0, 0, 1), 45)
        rotated.translate(exported.CenterOfMass - rotated.CenterOfMass)
        self.assertLess(rotated.cut(exported).Volume, 1e-6)
        self.assertLess(exported.cut(rotated).Volume, 1e-6)
        self.assertLess(original.cut(obj.Shape).Volume, 1e-6)
        self.assertLess(obj.Shape.cut(original).Volume, 1e-6)

    def test_overview_keeps_positive_nonoverlapping_grid_for_centred_exports(self):
        from gondola.print_export import export_print_parts

        parts = [
            self.part("First", Part.makeBox(40, 20, 3)),
            self.part("Second", Part.makeBox(12, 8, 2)),
            self.part("NextRow", Part.makeBox(340, 5, 2)),
        ]
        with tempfile.TemporaryDirectory() as directory:
            export_print_parts(self.doc, parts, [], directory, "origin")
            layout = App.getDocument("GondolaPrintParts")
            first, second = layout.First.Shape.BoundBox, layout.Second.Shape.BoundBox
            self.assertAlmostEqual(first.XMin, 0)
            self.assertAlmostEqual(first.YMin, 0)
            self.assertAlmostEqual(second.YMin, 0)
            self.assertAlmostEqual(second.XMin - first.XMax, 15)
            third = layout.NextRow.Shape.BoundBox
            self.assertAlmostEqual(third.XMin, 0)
            self.assertAlmostEqual(third.YMin - first.YMax, 15)
            for obj, item in zip(parts, (layout.First, layout.Second, layout.NextRow)):
                shifted = obj.Shape.copy()
                shifted.translate(item.Shape.CenterOfMass - shifted.CenterOfMass)
                self.assertLess(shifted.cut(item.Shape).Volume, 1e-6)
                self.assertLess(item.Shape.cut(shifted).Volume, 1e-6)

    def test_rail_stl_matches_reopened_native_without_relaxing_surface_tolerance(self):
        from gondola.parts import rail
        from gondola.print_export import mesh_from_shape, print_shape
        from gondola.validation.geometry import compare_mesh_surfaces

        obj = self.part("Rail", rail.rail_shape(), 45)
        self.doc.recompute()
        with tempfile.TemporaryDirectory() as directory:
            cad_path = Path(directory) / "rail.FCStd"
            mesh_path = Path(directory) / "rail.stl"
            mesh_from_shape(print_shape(obj)).write(str(mesh_path))
            self.doc.saveAs(str(cad_path))
            App.closeDocument(self.doc.Name)
            restored = App.openDocument(str(cad_path), hidden=True)
            actual = Mesh.Mesh(str(mesh_path))
            expected = mesh_from_shape(print_shape(restored.Rail))
            result = compare_mesh_surfaces(actual, expected)
            self.assertTrue(result["passed"], result)
            self.assertEqual(result["plane_tolerance_mm"], 1e-5)
            self.assertTrue(actual.isSolid())
            self.assertEqual(actual.countComponents(), 1)


if __name__ == "__main__":
    unittest.main()
