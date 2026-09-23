"""Native regressions for integral spacerless outer-ring bearing capture."""

import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class IntegralBearingCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.parts import bearing_retention, propulsion

        cls.b = bearing_retention
        cls.p = propulsion
        cls.cup = bearing_retention.cup_shape()
        cls.frame = propulsion.fixed_frame_shape()
        cls.carrier = propulsion.moving_carrier_shape()

    def test_coupon_and_both_release_states_are_connected_single_solids(self):
        for shape in (
            self.cup,
            self.b.cup_shape(self.b.RELEASE_MM),
            self.b.coupon_shape(),
        ):
            with self.subTest(volume=shape.Volume):
                self.assertTrue(shape.isValid())
                self.assertEqual(len(shape.Solids), 1)
        self.assertAlmostEqual(self.b.ARM_THICKNESS, 1.5)
        self.assertAlmostEqual(self.b.HOOK_STOP_Y - self.b.HOOK_FRONT_Y, 1.5)
        self.assertGreaterEqual(-self.b.ARM_ROOT_Z, 10)

    def test_outer_ring_capture_does_not_need_a_carrier_or_spacer(self):
        report = self.b.geometry_check(self.cup)
        self.assertTrue(report["passed"], report)
        self.assertAlmostEqual(report["nominal_axial_endplay_mm"], 0.2)
        self.assertAlmostEqual(report["complete_guide_length_mm"], 2.1)
        self.assertAlmostEqual(report["complete_guide_overlap_at_inward_limit_mm"], 1.9)
        self.assertGreater(report["inward_overtravel_block_mm3"], 0.05)
        self.assertGreater(report["outward_overtravel_block_mm3"], 0.1)
        self.assertEqual(report["shield_design_envelope_collision_mm3"], 0)

    def test_bearing_cannot_be_pulled_past_resting_hooks_but_released_path_is_clear(
        self,
    ):
        sweep = self.p.cylinder(3, 10.5, (0, -8, 0))
        self.assertGreater(self.cup.common(sweep).Volume, 0.1)
        released = self.b.released_shape(self.cup)
        self.assertLess(released.common(sweep).Volume, 1e-7)
        for tool in self.b.release_tool_shapes():
            self.assertLess(self.cup.common(tool).Volume, 1e-7)

    def test_square_hooks_keep_full_axial_thickness_without_thin_ramps(self):
        from gondola.cad import box

        ring = self.p.cylinder(2.99, 1.48, (0, -1.69, 0)).cut(
            self.p.cylinder(2.81, 1.48, (0, -1.69, 0))
        )
        for side in (-1, 1):
            witness = ring.common(box(4, 1.48, 2, (0 if side > 0 else -4, -1.69, -1)))
            self.assertGreater(witness.Volume, 0.4)
            self.assertLess(witness.cut(self.b.hook_shape(side)).Volume, 1e-7)

    def test_missing_one_hook_is_not_mistaken_for_redundant_capture(self):
        missing_hook = self.cup.cut(self.b.hook_shape(1))
        report = self.b.geometry_check(missing_hook)
        self.assertFalse(report["passed"])
        self.assertGreater(report["hook_missing_mm3"], 30)

    def test_refilled_service_pocket_is_rejected(self):
        from gondola.cad import box

        blocked = self.cup.fuse(box(1, 0.6, 2, (3.5, -0.2, -1)))
        report = self.b.geometry_check(blocked)
        self.assertFalse(report["passed"])
        self.assertGreater(report["hook_back_pocket_collision_mm3"], 1)

    def test_release_motion_checks_a_retained_neighbor_outside_the_resting_arm(self):
        from gondola.cad import box
        from gondola.validation.bearing_capture import release_motion_check

        fixed = self.cup.cut(
            Part.makeCompound([self.b.hook_shape(-1), self.b.hook_shape(1)])
        )
        bearing = self.p.bearing_shape()
        obstacles = {"frame": fixed, "retained_bearing": bearing}
        baseline = release_motion_check(lambda shape: shape, obstacles)
        self.assertTrue(baseline["passed"], baseline)
        blocker = box(0.05, 0.2, 0.2, (7.42, -0.7, -0.1))
        self.assertLess(self.cup.common(blocker).Volume, 1e-7)
        obstacles["neighbor"] = blocker
        result = release_motion_check(lambda shape: shape, obstacles)
        self.assertFalse(result["passed"], result)
        self.assertIn("retained_bearing", result["checked_objects"])
        self.assertTrue(result["poses"][0]["passed"])
        self.assertTrue(
            any("neighbor" in row["collisions_mm3"] for row in result["poses"])
        )

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
            p.cylinder(1.5, 14, (0, 20, 0)) if shaft is None else shaft,
            seat,
            self.carrier,
        )

    def test_all_four_installed_cups_keep_actual_arms_slots_and_support(self):
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
                        report["minimum_carrier_to_bearing_face_gap_mm"], 1.8
                    )
                    self.assertEqual(len(report["hook_contact_patch_areas_mm2"]), 2)
                    self.assertGreater(min(report["hook_contact_patch_areas_mm2"]), 0.5)

    def test_capture_uses_actual_frame_roll_in_tilted_pod_coordinates(self):
        from gondola.validation.bearing_capture import bearing_stack_check

        bearing, shaft, frame, carrier = self._stack()
        for angle in (37, 150):
            rotated = frame.copy()
            rotated.rotate(App.Vector(), App.Vector(0, 1, 0), angle)
            report = bearing_stack_check(
                bearing, shaft, rotated, carrier, toward_travel=0.5, away_travel=0.5
            )
            self.assertTrue(report["passed"], report)

    def test_unequal_travel_checks_both_ends_of_the_moving_shaft_journal(self):
        from gondola.validation.bearing_capture import bearing_stack_check

        # A deliberately shortened journal isolates both axial coverage limits.
        shaft = self.p.cylinder(1.5, 6.1, (0, 27.9, 0))
        for toward, away, expected_coverage, passed in (
            (0.25, 2.5, 2.7, True),
            (0.5, 2.5, 2.6, False),
            (0.25, 3.1, 2.6, False),
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
                    result["minimum_carrier_to_bearing_face_gap_mm"], 1.8 - 1e-5
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

    def test_saved_frame_missing_hook_fails_capture(self):
        from gondola.cad import translated_shape
        from gondola.validation.bearing_capture import bearing_stack_check

        bearing, shaft, frame, carrier = self._stack()
        frame = frame.cut(
            translated_shape(self.b.hook_shape(1), y=self.p.BEARING_START_Y)
        )
        report = bearing_stack_check(
            bearing, shaft, frame, carrier, toward_travel=0.5, away_travel=0.5
        )
        self.assertFalse(report["passed"])
        self.assertIn("two separate", report["error"])

    def test_wrong_bearing_or_shifted_and_undersize_journals_fail(self):
        from gondola.cad import translated_shape
        from gondola.validation.bearing_capture import bearing_stack_check

        bearing, shaft, frame, carrier = self._stack()
        for candidate in (
            translated_shape(shaft, x=0.1),
            self.p.cylinder(1.4, 14, (0, 20, 0)),
        ):
            report = bearing_stack_check(
                bearing, candidate, frame, carrier, toward_travel=0.5, away_travel=0.5
            )
            self.assertFalse(report["passed"], report)
        wrong_bearing = self.p.cylinder(3.5, 3, (0, self.p.BEARING_START_Y, 0)).cut(
            self.p.cylinder(1.5, 3, (0, self.p.BEARING_START_Y, 0))
        )
        report = bearing_stack_check(
            wrong_bearing, shaft, frame, carrier, toward_travel=0.5, away_travel=0.5
        )
        self.assertFalse(report["passed"], report)

    def test_broad_carrier_stop_face_remains_rotation_invariant(self):
        p = self.p
        for side in (-1, 1):
            witness = p.cylinder(3.55, 0.01, (0, side * 26 - 0.005, 0)).cut(
                p.cylinder(3.25, 0.01, (0, side * 26 - 0.005, 0))
            )
            volumes = []
            for angle in range(0, 360, 30):
                rotated = self.carrier.copy()
                rotated.rotate(App.Vector(), App.Vector(0, 1, 0), angle)
                volumes.append(rotated.common(witness).Volume)
            self.assertGreater(min(volumes), 0.015)
            self.assertLess(max(volumes) - min(volumes), 1e-7)


if __name__ == "__main__":
    unittest.main()
