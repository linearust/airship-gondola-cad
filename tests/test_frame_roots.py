"""Native regressions for solid bearing roots and the M3 U rail foot."""

import math
import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class FrameRootTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.parts import propulsion

        cls.doc = App.newDocument("SolidBearingRoots")
        cls.module = propulsion.build_propulsion_module(cls.doc)

    @classmethod
    def tearDownClass(cls):
        App.closeDocument(cls.doc.Name)

    def test_all_four_roots_have_a_complete_load_path(self):
        from gondola.validation.propulsion import bearing_post_roots_check

        rows = bearing_post_roots_check(self.doc)
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(row["passed"] for row in rows), rows)
        for row in rows:
            self.assertEqual(row["root_section_mm"], [13, 6])
            self.assertEqual(row["root_height_range_mm"], [12.5, 27])
            self.assertLess(row["missing_root_material_mm3"], 1e-7)
            self.assertEqual(row["root_blend_radius_mm"], 1.5)
            self.assertLess(row["missing_root_blend_mm3"], 1e-7)
            self.assertLess(row["unexpected_root_material_mm3"], 1e-7)
        frame = self.doc.PropulsionFixedFrame
        self.assertTrue(frame.Shape.isValid())
        self.assertEqual(len(frame.Shape.Solids), 1)
        self.assertEqual(float(frame.BearingPostWidth), 13)
        self.assertNotIn("BearingPostRootWidth", frame.PropertiesList)
        self.assertNotIn("BearingPostRootHeight", frame.PropertiesList)

    def test_narrowing_each_straight_root_fails_with_the_old_core_intact(self):
        from gondola.validation.propulsion import bearing_post_roots_check

        frame = self.doc.PropulsionFixedFrame
        original = frame.Shape.copy()
        try:
            for centre_y in (-109.75, -40.25, 40.25, 109.75):
                with self.subTest(centre_y=centre_y):
                    # Remove added width while retaining the former 9.6 mm core.
                    cutter = Part.makeBox(
                        1.7, 6, 14.5, App.Vector(4.8, centre_y - 3, 12.5)
                    )
                    self.assertAlmostEqual(
                        original.common(cutter).Volume, 147.9, places=6
                    )
                    frame.Shape = original.cut(cutter)
                    self.doc.recompute()
                    rows = bearing_post_roots_check(self.doc)
                    failed = [row for row in rows if not row["passed"]]
                    self.assertEqual(len(failed), 1, rows)
                    self.assertAlmostEqual(
                        failed[0]["side"] * (75 + failed[0]["post_local_y_mm"]),
                        centre_y,
                    )
                    self.assertAlmostEqual(
                        failed[0]["missing_root_material_mm3"], 147.9, places=6
                    )
        finally:
            frame.Shape = original
            self.doc.recompute()

    def test_reintroduced_taper_fails_with_complete_straight_posts(self):
        from gondola.validation.propulsion import bearing_post_roots_check

        frame = self.doc.PropulsionFixedFrame
        original = frame.Shape.copy()
        try:
            points = [
                App.Vector(x, 106.75, z)
                for x, z in ((-9, 12.5), (9, 12.5), (6.5, 17.5), (-6.5, 17.5))
            ]
            taper = Part.Face(Part.makePolygon(points + points[:1])).extrude(
                App.Vector(0, 6, 0)
            )
            frame.Shape = original.fuse(taper).removeSplitter()
            self.doc.recompute()
            rows = bearing_post_roots_check(self.doc)
            self.assertTrue(
                all(row["missing_root_material_mm3"] < 1e-7 for row in rows)
            )
            failed = [row for row in rows if not row["passed"]]
            self.assertEqual(len(failed), 1, rows)
            # The permitted pair of radius1.5 blends occupies part of the old
            # taper envelope; every other reintroduced wedge is still rejected.
            self.assertAlmostEqual(
                failed[0]["unexpected_root_material_mm3"],
                75 - 2 * 6 * 1.5**2 * (1 - math.pi / 4),
            )
        finally:
            frame.Shape = original
            self.doc.recompute()

    def test_reopened_low_corridor_fails_saved_geometry_root_check(self):
        from gondola.parts import propulsion
        from gondola.validation.propulsion import bearing_post_roots_check

        frame = self.doc.PropulsionFixedFrame
        original = frame.Shape.copy()
        try:
            corridor = Part.makeBox(
                6.4,
                propulsion.BEARING_POST_DEPTH,
                4,
                App.Vector(
                    -3.2,
                    propulsion.PIVOT_HALF_SPAN + propulsion.BEARING_GUIDE_START_Y,
                    propulsion.FOOT_BOTTOM_Z + propulsion.FOOT_THICKNESS,
                ),
            )
            removed_volume = original.common(corridor).Volume
            self.assertGreater(removed_volume, 90)
            self.assertAlmostEqual(removed_volume, corridor.Volume, places=6)
            frame.Shape = original.cut(corridor)
            self.doc.recompute()
            self.assertTrue(frame.Shape.isValid())
            self.assertEqual(len(frame.Shape.Solids), 1)
            rows = bearing_post_roots_check(self.doc)
            failed = [row for row in rows if not row["passed"]]
            self.assertEqual(len(failed), 1, rows)
            self.assertEqual(failed[0]["side"], 1)
            self.assertGreater(failed[0]["post_local_y_mm"], 0)
            self.assertAlmostEqual(
                failed[0]["missing_root_material_mm3"], removed_volume, places=6
            )
        finally:
            frame.Shape = original
            self.doc.recompute()

    def test_output_beam_is_raised_and_five_mm_thick(self):
        from gondola.parts import propulsion

        frame = self.doc.PropulsionFixedFrame.Shape
        outer_y = (
            propulsion.PIVOT_HALF_SPAN
            + propulsion.BEARING_SHOULDER_Y
            + propulsion.BEARING_SHOULDER_THICKNESS
            + 0.5
        )
        beam_section = frame.common(Part.makeBox(20, 230, 1, App.Vector(-10, -115, 8)))
        self.assertAlmostEqual(beam_section.BoundBox.YMin, -outer_y, places=6)
        self.assertAlmostEqual(beam_section.BoundBox.YMax, outer_y, places=6)
        for start_y in (20, -outer_y):
            with self.subTest(start_y=start_y):
                solid_foot = Part.makeBox(
                    18,
                    outer_y - 20,
                    5,
                    App.Vector(-9, start_y, 7.5),
                )
                lower_edges = [
                    edge
                    for edge in solid_foot.Edges
                    if abs(edge.Length - (outer_y - 20)) < 1e-7
                    and all(abs(v.Point.z - 7.5) < 1e-7 for v in edge.Vertexes)
                ]
                solid_foot = solid_foot.makeFillet(0.5, lower_edges)
                self.assertLess(solid_foot.cut(frame).Volume, 1e-7)

    def test_thinning_the_raised_beam_fails_with_all_post_roots_intact(self):
        from gondola.validation.propulsion import bearing_post_roots_check

        frame = self.doc.PropulsionFixedFrame
        original = frame.Shape.copy()
        try:
            loss = Part.makeBox(3, 4, 1, App.Vector(-1.5, 60, 7.5))
            frame.Shape = original.cut(loss)
            self.doc.recompute()
            rows = bearing_post_roots_check(self.doc)
            self.assertTrue(
                all(row["missing_root_material_mm3"] < 1e-7 for row in rows)
            )
            self.assertTrue(
                all(row["unexpected_root_material_mm3"] < 1e-7 for row in rows)
            )
            self.assertTrue(all(not row["passed"] for row in rows))
            for row in rows:
                self.assertAlmostEqual(row["missing_shared_beam_mm3"], 12)
        finally:
            frame.Shape = original
            self.doc.recompute()

    def test_central_seat_is_complete_and_cannot_be_hollowed_for_side_access(self):
        from gondola.parts import servo_bridge

        frame = self.doc.PropulsionFixedFrame.Shape
        bridge = self.doc.ServoDriveBridge.Shape
        support = Part.makeBox(
            40,
            12,
            servo_bridge.SEAT_Z - 9.7,
            App.Vector(-20, -6, 9.7),
        )
        contact = Part.makePlane(40, 12, App.Vector(-20, -6, servo_bridge.SEAT_Z))
        self.assertLess(support.cut(frame).Volume, 1e-7)
        self.assertAlmostEqual(contact.common(frame).Area, 480, places=5)
        self.assertAlmostEqual(contact.common(bridge).Area, 480, places=5)
        self.assertLess(frame.common(bridge).Volume, 1e-7)

    def test_ten_mm_load_zones_keep_two_mm_stock_beyond_loaded_annuli(
        self,
    ):
        from gondola.parts import propulsion

        frame = self.doc.PropulsionFixedFrame.Shape
        offset = propulsion.RAIL_BOLT_OFFSET_X
        length = propulsion.RAIL_CONTACT_LENGTH
        foot = Part.makeBox(10, 12, 11, App.Vector(-5, -6, 1.5))
        foot = foot.cut(Part.makeBox(10, 2.5, 8.2, App.Vector(-5, -1.25, 1.5)))
        foot = foot.cut(
            Part.makeCylinder(1.7, 14, App.Vector(0, -7, 6), App.Vector(0, 1, 0))
        )
        for side in (-1, 1):
            seated = foot.copy()
            seated.translate(App.Vector(side * offset, 0, 0))
            self.assertLess(seated.cut(frame).Volume, 1e-7)
        self.assertAlmostEqual(offset, 15)
        self.assertAlmostEqual(length / 2 - offset - 3, 2)
        self.assertAlmostEqual(length, 40)
        connection = Part.makeBox(4, 4, 11, App.Vector(5, -5.25, 1.5))
        self.assertLess(connection.cut(frame).Volume, 1e-7)

    def test_side_bore_fill_does_not_fill_the_web_passage_and_frame_lifts(self):
        from gondola.parts import rail
        from gondola.validation.propulsion import (
            frame_rail_bore_filled,
            vertical_frame_release_check,
        )

        frame = self.doc.PropulsionFixedFrame.Shape
        filled = frame_rail_bore_filled(frame)
        rail_shape = rail.rail_shape()
        rail_shape.translate(App.Vector(14, 0, 0))
        self.assertLess(frame.cut(filled).Volume, 1e-7)
        self.assertLess(filled.common(rail_shape).Volume, 1e-7)
        result = vertical_frame_release_check(frame, rail_shape)
        self.assertTrue(result["passed"], result)
        self.assertLess(
            result["lower_frame_path"]["lower_frame_outside_envelope_mm3"], 1e-7
        )
        regions = result["lower_frame_path"]["regions"]
        self.assertEqual(len(regions), 3)
        self.assertTrue(all(row["passed"] for row in regions))
        self.assertEqual(
            regions[0]["segments"][0]["method"],
            "continuous planar/coaxial-cylinder face-prism union",
        )

    def test_connector_plate_keeps_bulkhead_support_and_shared_clamp(self):
        from gondola.parts import servo_bridge
        from gondola.validation.servo_module import bridge_joint_check

        bridge = self.doc.ServoDriveBridge.Shape
        centre = Part.makeBox(
            28.8,
            5,
            2.5,
            App.Vector(-14.4, -2.5, servo_bridge.CONNECTOR_PLATE_BOTTOM_Z),
        )
        self.assertLess(centre.cut(bridge).Volume, 1e-7)
        self.assertEqual(len(bridge.Solids), 1)
        result = bridge_joint_check(self.doc, self.module)
        self.assertTrue(result["passed"], result)


if __name__ == "__main__":
    unittest.main()
