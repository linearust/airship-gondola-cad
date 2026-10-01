"""Native regressions for rigid, serviceable outer-ring bearing capture."""

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
        from gondola.parts import bearing_retention, propulsion

        cls.b = bearing_retention
        cls.p = propulsion
        cls.cup = bearing_retention.cup_shape()
        cls.frame = propulsion.fixed_frame_shape()
        cls.carrier = propulsion.moving_carrier_shape()

    def test_frame_keeper_and_coupon_are_connected_single_solids(self):
        for shape in (self.cup, self.b.keeper_shape(), self.b.coupon_shape()):
            with self.subTest(volume=shape.Volume):
                self.assertTrue(shape.isValid())
                self.assertEqual(len(shape.Solids), 1)

    def test_outer_ring_capture_leaves_axial_and_diametral_allowance(self):
        report = self.b.geometry_check(self.cup, self.b.keeper_shape())
        self.assertTrue(report["passed"], report)
        self.assertAlmostEqual(report["nominal_axial_endplay_mm"], 0.5)
        self.assertAlmostEqual(self.b.SEAT_RADIUS * 2, 6.1)

    def test_snug_keeper_guides_and_shallow_nut_recess_retain_the_frame_floor(self):
        from gondola.cad import box

        self.assertAlmostEqual(self.b.KEEPER_GUIDE_CLEARANCE, 0.1)
        self.assertAlmostEqual(self.cup.BoundBox.YMax, 4.0)
        self.assertAlmostEqual(self.b.KEEPER_NUT_SEAT_Y, 3.5)
        # Pocket bearing plane at3.5 leaves2.0mm from the keeper hard seat1.5.
        floor = box(0.2, 2.0, 0.2, (1.5, 1.5, -18.1))
        self.assertLess(floor.cut(self.cup).Volume, 1e-7)
        pocket = box(0.2, 0.49, 0.2, (1.5, 3.51, -18.1))
        self.assertLess(pocket.common(self.cup).Volume, 1e-7)

    def test_symmetric_keeper_backing_retains_frame_load_paths(self):
        from gondola.validation.bearing_capture import keeper_backing_check

        report = keeper_backing_check(self.cup, self.b.keeper_shape())
        self.assertTrue(report["passed"], report)

    def test_saved_backing_check_rejects_missing_paths_or_asymmetric_additions(self):
        from gondola.cad import box
        from gondola.validation.bearing_capture import keeper_backing_check

        keeper = self.b.keeper_shape()
        cases = (
            (self.cup, keeper.cut(box(9, 2, 9, (-4.5, -0.5, -14)))),
            (self.cup, keeper.cut(box(2, 4, 1, (2.5, -2, -20)))),
            (self.cup.cut(box(9, 1, 9, (-4.5, 2, -14))), keeper),
            (self.cup.cut(box(1, 6, 9, (5, -2, -14))), keeper),
            (self.cup, keeper.fuse(box(0.3, 1, 1, (4.4, -1.5, -8)))),
        )
        for seat, candidate in cases:
            with self.subTest(seat_volume=seat.Volume, keeper_volume=candidate.Volume):
                report = keeper_backing_check(seat, candidate)
                self.assertFalse(report["passed"], report)

    def test_keeper_alignment_has_a_finite_shield_clearance_budget(self):
        from gondola.validation.bearing_capture import keeper_alignment_sensitivity

        report = keeper_alignment_sensitivity(self.b.keeper_shape())
        self.assertTrue(report["passed"], report)
        cases = {row["prescribed_radial_offset_mm"]: row for row in report["cases"]}
        self.assertTrue(cases[0.05]["all_cardinal_offsets_clear"])
        self.assertTrue(cases[0.05]["positive_nominal_gap"])
        self.assertAlmostEqual(cases[0.1]["nominal_radial_gap_mm"], 0)
        self.assertFalse(cases[0.1]["positive_nominal_gap"])
        self.assertFalse(cases[0.2]["all_cardinal_offsets_clear"])
        self.assertAlmostEqual(cases[0.25]["nominal_radial_gap_mm"], -0.15)
        self.assertFalse(cases[0.25]["all_cardinal_offsets_clear"])
        self.assertFalse(cases[0.25]["positive_nominal_gap"])

    def test_hypothetical_penetration_does_not_hide_installed_shield_overlap(self):
        from gondola.validation.bearing_capture import keeper_alignment_sensitivity
        from gondola.validation.evidence import overlap_failures

        keeper = self.b.keeper_shape()
        nominal = keeper_alignment_sensitivity(keeper)
        self.assertTrue(nominal["passed"])
        self.assertEqual(overlap_failures(nominal, 1e-5), [])
        blocked = keeper.fuse(self.p.cylinder(2.8, 1.5, (0, -2, 0)))
        actual_collision = keeper_alignment_sensitivity(blocked)
        self.assertFalse(actual_collision["passed"])
        failures = overlap_failures(actual_collision, 1e-5)
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]["field"], "/nominal_shield_envelope_overlap_mm3")
        self.assertGreater(failures[0]["volume_mm3"], 0)

    def test_removed_keeper_opens_the_full_inward_bearing_path(self):
        sweep = self.p.cylinder(3, 10.5, (0, -8, 0))
        self.assertGreater(self.b.keeper_shape().common(sweep).Volume, 0.1)
        self.assertLess(self.cup.common(sweep).Volume, 1e-7)

    def test_inward_keeper_service_detects_an_obstacle_between_endpoints(self):
        from gondola.cad import box, translated_shape
        from gondola.validation.propulsion_service import continuous_path

        keeper = self.b.keeper_shape()
        blocker = box(0.2, 0.2, 0.2, (3.5, -7, -5))
        self.assertLess(keeper.common(blocker).Volume, 1e-7)
        self.assertLess(translated_shape(keeper, y=-20).common(blocker).Volume, 1e-7)
        result = continuous_path(keeper, [(0, 0, 0), (0, -20, 0)], {"blocker": blocker})
        self.assertFalse(result["passed"], result)

    def test_missing_keeper_retention_land_fails(self):
        broken = self.b.keeper_shape().cut(self.p.cylinder(3.2, 4, (0, -3, 0)))
        report = self.b.geometry_check(self.cup, broken)
        self.assertFalse(report["passed"], report)

    def test_closed_or_oversized_seat_cannot_claim_supported_fit(self):
        from gondola.cad import box

        for cup in (
            self.cup.fuse(box(0.2, 0.2, 0.2, (2.9, 1, -0.1))),
            self.cup.cut(self.p.cylinder(3.4, 3, (0, -0.5, 0))),
        ):
            report = self.b.geometry_check(cup, self.b.keeper_shape())
            self.assertFalse(report["passed"], report)

    def _stack(self, *, side=1, pod_y=None, frame=None, bearing=None, shaft=None):
        from gondola.cad import mirrored_y, translated_shape

        p = self.p
        pod_y = p.PIVOT_HALF_SPAN if pod_y is None else pod_y
        seat = translated_shape(
            self.frame if frame is None else frame, y=-pod_y, z=-p.PIVOT_Z
        )
        seat = mirrored_y(seat, side)
        return (
            translated_shape(p.bearing_shape(), y=p.BEARING_START_Y)
            if bearing is None
            else bearing,
            p.cylinder(1.5, p.OUTPUT_IDLE_SHAFT_LENGTH, (0, p.OUTPUT_SHAFT_INNER_Y, 0))
            if shaft is None
            else shaft,
            seat,
            self.carrier,
            translated_shape(self.b.keeper_shape(), y=p.BEARING_START_Y),
        )

    def test_all_four_installed_cups_keep_rigid_keepers_and_support(self):
        from gondola.validation.bearing_capture import bearing_stack_check

        for pod_y in (-self.p.PIVOT_HALF_SPAN, self.p.PIVOT_HALF_SPAN):
            for side in (-1, 1):
                with self.subTest(pod_y=pod_y, side=side):
                    report = bearing_stack_check(
                        *self._stack(side=side, pod_y=pod_y),
                        toward_travel=0.5,
                        away_travel=0.5,
                    )
                    self.assertTrue(report["passed"], report)
                    self.assertAlmostEqual(
                        report["minimum_carrier_to_bearing_face_gap_mm"], 1.5
                    )
                    self.assertGreater(
                        report["keeper_outer_ring_contact_area_mm2"], 3.0
                    )

    def test_capture_uses_actual_frame_roll_in_tilted_pod_coordinates(self):
        from gondola.validation.bearing_capture import bearing_stack_check

        bearing, shaft, frame, carrier, keeper = self._stack()
        for angle in (37, 150):
            rotated = frame.copy()
            rotated.rotate(App.Vector(), App.Vector(0, 1, 0), angle)
            rotated_keeper = keeper.copy()
            rotated_keeper.rotate(App.Vector(), App.Vector(0, 1, 0), angle)
            report = bearing_stack_check(
                bearing,
                shaft,
                rotated,
                carrier,
                rotated_keeper,
                toward_travel=0.5,
                away_travel=0.5,
            )
            self.assertTrue(report["passed"], report)

    def test_unequal_travel_checks_both_ends_of_the_moving_shaft_journal(self):
        from gondola.validation.bearing_capture import bearing_stack_check

        # A deliberately shortened journal isolates both axial coverage limits.
        shaft = self.p.cylinder(1.5, 6.1, (0, self.p.BEARING_START_Y - 0.9, 0))
        for toward, away, expected_coverage, passed in (
            (0.25, 2.5, 3.0, True),
            (0.5, 2.5, 2.9, False),
            (0.25, 2.8, 2.9, False),
        ):
            with self.subTest(toward=toward, away=away):
                result = bearing_stack_check(
                    *self._stack(shaft=shaft),
                    toward_travel=toward,
                    away_travel=away,
                )
                self.assertEqual(result["passed"], passed, result)
                self.assertEqual(
                    result["nominal_3mm_journal_covers_bearing_and_carrier_motion"],
                    passed,
                )
                self.assertAlmostEqual(
                    result["minimum_shaft_coverage_over_bearing_motion_mm"],
                    expected_coverage,
                )
                self.assertGreaterEqual(
                    result["minimum_carrier_to_bearing_face_gap_mm"], 1.5 - 1e-5
                )

    def test_missing_or_invalid_either_carrier_stop_is_rejected(self):
        from gondola.validation.bearing_capture import bearing_stack_check

        for invalid in (None, float("nan"), float("inf"), -0.1):
            for toward, away in ((invalid, 0.5), (0.5, invalid)):
                with self.subTest(toward=toward, away=away):
                    result = bearing_stack_check(
                        *self._stack(), toward_travel=toward, away_travel=away
                    )
                    self.assertFalse(result["passed"], result)
                    self.assertEqual(result["error"], "Unproven carrier axial stop")

    def test_saved_keeper_missing_ring_land_fails_capture(self):
        from gondola.validation.bearing_capture import bearing_stack_check

        bearing, shaft, frame, carrier, keeper = self._stack()
        keeper = keeper.cut(self.p.cylinder(3.2, 4, (0, self.p.BEARING_START_Y - 3, 0)))
        report = bearing_stack_check(
            bearing, shaft, frame, carrier, keeper, toward_travel=0.5, away_travel=0.5
        )
        self.assertFalse(report["passed"], report)

    def test_wrong_bearing_or_shifted_and_undersize_journals_fail(self):
        from gondola.cad import translated_shape
        from gondola.validation.bearing_capture import bearing_stack_check

        bearing, shaft, frame, carrier, keeper = self._stack()
        for candidate in (
            translated_shape(shaft, x=0.1),
            self.p.cylinder(
                1.4,
                self.p.OUTPUT_IDLE_SHAFT_LENGTH,
                (0, self.p.OUTPUT_SHAFT_INNER_Y, 0),
            ),
        ):
            report = bearing_stack_check(
                bearing,
                candidate,
                frame,
                carrier,
                keeper,
                toward_travel=0.5,
                away_travel=0.5,
            )
            self.assertFalse(report["passed"], report)
        wrong_bearing = self.p.cylinder(3.5, 3, (0, self.p.BEARING_START_Y, 0)).cut(
            self.p.cylinder(1.5, 3, (0, self.p.BEARING_START_Y, 0))
        )
        report = bearing_stack_check(
            wrong_bearing,
            shaft,
            frame,
            carrier,
            keeper,
            toward_travel=0.5,
            away_travel=0.5,
        )
        self.assertFalse(report["passed"], report)

    def test_broad_carrier_stop_face_remains_rotation_invariant(self):
        p = self.p
        for side in (-1, 1):
            witness = p.cylinder(
                3.55, 0.01, (0, side * p.CARRIER_END_Y - 0.005, 0)
            ).cut(p.cylinder(3.25, 0.01, (0, side * p.CARRIER_END_Y - 0.005, 0)))
            volumes = []
            for angle in range(0, 360, 30):
                rotated = self.carrier.copy()
                rotated.rotate(App.Vector(), App.Vector(0, 1, 0), angle)
                volumes.append(rotated.common(witness).Volume)
            self.assertGreater(min(volumes), 0.015)
            self.assertLess(max(volumes) - min(volumes), 1e-7)


if __name__ == "__main__":
    unittest.main()
