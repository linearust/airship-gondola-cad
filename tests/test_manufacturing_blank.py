"""Do not export an illustrative machined hole pattern as purchased-horn data."""

import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires FreeCAD")
class ManufacturingBlankTests(unittest.TestCase):
    def setUp(self):
        self.doc = App.newDocument("ManufacturingBlankTests")
        self.addCleanup(App.closeDocument, self.doc.Name)
        self.part = self.doc.addObject("Part::Feature", "Adapter")
        blank = Part.makeBox(12, 8, 4)
        self.part.Shape = blank.cut(Part.makeCylinder(1, 4, App.Vector(6, 4, 0)))
        self.part.addProperty("Part::PropertyPartShape", "PrintBlankShape")
        self.part.PrintBlankShape = blank
        self.part.addProperty("App::PropertyString", "AfterPrintPreparation")
        self.part.AfterPrintPreparation = "Transfer holes from the measured part."
        self.part.addProperty("App::PropertyRotation", "PrintRotation")

    def test_export_keeps_undrilled_stock_separate_from_assembly(self):
        from gondola.print_export import print_shape

        exported = print_shape(self.part)
        self.assertAlmostEqual(exported.Volume, 12 * 8 * 4)
        self.assertGreater(exported.Volume, self.part.Shape.Volume)

    def test_missing_stock_or_missing_preparation_cannot_export(self):
        from gondola.print_export import print_shape

        original = self.part.PrintBlankShape.copy()
        self.part.PrintBlankShape = Part.makeBox(11, 8, 4)
        with self.assertRaises(ValueError):
            print_shape(self.part)
        self.part.PrintBlankShape = original
        self.part.AfterPrintPreparation = ""
        with self.assertRaises(ValueError):
            print_shape(self.part)

    def test_baseline_detects_changed_blank_with_unchanged_assembly(self):
        from gondola.validation.baseline import compare_shape_objects

        other = self.doc.addObject("Part::Feature", "SameAssembly")
        other.Shape = self.part.Shape.copy()
        other.addProperty("Part::PropertyPartShape", "PrintBlankShape")
        other.PrintBlankShape = Part.makeBox(13, 8, 4)
        other.addProperty("App::PropertyString", "AfterPrintPreparation")
        other.AfterPrintPreparation = self.part.AfterPrintPreparation
        result = compare_shape_objects(self.part, other)
        self.assertLess(result["local_shape"]["difference_mm3"], 1e-5)
        self.assertFalse(result["print_blank_unchanged"])
        self.assertFalse(result["passed"])


if __name__ == "__main__":
    unittest.main()
