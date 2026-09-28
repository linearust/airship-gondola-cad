"""Exercise STL surface identity without requiring the FreeCAD runtime."""

import unittest
from types import SimpleNamespace

from gondola.validation.geometry import compare_mesh_surfaces


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

    def test_rail_float32_retriangulation_uses_coordinate_rounding_bound(self):
        # Actual STL/native rail facets, not a hand-tuned tolerance example.
        # Y >256mm has twice the float32 spacing of X <256mm.
        a = (242.2854766845703, 256.1641540527344, 1.1789947748184204)
        b = (242.30499267578125, 256.1836853027344, 1.1698462963104248)
        c = (242.32411193847656, 256.2027893066406, 1.15910804271698)
        d = (242.34274291992188, 256.221435546875, 1.146816372871399)
        result = compare_mesh_surfaces(
            mesh((a, b, c), (a, c, d)), mesh((a, b, d), (b, c, d))
        )
        self.assertTrue(result["passed"], result)
        self.assertTrue(result["exact_serialized_vertex_sets_match"])
        # Twice the 3-axis nearest-rounding-cell radius, without a fitted factor.
        rounding_bound = ((2**-16) ** 2 + (2**-15) ** 2 + (2**-23) ** 2) ** 0.5
        self.assertAlmostEqual(
            result["maximum_rounding_cell_allowance_mm"], rounding_bound
        )
        self.assertEqual(result["plane_tolerance_mm"], 1e-5)

    def test_changed_vertices_cannot_use_retriangulation_rounding_allowance(self):
        square = [
            tuple((x + 240, y + 260, z) for x, y, z in facet.Points)
            for facet in self.square.Facets
        ]
        for displacement in (2e-5, 0.001):
            with self.subTest(displacement=displacement):
                shifted = [
                    tuple((x, y, z + displacement) for x, y, z in triangle)
                    for triangle in square
                ]
                result = compare_mesh_surfaces(mesh(*square), mesh(*shifted))
                self.assertFalse(result["passed"], result)
                self.assertFalse(result["exact_serialized_vertex_sets_match"])
                self.assertEqual(result["maximum_rounding_cell_allowance_mm"], 0)
                self.assertEqual(result["maximum_plane_tolerance_mm"], 1e-5)

    def test_same_vertex_nonplanar_flip_beyond_rounding_bound_is_rejected(self):
        a, b = (240, 260, 0), (241, 260, 0)
        c, d = (241, 261, 0.0001), (240, 261, 0)
        result = compare_mesh_surfaces(
            mesh((a, b, c), (a, c, d)), mesh((a, b, d), (b, c, d))
        )
        self.assertTrue(result["exact_serialized_vertex_sets_match"])
        # The changed diagonal lifts the center by about50nm, exceeding the
        # roughly34nm serialized-coordinate bound, despite identical vertices.
        self.assertGreater(0.0001 / 2, result["maximum_plane_tolerance_mm"])
        self.assertFalse(result["passed"], result)

    def test_shared_vertex_set_does_not_hide_a_missing_face(self):
        a, b = (240, 260, 0), (241, 260, 0)
        c, d, center = (241, 261, 0), (240, 261, 0), (240.5, 260.5, 0)
        triangles = [(a, b, center), (b, c, center), (c, d, center), (d, a, center)]
        for first, second in ((triangles, triangles[1:]), (triangles[1:], triangles)):
            result = compare_mesh_surfaces(mesh(*first), mesh(*second))
            self.assertTrue(result["exact_serialized_vertex_sets_match"])
            self.assertFalse(result["passed"], result)

    def test_far_unchanged_geometry_does_not_enlarge_local_rounding_bound(self):
        raised = (1, 1, 0.00004)
        distant = ((1e6, 0, 0), (1e6 + 1, 0, 0), (1e6, 1, 0))
        first = mesh((self.a, self.b, raised), (self.a, raised, self.d), distant)
        second = mesh((self.a, self.b, self.d), (self.b, raised, self.d), distant)
        result = compare_mesh_surfaces(first, second)
        self.assertTrue(result["exact_serialized_vertex_sets_match"])
        self.assertEqual(result["maximum_plane_tolerance_mm"], 1e-5)
        self.assertFalse(result["passed"], result)

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
