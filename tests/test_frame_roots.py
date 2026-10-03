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

    def test_two_inboard_housings_have_complete_short_web_load_paths(self):
        from gondola.validation.propulsion import bearing_post_roots_check

        rows = bearing_post_roots_check(self.doc)
        self.assertEqual(len(rows), 2)
        self.assertEqual({row["side"] for row in rows}, {-1, 1})
        self.assertTrue(all(row["passed"] for row in rows), rows)
        for row in rows:
            for field in (
                "missing_root_material_mm3",
                "missing_root_blend_mm3",
                "missing_shared_beam_mm3",
                "missing_housing_bed_mm3",
            ):
                self.assertLess(row[field], 1e-7)
        frame = self.doc.PropulsionFixedFrame
        self.assertTrue(frame.Shape.isValid())
        self.assertEqual(len(frame.Shape.Solids), 1)
        self.assertEqual(float(frame.BearingPostWidth), 18)
        # Literal18x19 short webs under each inboard housing, independent of
        # builder constants and report metadata. No outer support remains.
        for centre_y in (-34.5, 34.5):
            root = Part.makeBox(18, 19, 12.5, App.Vector(-9, centre_y - 9.5, 29.5))
            self.assertLess(abs(root.cut(frame.Shape).Volume), 1e-7)
        for side in (-1, 1):
            outer = Part.makeBox(
                30, 60, 60, App.Vector(-15, 60 if side > 0 else -120, 0)
            )
            self.assertLess(abs(outer.common(frame.Shape).Volume), 1e-7)

    def test_narrowing_any_post_fails_with_the_other_web_and_core_intact(self):
        from gondola.validation.propulsion import bearing_post_roots_check

        frame = self.doc.PropulsionFixedFrame
        original = frame.Shape.copy()
        try:
            for centre_y in (-34.5, 34.5):
                with self.subTest(centre_y=centre_y):
                    # Strip1.7mm from one root side; the full14.6mm central core
                    # and the other complete web remain connected.
                    cutter = Part.makeBox(
                        1.7, 19, 12.5, App.Vector(7.3, centre_y - 9.5, 29.5)
                    )
                    self.assertAlmostEqual(
                        original.common(cutter).Volume, 403.75, places=6
                    )
                    frame.Shape = original.cut(cutter)
                    self.doc.recompute()
                    self.assertEqual(len(frame.Shape.Solids), 1)
                    rows = bearing_post_roots_check(self.doc)
                    failed = [row for row in rows if not row["passed"]]
                    self.assertEqual(len(failed), 1, rows)
                    self.assertEqual(failed[0]["side"], 1 if centre_y > 0 else -1)
                    self.assertAlmostEqual(
                        failed[0]["missing_root_material_mm3"], 403.75, places=6
                    )
        finally:
            frame.Shape = original
            self.doc.recompute()

    def test_missing_root_blend_fails_while_all_rectangular_cores_remain(self):
        from gondola.validation.propulsion import bearing_post_roots_check

        frame = self.doc.PropulsionFixedFrame
        original = frame.Shape.copy()
        try:
            # The analytic lower concave quarter circle lies outside the
            # complete18x19 web. Its loss must not hide behind a core check.
            blend = Part.makeBox(18, 1.5, 1.5, App.Vector(-9, 23.5, 29.5)).cut(
                Part.makeCylinder(
                    1.5, 18, App.Vector(-9, 23.5, 31), App.Vector(1, 0, 0)
                )
            )
            expected = 18 * 1.5**2 * (1 - math.pi / 4)
            self.assertAlmostEqual(original.common(blend).Volume, expected, places=6)
            frame.Shape = original.cut(blend)
            rows = bearing_post_roots_check(self.doc)
            self.assertTrue(
                all(row["missing_root_material_mm3"] < 1e-7 for row in rows)
            )
            failed = [row for row in rows if not row["passed"]]
            self.assertEqual(len(failed), 1, rows)
            self.assertEqual(failed[0]["side"], 1)
            self.assertAlmostEqual(
                failed[0]["missing_root_blend_mm3"], expected, places=6
            )
        finally:
            frame.Shape = original
            self.doc.recompute()

    def test_reopened_low_corridor_fails_with_the_frame_still_connected(self):
        from gondola.validation.propulsion import bearing_post_roots_check

        frame = self.doc.PropulsionFixedFrame
        original = frame.Shape.copy()
        try:
            corridor = Part.makeBox(6.4, 6, 4, App.Vector(-3.2, 38, 29.5))
            self.assertAlmostEqual(original.common(corridor).Volume, 153.6, places=6)
            frame.Shape = original.cut(corridor)
            self.doc.recompute()
            self.assertTrue(frame.Shape.isValid())
            self.assertEqual(len(frame.Shape.Solids), 1)
            rows = bearing_post_roots_check(self.doc)
            failed = [row for row in rows if not row["passed"]]
            self.assertEqual(len(failed), 1, rows)
            self.assertEqual(failed[0]["side"], 1)
            self.assertAlmostEqual(
                failed[0]["missing_root_material_mm3"], 153.6, places=6
            )
        finally:
            frame.Shape = original
            self.doc.recompute()

    def test_shared_beam_has_shortened_span_and_nine_point_five_mm_core(self):
        frame = self.doc.PropulsionFixedFrame.Shape
        # This full-height interior slab ties each housing into the pedestal.
        for start_y in (-44, 20):
            core = Part.makeBox(16, 24, 9.5, App.Vector(-8, start_y, 20))
            self.assertLess(abs(core.cut(frame).Volume), 1e-7)
        self.assertAlmostEqual(frame.BoundBox.YMin, -44, places=6)
        self.assertAlmostEqual(frame.BoundBox.YMax, 44, places=6)

    def test_thinning_beam_fails_with_both_paired_housing_roots_intact(self):
        from gondola.validation.propulsion import bearing_post_roots_check

        frame = self.doc.PropulsionFixedFrame
        original = frame.Shape.copy()
        try:
            loss = Part.makeBox(3, 4, 1, App.Vector(-1.5, 20, 20))
            self.assertAlmostEqual(original.common(loss).Volume, 12, places=6)
            frame.Shape = original.cut(loss)
            rows = bearing_post_roots_check(self.doc)
            self.assertTrue(
                all(row["missing_root_material_mm3"] < 1e-7 for row in rows)
            )
            self.assertTrue(all(not row["passed"] for row in rows))
            for row in rows:
                self.assertAlmostEqual(row["missing_shared_beam_mm3"], 12, places=6)
        finally:
            frame.Shape = original
            self.doc.recompute()

    def test_missing_housing_bed_fails_without_touching_posts_or_bolt_passages(self):
        from gondola.validation.propulsion import bearing_post_roots_check

        frame = self.doc.PropulsionFixedFrame
        original = frame.Shape.copy()
        try:
            # Bed stock above the broad web and away from the remaining bolt axis.
            loss = Part.makeBox(3, 3, 1, App.Vector(-1.5, 33, 42.5))
            self.assertAlmostEqual(original.common(loss).Volume, 9, places=6)
            frame.Shape = original.cut(loss)
            rows = bearing_post_roots_check(self.doc)
            self.assertTrue(
                all(row["missing_root_material_mm3"] < 1e-7 for row in rows)
            )
            failed = [row for row in rows if not row["passed"]]
            self.assertEqual(len(failed), 1, rows)
            self.assertEqual(failed[0]["side"], 1)
            self.assertAlmostEqual(failed[0]["missing_housing_bed_mm3"], 9, places=6)
        finally:
            frame.Shape = original
            self.doc.recompute()

    def test_two_standard_shoes_retain_roofs_and_two_mm_bearing_floors(self):
        frame = self.doc.PropulsionFixedFrame.Shape
        for centre in (-14, 14):
            roof = Part.makeBox(16, 10.5, 3, App.Vector(centre - 8, -5.25, 9.5))
            self.assertLess(roof.cut(frame).Volume, 1e-7)
            for y in (-3.25, 1.25):
                floor = Part.makeCylinder(
                    3.1, 2, App.Vector(centre, y, 6), App.Vector(0, 1, 0)
                ).cut(
                    Part.makeCylinder(
                        1.7, 2, App.Vector(centre, y, 6), App.Vector(0, 1, 0)
                    )
                )
                self.assertLess(floor.cut(frame).Volume, 1e-7)
            clear = Part.makeBox(16, 2.5, 7, App.Vector(centre - 8, -1.25, 2.5))
            self.assertLess(clear.common(frame).Volume, 1e-7)

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
        self.assertEqual(
            {row["region"] for row in regions},
            {
                "PropulsionFixedFrameShoe-14",
                "PropulsionFixedFrameShoe14",
            },
        )
        self.assertTrue(all(row["passed"] for row in regions))
        self.assertEqual(
            regions[0]["segments"][0]["method"],
            "continuous planar/coaxial-cylinder face-prism union",
        )


if __name__ == "__main__":
    unittest.main()
