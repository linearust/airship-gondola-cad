"""Exercise STL surface identity without requiring the FreeCAD runtime."""

import unittest
from types import SimpleNamespace

from gondola.validation.geometry import compare_mesh_surfaces, mesh_triangle_signature


def mesh(*triangles):
    return SimpleNamespace(
        Facets=[SimpleNamespace(Points=triangle) for triangle in triangles]
    )


class MeshSurfaceTests(unittest.TestCase):
    def setUp(self):
        self.a = (0, 0, 0)
        self.b = (1, 0, 0)
        self.c = (1, 1, 0)
        self.d = (0, 1, 0)
        self.square = mesh((self.a, self.b, self.c), (self.a, self.c, self.d))

    def test_planar_diagonal_change_preserves_surface(self):
        other = mesh((self.a, self.b, self.d), (self.b, self.c, self.d))
        self.assertNotEqual(
            mesh_triangle_signature(self.square), mesh_triangle_signature(other)
        )
        result = compare_mesh_surfaces(self.square, other)
        self.assertTrue(result["passed"], result)
        self.assertEqual(result["actual_retriangulated_facets"], 2)

    def test_planar_subdivision_and_vertex_order_preserve_surface(self):
        center = (0.5, 0.5, 0)
        divided = mesh(
            (center, self.b, self.a),
            (self.c, self.b, center),
            (center, self.c, self.d),
            (self.d, self.a, center),
        )
        self.assertTrue(compare_mesh_surfaces(self.square, divided)["passed"])

    def test_float32_skinny_facets_allow_equivalent_retriangulation(self):
        # Quantized points from the diagonal planar face of PropulsionFixedFrame.
        # Skinny facet normals differ slightly after STL serialization.
        a = (86.683716, 81.026863, 2.718249)
        b = (86.743851, 81.086998, 2.790715)
        c = (86.800865, 81.144012, 2.868055)
        d = (86.854568, 81.197716, 2.95)
        actual = mesh((a, b, d), (b, c, d))
        expected = mesh((a, b, c), (a, c, d))
        result = compare_mesh_surfaces(actual, expected)
        self.assertTrue(result["passed"], result)

    def test_missing_or_extra_surface_is_rejected_in_either_direction(self):
        missing = mesh((self.a, self.b, self.c))
        for actual, expected in ((self.square, missing), (missing, self.square)):
            with self.subTest(actual=actual):
                self.assertFalse(compare_mesh_surfaces(actual, expected)["passed"])

    def test_duplicate_coverage_cannot_compensate_for_a_hole(self):
        full = mesh((self.a, self.b, self.d))
        midpoint = (0.5, 0.5, 0)
        half = (self.a, self.b, midpoint)
        doubled_half = mesh(half, half)
        result = compare_mesh_surfaces(full, doubled_half)
        self.assertFalse(result["passed"])
        self.assertTrue(result["uncovered_actual_triangles"])

    def test_nonplanar_diagonal_change_is_rejected_with_same_vertices(self):
        raised = (1, 1, 0.01)
        first = mesh((self.a, self.b, raised), (self.a, raised, self.d))
        second = mesh((self.a, self.b, self.d), (self.b, raised, self.d))
        self.assertFalse(compare_mesh_surfaces(first, second)["passed"])

    def test_plane_displacement_is_limited_to_serialization_tolerance(self):
        for displacement, accepted in ((5e-6, True), (2e-5, False), (0.001, False)):
            with self.subTest(displacement=displacement):
                triangles = [
                    tuple((x, y, z + displacement) for x, y, z in facet.Points)
                    for facet in self.square.Facets
                ]
                displaced = mesh(*triangles)
                self.assertEqual(
                    compare_mesh_surfaces(self.square, displaced)["passed"], accepted
                )

    def test_empty_mesh_cannot_supply_surface_evidence(self):
        self.assertFalse(compare_mesh_surfaces(mesh(), mesh())["passed"])


if __name__ == "__main__":
    unittest.main()
