"""STEP identity must distinguish empty topology from equal scalar volumes."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class StepIdentityTests(unittest.TestCase):
    def test_empty_compound_is_empty_but_face_wire_and_vertex_are_not(self):
        from gondola.print_export import _topologically_empty

        self.assertTrue(_topologically_empty(Part.Shape()))
        self.assertTrue(_topologically_empty(Part.makeCompound([])))
        box = Part.makeBox(2, 2, 2)
        for shape in (box, box.Faces[0], box.Wires[0], box.Vertexes[0]):
            with self.subTest(topology=shape.ShapeType):
                self.assertFalse(_topologically_empty(shape))

    def test_relocated_cavity_does_not_pass_by_equal_volume_and_bounds(self):
        from gondola.print_export import geometry_comparison

        block = Part.makeBox(10, 10, 10)
        first = block.cut(Part.makeCylinder(0.5, 10, App.Vector(3, 3, 0)))
        second = block.cut(Part.makeCylinder(0.5, 10, App.Vector(7, 7, 0)))
        result = geometry_comparison(first, second)
        self.assertLess(result["volume_difference_mm3"], 1e-6)
        self.assertLess(result["bounds_difference_mm"], 1e-6)
        self.assertGreater(result["difference_mm3"], 1)
        self.assertFalse(result["closed_solid_identity_by_empty_cuts"])

    def test_small_real_material_loss_is_not_accepted_as_empty(self):
        from gondola.print_export import geometry_comparison

        original = Part.makeBox(10, 10, 10)
        damaged = original.cut(Part.makeBox(0.02, 0.02, 0.1, App.Vector(5, 5, 0)))
        result = geometry_comparison(original, damaged)
        self.assertLess(result["bounds_difference_mm"], 1e-6)
        self.assertGreater(result["difference_mm3"], 1e-5)
        self.assertGreater(result["volume_difference_mm3"], 1e-5)
        self.assertFalse(result["closed_solid_identity_by_empty_cuts"])

    def test_fixed_frame_step_round_trip_preserves_closed_solid(self):
        from gondola.parts.propulsion import integral_frame_shape
        from gondola.print_export import geometry_comparison, print_shape

        original = print_shape(
            SimpleNamespace(
                Shape=integral_frame_shape(),
                PrintRotation=App.Rotation(App.Vector(0, 0, 1), 45),
            )
        )
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / "fixed_frame.step")
            original.exportStep(path)
            restored = Part.Shape()
            restored.read(path)
        result = geometry_comparison(original, restored)
        self.assertTrue(restored.isValid())
        self.assertEqual(len(restored.Solids), 1)
        self.assertLess(result["difference_mm3"], 1e-5)
        self.assertLess(result["bounds_difference_mm"], 1e-5)
        self.assertTrue(result["closed_solid_identity_by_empty_cuts"])
        self.assertEqual(
            result["volume_difference_mm3"], abs(original.Volume - restored.Volume)
        )


if __name__ == "__main__":
    unittest.main()
