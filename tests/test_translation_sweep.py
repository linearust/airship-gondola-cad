"""Continuous sweeps retain concavities and correctly erode enclosed voids."""

import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires FreeCAD")
class TranslationSweepTests(unittest.TestCase):
    def assert_same_volume(self, actual, expected):
        self.assertTrue(actual.isValid())
        self.assertLess(abs(actual.cut(expected).Volume), 1e-7)
        self.assertLess(abs(expected.cut(actual).Volume), 1e-7)

    def test_open_concavity_remains_open_in_both_directions(self):
        from gondola.validation.geometry import translation_sweep

        # Union distributes over a translation sweep, so extending each of
        # these axis-aligned boxes gives an independent analytical reference.
        base = Part.makeBox(6, 2, 2)
        arms = [Part.makeBox(2, 6, 2, App.Vector(x, 0, 0)) for x in (0, 4)]
        body = base.multiFuse(arms).removeSplitter()
        for distance in (-1, 1):
            start = min(distance, 0)
            expected = Part.makeBox(7, 2, 2, App.Vector(start, 0, 0)).multiFuse(
                [Part.makeBox(3, 6, 2, App.Vector(x + start, 0, 0)) for x in (0, 4)]
            )
            with self.subTest(distance=distance):
                swept, method = translation_sweep(body, (distance, 0, 0))
                self.assertIn("face-prism", method)
                self.assert_same_volume(swept, expected)

    def test_inner_boundary_normals_sweep_an_enclosed_cavity(self):
        from gondola.validation.geometry import translation_sweep

        body = Part.makeBox(6, 6, 6).cut(Part.makeBox(2, 2, 2, App.Vector(2, 2, 2)))
        for distance in (1, 3):
            expected = Part.makeBox(6 + distance, 6, 6)
            if distance < 2:
                expected = expected.cut(
                    Part.makeBox(2 - distance, 2, 2, App.Vector(2 + distance, 2, 2))
                )
            with self.subTest(distance=distance):
                swept, method = translation_sweep(body, (distance, 0, 0))
                self.assertIn("face-prism", method)
                self.assert_same_volume(swept, expected)

    def test_oblique_sweep_retains_the_actual_hexagonal_footprint(self):
        from gondola.validation.geometry import translation_sweep

        outline = [(0, 0), (1, 0), (3, 1), (3, 2), (2, 2), (0, 1), (0, 0)]
        expected = Part.Face(
            Part.makePolygon([App.Vector(x, y, 0) for x, y in outline])
        ).extrude(App.Vector(0, 0, 1))
        swept, _ = translation_sweep(Part.makeBox(1, 1, 1), (2, 1, 0))
        self.assert_same_volume(swept, expected)

    def test_disconnected_solids_merge_only_where_their_paths_overlap(self):
        from gondola.validation.geometry import translation_sweep

        body = Part.makeCompound(
            [Part.makeBox(1, 1, 1, App.Vector(x, 0, 0)) for x in (0, 2)]
        )
        swept, _ = translation_sweep(body, (1.5, 0, 0))
        self.assert_same_volume(swept, Part.makeBox(4.5, 1, 1))


@unittest.skipIf(App is None, "Requires FreeCAD")
class TranslationCertificateTests(unittest.TestCase):
    def test_curved_open_half_can_clear_a_shaft_despite_bounding_prism_overlap(self):
        from gondola.validation.geometry import (
            certify_translation_clearance,
            intersection_volume,
            translation_sweep,
        )

        axis = App.Vector(0, 1, 0)
        outer = Part.makeCylinder(2, 2, App.Vector(), axis)
        bore = Part.makeCylinder(1.2, 2, App.Vector(), axis)
        half = outer.cut(bore).common(Part.makeBox(4, 2, 1.7, App.Vector(-2, 0, -2)))
        shaft = Part.makeCylinder(1, 2, App.Vector(), axis)
        swept, method = translation_sweep(half, (0, 0, -3))
        self.assertIn("conservative", method)
        self.assertGreater(intersection_volume(swept, shaft), 0)
        result = certify_translation_clearance(half, (0, 0, -3), {"shaft": shaft})
        self.assertTrue(result["passed"], result)
        self.assertGreater(result["certified_intervals"], 1)

    def test_clear_endpoints_do_not_hide_a_thin_midpath_obstacle(self):
        from gondola.validation.geometry import certify_translation_clearance

        result = certify_translation_clearance(
            Part.makeBox(0.1, 1, 1),
            (10, 0, 0),
            {"thin_wall": Part.makeBox(0.02, 1, 1, App.Vector(5.37, 0, 0))},
        )
        self.assertFalse(result["passed"])
        self.assertEqual(result["collision"]["obstacle"], "thin_wall")
        self.assertGreater(result["collision"]["intersection_mm3"], 0)

    def test_a_solid_nested_inside_an_obstacle_cannot_be_certified_clear(self):
        from gondola.validation.geometry import certify_translation_clearance

        result = certify_translation_clearance(
            Part.makeBox(1, 1, 1, App.Vector(3, 3, 3)),
            (1, 0, 0),
            {"enclosure": Part.makeBox(10, 10, 10)},
        )
        self.assertFalse(result["passed"])
        self.assertEqual(result["collision"]["obstacle"], "enclosure")

    def test_uncertified_subdivision_or_work_limits_fail_closed(self):
        from gondola.validation.geometry import certify_translation_clearance

        moving = Part.makeBox(1, 1, 1)
        obstacles = {"near_wall": Part.makeBox(1, 1, 1, App.Vector(0, 1.1, 0))}
        for limit in ({"max_depth": 0}, {"max_evaluations": 1}):
            with self.subTest(limit=limit):
                result = certify_translation_clearance(
                    moving, (1, 0, 0), obstacles, **limit
                )
                self.assertFalse(result["passed"])
                self.assertIn("unresolved", result)


if __name__ == "__main__":
    unittest.main()
