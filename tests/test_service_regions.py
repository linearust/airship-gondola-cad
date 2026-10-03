"""Conservative service stock must cover parts without filling empty corners."""

import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class ServiceRegionTests(unittest.TestCase):
    def test_side_driver_fits_stem_guide_but_retains_handle_approach_obstacle(self):
        from gondola.validation.rail_access import side_driver_clearance
        from gondola.validation.service_geometry import side_driver_shape

        # An off-origin screw locates a narrow guide on its negative-Y side.
        # The accepted stem clears a 4.2 mm bore; the screw head stays untouched.
        screw = Part.makeCylinder(3, 2, App.Vector(17, 8, 23), App.Vector(0, 1, 0))
        guide = Part.makeBox(12, 1, 12, App.Vector(11, -60, 17))
        guide = guide.cut(
            Part.makeCylinder(2.1, 2, App.Vector(17, -60.5, 23), App.Vector(0, 1, 0))
        )
        obstacles = {"screw": screw, "stem_guide": guide}
        clear = side_driver_clearance(screw, obstacles)
        self.assertTrue(clear["passed"], clear)
        self.assertAlmostEqual(side_driver_shape(screw).distToShape(screw)[0], 0.1)

        # This obstruction clears the seated tool and its slender stem, but
        # intersects the wider handle during the declared insertion approach.
        blocker = Part.makeBox(1, 1, 1, App.Vector(22.5, -190, 22.5))
        self.assertLess(side_driver_shape(screw).common(blocker).Volume, 1e-7)
        blocked = side_driver_clearance(screw, {**obstacles, "handle_stop": blocker})
        self.assertFalse(blocked["passed"], blocked)
        self.assertGreater(
            blocked["segments"][0]["intersection_mm3"]["handle_stop"], 0.1
        )

    def test_separate_stock_preserves_open_gap_but_rejects_omitted_part(self):
        from gondola.validation.service_geometry import contained_region_paths

        regions = [
            ("left", Part.makeBox(1, 1, 1)),
            ("right", Part.makeBox(1, 1, 1, App.Vector(2, 0, 0))),
        ]
        shape = Part.makeCompound([part for _, part in regions])
        obstacles = {"between_regions": Part.makeBox(0.5, 1, 3, App.Vector(1.25, 0, 0))}
        waypoints = [(0, 0, 0), (0, 0, 2)]
        result = contained_region_paths(shape, regions, waypoints, obstacles)
        self.assertTrue(result["passed"], result)
        self.assertEqual(
            [row["region"] for row in result["regions"]], ["left", "right"]
        )
        self.assertLess(result["uncovered_volume_mm3"], 1e-7)
        omitted = contained_region_paths(shape, regions[:1], waypoints, obstacles)
        self.assertFalse(omitted["passed"])
        self.assertAlmostEqual(omitted["uncovered_volume_mm3"], 1)

    def test_intermediate_obstacle_cannot_pass_clear_endpoints(self):
        from gondola.validation.service_geometry import contained_region_paths

        part = Part.makeBox(1, 1, 1)
        result = contained_region_paths(
            part,
            [("part", part)],
            [(0, 0, 0), (10, 0, 0)],
            {"midpath": Part.makeBox(0.5, 1, 1, App.Vector(4, 0, 0))},
        )
        self.assertFalse(result["passed"])
        self.assertGreater(
            result["regions"][0]["segments"][0]["intersection_mm3"]["midpath"], 0.4
        )
        self.assertEqual(part.BoundBox.XMin, 0)

    def test_empty_stock_or_path_cannot_pass(self):
        from gondola.validation.service_geometry import contained_region_paths

        part = Part.makeBox(1, 1, 1)
        for regions, points in (
            ([], [(0, 0, 0), (0, 0, 2)]),
            ([("part", part)], [(0, 0, 0)]),
        ):
            with self.subTest(regions=len(regions), waypoints=len(points)):
                self.assertFalse(
                    contained_region_paths(part, regions, points, {})["passed"]
                )
