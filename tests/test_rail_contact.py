"""Direct rail roof, local trim and flexure load-path regressions."""

import unittest

try:
    import FreeCAD as App
except ImportError:
    App = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class RailContactTests(unittest.TestCase):
    def test_full_rail_has_all_twelve_thin_open_flexures(self):
        from gondola.parts import rail

        report = rail.flex_relief_check()
        self.assertTrue(report["passed"], report)
        self.assertEqual(len(report["rows"]), 12)
        self.assertFalse(rail.fit_contract()["shoe_required"])
        self.assertFalse(rail.fit_contract()["unbolted_nut_captured"])

    def test_hidden_roof_across_a_flex_gap_is_rejected(self):
        import Part

        from gondola.parts import rail

        shape = rail.rail_shape().fuse(
            Part.makeBox(
                3,
                rail.TRACK_WIDTH,
                0.2,
                App.Vector(22.5, rail.TRACK_CENTRES_Y[0] - rail.TRACK_WIDTH / 2, 6.8),
            )
        )
        report = rail.flex_relief_check(shape)
        self.assertFalse(report["passed"])
        self.assertGreater(max(row["blocked_relief_mm3"] for row in report["rows"]), 4)

    def test_broken_flexure_floor_is_rejected(self):
        import Part

        from gondola.parts import rail

        shape = rail.rail_shape().cut(
            Part.makeBox(
                1,
                rail.FLEXURE_WIDTH + 0.2,
                2,
                App.Vector(
                    23.5, rail.TRACK_CENTRES_Y[0] - rail.FLEXURE_WIDTH / 2 - 0.1, -0.1
                ),
            )
        )
        result = rail.flex_relief_check(shape)
        self.assertFalse(result["passed"])
        self.assertGreater(max(row["missing_base_mm3"] for row in result["rows"]), 1)

    def test_roof_and_guide_walls_support_both_clamps_at_full_trim(self):
        from gondola.parts import rail
        from gondola.validation.assembly import roof_load_path_check

        shape = rail.bay_shape()
        for x in (-rail.TRIM_LIMIT, 0, rail.TRIM_LIMIT):
            with self.subTest(x=x):
                contact = rail.rail_support_check(shape, x)
                self.assertTrue(contact["passed"], contact)
                self.assertGreater(contact["filled_plate_contact_end_margin_mm"], 1.5)
                load = roof_load_path_check(shape, x)
                self.assertTrue(load["passed"], load)
                self.assertEqual(len(load["rows"]), 2)

    def test_trim_cannot_cross_into_flexible_or_unsupported_region(self):
        from gondola.parts import rail

        shape = rail.rail_shape()
        for x in (rail.TRIM_LIMIT + 0.1, 24):
            with self.subTest(x=x):
                self.assertFalse(rail.rail_support_check(shape, x)["passed"])

    def test_hidden_roof_void_breaking_clamp_load_path_is_rejected(self):
        import Part

        from gondola.parts import rail
        from gondola.validation.assembly import roof_load_path_check

        y = rail.TRACK_CENTRES_Y[0]
        missing = rail.bay_shape().cut(
            Part.makeBox(2, 0.5, 0.5, App.Vector(-1, y + 1.4, 5.3))
        )
        result = roof_load_path_check(missing, 0)
        self.assertFalse(result["passed"], result)
        self.assertGreater(result["rows"][0]["missing_load_material_mm3"], 0.4)

    def test_missing_guide_sidewall_cannot_claim_a_roof_load_path(self):
        import Part

        from gondola.parts import rail
        from gondola.validation.assembly import roof_load_path_check

        y = rail.TRACK_CENTRES_Y[0]
        missing = rail.bay_shape().cut(Part.makeBox(4, 2, 1, App.Vector(-2, y + 2, 2)))
        self.assertFalse(roof_load_path_check(missing, 0)["passed"])

    def test_obstructed_top_slot_is_rejected(self):
        import Part

        from gondola.parts import rail

        y = rail.TRACK_CENTRES_Y[0]
        blocked = rail.bay_shape().fuse(
            Part.makeBox(
                1, rail.SLOT_WIDTH, 1, App.Vector(-0.5, y - rail.SLOT_WIDTH / 2, 5.5)
            )
        )
        self.assertFalse(rail.rail_support_check(blocked, 0)["passed"])


if __name__ == "__main__":
    unittest.main()
