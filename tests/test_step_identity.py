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
    def test_single_solid_container_wrappers_are_accepted(self):
        from gondola.print_export import print_solid_comparison

        original = Part.makeBox(10, 10, 10)
        for candidate in (
            original.copy(),
            Part.makeCompound([original]),
            Part.makeCompound([Part.makeCompound([original])]),
        ):
            with self.subTest(shape_type=candidate.ShapeType):
                self.assertTrue(
                    print_solid_comparison(original, candidate, 1e-5)["passed"]
                )

    def test_loose_geometry_inside_solid_bounds_is_not_printable(self):
        from gondola.print_export import print_solid_comparison

        original = Part.makeBox(10, 10, 10)
        extras = (
            Part.Vertex(App.Vector(2, 2, 2)),
            Part.makeLine(App.Vector(2, 2, 2), App.Vector(3, 3, 3)),
            Part.makePlane(1, 1, App.Vector(2, 2, 2)),
        )
        for extra in extras:
            candidate = Part.makeCompound([original, extra])
            # Solid count and validity look correct; points/edges also leave
            # the scalar volume unchanged. A loose face can alter its integral.
            self.assertTrue(candidate.isValid())
            self.assertEqual(len(candidate.Solids), 1)
            if extra.ShapeType in ("Vertex", "Edge"):
                self.assertAlmostEqual(original.Volume, candidate.Volume)
            for first, second in ((original, candidate), (candidate, original)):
                with self.subTest(extra=extra.ShapeType, first=first.ShapeType):
                    self.assertFalse(
                        print_solid_comparison(first, second, 1e-5)["passed"]
                    )

    def test_open_shell_or_multiple_solids_cannot_pass_print_identity(self):
        from gondola.print_export import print_solid_comparison

        original = Part.makeBox(10, 10, 10)
        for candidate in (
            Part.Shape(),
            Part.makeShell(original.Faces[:-1]),
            Part.makeCompound([original, Part.makeBox(1, 1, 1, App.Vector(2, 2, 2))]),
        ):
            with self.subTest(
                shape_type="null" if candidate.isNull() else candidate.ShapeType
            ):
                self.assertFalse(
                    print_solid_comparison(original, candidate, 1e-5)["passed"]
                )

    def test_empty_compound_is_empty_but_face_wire_and_vertex_are_not(self):
        from gondola.print_export import _topologically_empty

        self.assertTrue(_topologically_empty(Part.Shape()))
        self.assertTrue(_topologically_empty(Part.makeCompound([])))
        box = Part.makeBox(2, 2, 2)
        for shape in (box, box.Faces[0], box.Wires[0], box.Vertexes[0]):
            with self.subTest(topology=shape.ShapeType):
                self.assertFalse(_topologically_empty(shape))

    def test_relocated_cavity_does_not_pass_by_equal_volume_and_bounds(self):
        from gondola.print_export import print_solid_comparison

        block = Part.makeBox(10, 10, 10)
        first = block.cut(Part.makeCylinder(0.5, 10, App.Vector(3, 3, 0)))
        second = block.cut(Part.makeCylinder(0.5, 10, App.Vector(7, 7, 0)))
        result = print_solid_comparison(first, second, 1e-5)
        self.assertFalse(result["passed"])
        self.assertLess(result["volume_difference_mm3"], 1e-6)
        self.assertLess(result["bounds_difference_mm"], 1e-6)
        self.assertGreater(result["difference_mm3"], 1)
        self.assertFalse(result["closed_solid_identity_by_empty_cuts"])

    def test_pole_boundaries_survive_orientation_and_step_round_trip(self):
        from gondola.print_export import (
            _boundary_signature,
            print_shape,
            print_solid_comparison,
        )

        block = Part.makeBox(10, 8, 6)
        for label, shape in (
            ("sphere", Part.makeSphere(3)),
            ("rounded_block", block.makeFillet(1, block.Edges)),
        ):
            with self.subTest(shape=label), tempfile.TemporaryDirectory() as folder:
                original = print_shape(
                    SimpleNamespace(
                        Shape=shape,
                        PrintRotation=App.Rotation(App.Vector(1, 2, 3), 37),
                    )
                )
                # A valid pole edge has no readable Curve in this OCC runtime.
                # No sentinel may itself count as an identity signature.
                self.assertIsNone(_boundary_signature(original))
                for suffix in ("brep", "step"):
                    path = str(Path(folder) / (label + "." + suffix))
                    if suffix == "brep":
                        original.exportBrep(path)
                    else:
                        original.exportStep(path)
                    restored = Part.Shape()
                    restored.read(path)
                    result = print_solid_comparison(original, restored, 1e-5)
                    self.assertTrue(result["passed"], result)
                    self.assertEqual(result["method"], "BRep symmetric difference")
                    self.assertTrue(result["closed_solid_identity_by_empty_cuts"])

    def test_two_unreadable_boundaries_do_not_match_by_equal_volume(self):
        from gondola.print_export import _boundary_signature, print_solid_comparison

        sphere = Part.makeSphere(3)
        first = sphere.cut(Part.makeCylinder(0.4, 6, App.Vector(1, 0, -3)))
        second = first.copy()
        second.rotate(App.Vector(), App.Vector(0, 0, 1), 180)
        shapes = (first, second)
        self.assertTrue(all(shape.isValid() for shape in shapes))
        self.assertTrue(all(_boundary_signature(shape) is None for shape in shapes))
        result = print_solid_comparison(*shapes, 1e-5)
        self.assertLess(result["volume_difference_mm3"], 1e-6)
        self.assertLess(result["bounds_difference_mm"], 1e-6)
        self.assertGreater(result["difference_mm3"], 1)
        self.assertFalse(result["passed"])
        self.assertFalse(result["closed_solid_identity_by_empty_cuts"])

    def test_small_real_material_loss_is_not_accepted_as_empty(self):
        from gondola.print_export import print_solid_comparison

        original = Part.makeBox(10, 10, 10)
        damaged = original.cut(Part.makeBox(0.02, 0.02, 0.1, App.Vector(5, 5, 0)))
        result = print_solid_comparison(original, damaged, 1e-5)
        self.assertFalse(result["passed"])
        self.assertLess(result["bounds_difference_mm"], 1e-6)
        self.assertGreater(result["difference_mm3"], 1e-5)
        self.assertGreater(result["volume_difference_mm3"], 1e-5)
        self.assertFalse(result["closed_solid_identity_by_empty_cuts"])

    def test_fixed_frame_step_round_trip_preserves_closed_solid(self):
        from gondola.parts.propulsion import fixed_frame_shape
        from gondola.print_export import (
            _topologically_empty,
            print_shape,
            print_solid_comparison,
        )

        original = print_shape(
            SimpleNamespace(
                Shape=fixed_frame_shape(),
                PrintRotation=App.Rotation(App.Vector(0, 0, 1), 45),
            )
        )
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / "fixed_frame.step")
            original.exportStep(path)
            restored = Part.Shape()
            restored.read(path)
        result = print_solid_comparison(original, restored, 1e-5)
        self.assertTrue(result["passed"])
        self.assertTrue(restored.isValid())
        self.assertEqual(len(restored.Solids), 1)
        self.assertLess(result["difference_mm3"], 1e-5)
        self.assertLess(result["bounds_difference_mm"], 1e-5)
        # A simpler frame may pass the boundary-signature fast path. Prove the
        # round trip independently instead of requiring one comparison branch.
        for difference in (original.cut(restored), restored.cut(original)):
            self.assertTrue(_topologically_empty(difference))
        self.assertEqual(
            result["volume_difference_mm3"], abs(original.Volume - restored.Volume)
        )


if __name__ == "__main__":
    unittest.main()
