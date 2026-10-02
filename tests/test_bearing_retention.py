"""Native negative controls for the paired inboard split-bearing housing."""

import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class ServiceableBearingCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.cad import translated_shape
        from gondola.parts import bearing_retention

        cls.b = bearing_retention
        cls.lower = translated_shape(bearing_retention.cup_shape(), y=28, z=50)
        cls.cap = translated_shape(bearing_retention.cap_shape(), y=28, z=50)
        cls.shaft = Part.makeCylinder(
            1.5, 42, App.Vector(0, 13, 50), App.Vector(0, 1, 0)
        )
        for start, length in ((13, 5), (44, 11)):
            cls.shaft = cls.shaft.cut(
                Part.makeBox(3, length, 4, App.Vector(1, start, 48))
            )

    def bearing(self, centre=28):
        origin = App.Vector(0, centre - 1.25, 50)
        return Part.makeCylinder(3, 2.5, origin, App.Vector(0, 1, 0)).cut(
            Part.makeCylinder(1.5, 2.5, origin, App.Vector(0, 1, 0))
        )

    def check(self, centre=28, **changes):
        from gondola.validation.bearing_capture import split_bearing_stack_check

        values = dict(
            bearing=self.bearing(centre),
            shaft=self.shaft,
            frame=self.lower,
            cap=self.cap,
            centre_y=centre,
            negative_travel=0.5,
            positive_travel=0.5,
        )
        values.update(changes)
        return split_bearing_stack_check(**values)

    def test_housing_cap_and_coupon_are_valid_single_solids(self):
        for shape in (self.lower, self.cap, self.b.coupon_shape()):
            self.assertTrue(shape.isValid())
            self.assertEqual(len(shape.Solids), 1)
        self.assertTrue(self.b.geometry_check()["passed"])

    def test_both_bearings_have_round_guides_and_two_outer_ring_shoulders(self):
        for centre in (28, 41):
            result = self.check(centre)
            self.assertTrue(result["passed"], result)
            self.assertEqual(result["bearing_endplay_each_direction_mm"], 0.25)
            self.assertAlmostEqual(
                result["minimum_shaft_coverage_over_bearing_motion_mm"], 3
            )

    def test_cap_has_complete_hard_seats_and_positive_side_key_registration(self):
        from gondola.validation.bearing_capture import split_cap_seating_check

        result = split_cap_seating_check(self.lower, self.cap)
        self.assertTrue(result["passed"], result)
        self.assertGreater(result["hard_seat_witness_area_mm2"], 140)
        self.assertTrue(
            all(v > 0 for v in result["hypothetical_misregistration_penetration_mm3"])
        )

    def test_missing_key_or_side_land_cannot_claim_cap_seating(self):
        from gondola.validation.bearing_capture import split_cap_seating_check

        for cutter in (
            Part.makeBox(3, 3, 1.5, App.Vector(6, 28, 50)),
            Part.makeBox(2, 2, 1, App.Vector(6, 30, 49.5)),
        ):
            result = split_cap_seating_check(self.lower.cut(cutter), self.cap)
            self.assertFalse(result["passed"], result)

    def test_shifted_cap_is_rejected(self):
        from gondola.cad import translated_shape

        for direction in ({"x": 0.1}, {"y": 0.1}, {"z": 0.1}):
            result = self.check(cap=translated_shape(self.cap, **direction))
            self.assertFalse(result["passed"], result)

    def test_missing_upper_shoulder_or_guide_is_rejected(self):
        for cutter in (
            Part.makeBox(8, 0.5, 5, App.Vector(-4, 25, 50)),
            Part.makeBox(1, 3, 4, App.Vector(2.9, 26.5, 50)),
        ):
            result = self.check(cap=self.cap.cut(cutter))
            self.assertFalse(result["passed"], result)

    def test_shield_intrusion_or_undersize_bore_is_rejected(self):
        obstruction = Part.makeBox(0.2, 0.2, 0.2, App.Vector(2.7, 25.5, 49.9))
        result = self.check(frame=self.lower.fuse(obstruction))
        self.assertFalse(result["passed"], result)
        self.assertGreater(result["shield_passage_intrusion_mm3"], 0)

    def test_oversized_radial_seat_cannot_claim_location(self):
        cutter = Part.makeCylinder(3.4, 3, App.Vector(0, 26.5, 50), App.Vector(0, 1, 0))
        result = self.check(frame=self.lower.cut(cutter), cap=self.cap.cut(cutter))
        self.assertFalse(result["passed"], result)
        self.assertGreater(result["missing_complete_guide_wall_mm3"], 0)

    def test_wrong_bearing_and_shifted_or_undersize_journal_fail(self):
        from gondola.cad import translated_shape

        wrong = Part.makeCylinder(
            3.1, 2.5, App.Vector(0, 26.75, 50), App.Vector(0, 1, 0)
        )
        for changes in (
            {"bearing": wrong},
            {"shaft": translated_shape(self.shaft, x=0.1)},
            {
                "shaft": Part.makeCylinder(
                    1.4, 42, App.Vector(0, 13, 50), App.Vector(0, 1, 0)
                )
            },
        ):
            self.assertFalse(self.check(**changes)["passed"])

    def test_flat_cannot_reach_either_bearing_under_axial_play(self):
        self.assertTrue(self.check(41)["passed"])
        shortened_journal = self.shaft.cut(
            Part.makeBox(3, 14, 4, App.Vector(1, 41, 48))
        )
        result = self.check(41, shaft=shortened_journal)
        self.assertFalse(result["passed"], result)
        self.assertFalse(
            result["nominal_3mm_journal_covers_bearing_and_carrier_motion"]
        )

    def test_missing_or_nonfinite_carrier_travel_is_rejected(self):
        for value in (None, float("nan"), float("inf"), -0.1):
            for field in ("negative_travel", "positive_travel"):
                self.assertFalse(self.check(**{field: value})["passed"])

    def test_cap_then_bearing_vertical_removal_clears_retained_lower_housing(self):
        from gondola.validation.propulsion_service import split_housing_vertical_service

        obstacles = {
            "LowerHousing": self.lower,
            "InboardBearing": self.bearing(28),
            "OutboardBearing": self.bearing(41),
        }
        result = split_housing_vertical_service(self.cap, obstacles)
        self.assertTrue(result["passed"], result)
        for centre in (28, 41):
            result = split_housing_vertical_service(
                self.bearing(centre),
                {"LowerHousing": self.lower},
                bearing_centre_y=centre,
            )
            self.assertTrue(result["passed"], result)

    def test_cap_and_bearing_service_reject_midpath_obstructions(self):
        from gondola.cad import translated_shape
        from gondola.validation.propulsion_service import split_housing_vertical_service

        for shape, station, point in (
            (self.cap, None, (-8, 34, 65)),
            (self.bearing(28), 28, (2, 27, 65)),
        ):
            blocker = Part.makeBox(0.2, 0.2, 0.2, App.Vector(*point))
            self.assertLess(shape.common(blocker).Volume, 1e-7)
            self.assertLess(translated_shape(shape, z=30).common(blocker).Volume, 1e-7)
            result = split_housing_vertical_service(
                shape, {"MidpathBlocker": blocker}, bearing_centre_y=station
            )
            self.assertFalse(result["passed"], result)

    def test_uncovered_cap_addition_is_not_hidden_by_the_service_proxy(self):
        from gondola.validation.propulsion_service import split_housing_vertical_service

        extra = self.cap.fuse(Part.makeBox(1, 1, 1, App.Vector(8.5, 34, 52)))
        result = split_housing_vertical_service(extra, {})
        self.assertFalse(result["passed"], result)
        self.assertGreater(result["uncovered_start_stock_mm3"], 0.49)


if __name__ == "__main__":
    unittest.main()
