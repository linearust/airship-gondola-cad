"""Native CAD regressions; run with the installed FreeCAD Python runtime."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from gondola.contracts.drive import DRIVE_CONFIGURATIONS, SELECTED_DRIVE

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class ContinuousServiceTests(unittest.TestCase):
    def test_midpath_obstacle_is_not_hidden_by_clear_endpoints(self):
        from gondola.cad import translated_shape
        from gondola.validation.geometry import intersection_volume
        from gondola.validation.propulsion_service import continuous_path

        moving = Part.makeBox(0.1, 1, 1)
        obstacle = Part.makeBox(0.02, 1, 1, App.Vector(5.37, 0, 0))
        self.assertEqual(intersection_volume(moving, obstacle), 0)
        self.assertEqual(
            intersection_volume(translated_shape(moving, x=10), obstacle), 0
        )
        result = continuous_path(
            moving, [(0, 0, 0), (10, 0, 0)], {"thin_wall": obstacle}
        )
        self.assertFalse(result["passed"])
        self.assertGreater(result["segments"][0]["intersection_mm3"]["thin_wall"], 0)

    def test_coaxial_sweep_keeps_a_real_through_bore_open(self):
        from gondola.validation.geometry import intersection_volume, translation_sweep

        sleeve = Part.makeCylinder(2, 2).cut(Part.makeCylinder(1, 2))
        swept, method = translation_sweep(sleeve, (0, 0, 8))
        expected = Part.makeCylinder(2, 10).cut(Part.makeCylinder(1, 10))
        self.assertIn("face-prism", method)
        self.assertLess(abs(expected.cut(swept).Volume), 1e-7)
        self.assertLess(abs(swept.cut(expected).Volume), 1e-7)
        self.assertEqual(intersection_volume(swept, Part.makeCylinder(0.5, 10)), 0)

    def test_transverse_cylinder_uses_a_conservative_envelope(self):
        from gondola.cad import translated_shape
        from gondola.validation.geometry import translation_sweep

        moving = Part.makeCylinder(1, 2)
        swept, method = translation_sweep(moving, (-10, 0, 0))
        self.assertIn("conservative", method)
        for distance in (0, -0.13, -4.57, -10):
            self.assertLess(
                abs(translated_shape(moving, x=distance).cut(swept).Volume), 1e-7
            )

    def test_retained_bolt_only_bypasses_its_own_withdrawal_not_nut_or_tool_checks(
        self,
    ):
        from gondola.parts import purchased_hardware as h
        from gondola.validation.propulsion_service import fastener_service_check

        bolt = h.servo_screw_shape(8).copy()
        nut = h.servo_nut_shape().copy()
        nut.translate(App.Vector(0, 0, 6))
        # Annulus blocks the full head, but clears the smaller holding tool.
        ring = Part.makeCylinder(2, 0.5, App.Vector(0, 0, -4)).cut(
            Part.makeCylinder(1.65, 0.5, App.Vector(0, 0, -4))
        )
        ordinary = fastener_service_check(
            bolt, nut, {"head_obstacle": ring}, thread_diameter=1.6
        )
        retained = fastener_service_check(
            bolt, nut, {"head_obstacle": ring}, thread_diameter=1.6, retain_bolt=True
        )
        self.assertFalse(ordinary["passed"], ordinary)
        self.assertTrue(retained["passed"], retained)
        self.assertIsNone(retained["bolt_axial_withdrawal"])
        for obstruction in (
            Part.makeBox(4, 4, 0.2, App.Vector(-2, -2, 8)),
            Part.makeCylinder(0.5, 1, App.Vector(0, 0, -4)),
        ):
            blocked = fastener_service_check(
                bolt,
                nut,
                {"obstruction": obstruction},
                thread_diameter=1.6,
                retain_bolt=True,
            )
            self.assertFalse(blocked["passed"], blocked)
        with self.assertRaises(ValueError):
            fastener_service_check(
                bolt, nut, {}, retain_bolt=True, nut_lateral_direction=(1, 0, 0)
            )

    def test_separate_driver_hub_and_tooth_envelope_preserves_empty_corners(self):
        from gondola.validation.propulsion_service import (
            driver_full_rotation_clearance_check,
        )

        gear = Part.makeCylinder(
            6, 5, App.Vector(0, 22.5, 0), App.Vector(0, 1, 0)
        ).fuse(Part.makeCylinder(12.5, 3, App.Vector(0, 27.5, 0), App.Vector(0, 1, 0)))
        obstacle = Part.makeBox(0.2, 1, 0.2, App.Vector(7, 23, 0))
        result = driver_full_rotation_clearance_check(
            gear, obstacle, App.Placement(), 1, SELECTED_DRIVE
        )
        self.assertTrue(result["passed"], result)
        self.assertAlmostEqual(result["guaranteed_gap_mm"], 1)
        blocker = Part.makeBox(0.2, 1, 0.2, App.Vector(6.05, 23, 0))
        self.assertFalse(
            driver_full_rotation_clearance_check(
                gear, blocker, App.Placement(), 1, SELECTED_DRIVE
            )["passed"]
        )

    def test_actual_gear_protrusion_cannot_hide_outside_the_rotation_envelope(self):
        from gondola.validation.propulsion_service import (
            driver_full_rotation_clearance_check,
        )

        gear = Part.makeCylinder(
            6, 5, App.Vector(0, 22.5, 0), App.Vector(0, 1, 0)
        ).fuse(Part.makeCylinder(12.5, 3, App.Vector(0, 27.5, 0), App.Vector(0, 1, 0)))
        extra = Part.makeBox(0.5, 1, 0.5, App.Vector(5.9, 24, 0))
        result = driver_full_rotation_clearance_check(
            gear.fuse(extra),
            Part.makeBox(1, 1, 1, App.Vector(50, 20, 0)),
            App.Placement(),
            1,
            SELECTED_DRIVE,
        )
        self.assertFalse(result["passed"], result)
        self.assertGreater(result["outside_full_rotation_envelope_mm3"], 0.1)

    def test_invalid_displacement_is_rejected(self):
        from gondola.validation.geometry import translation_sweep

        with self.assertRaises(ValueError):
            translation_sweep(Part.makeBox(1, 1, 1), (float("nan"), 0, 0))


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class GearEngagementTests(unittest.TestCase):
    def gears(self):
        def gear(radius, hub_radius, x, face_y, face_width, total_length):
            axis = App.Vector(0, 1, 0)
            origin = App.Vector(x, face_y, 0)
            return Part.makeCylinder(radius, face_width, origin, axis).fuse(
                Part.makeCylinder(hub_radius, total_length, origin, axis)
            )

        return gear(12.5, 6, 0, 1, 3, 8), gear(4.5, 3.25, 16, 0, 5, 10)

    def check(self, driver, output):
        from gondola.validation.propulsion import gear_mesh_check

        return gear_mesh_check(
            driver,
            output,
            module=0.5,
            driver_teeth=48,
            output_teeth=16,
            minimum_face_overlap=3,
        )

    def test_aligned_tooth_faces_pass_positioning_check(self):
        result = self.check(*self.gears())
        self.assertTrue(result["passed"], result)
        self.assertAlmostEqual(result["tooth_face_overlap_mm"], 3)

    def test_overlapping_hub_lengths_cannot_hide_disengaged_tooth_faces(self):
        from gondola.cad import translated_shape

        driver, output = self.gears()
        output = translated_shape(output, y=4.2)
        self.assertLess(output.BoundBox.YMin, driver.BoundBox.YMax)
        result = self.check(driver, output)
        self.assertFalse(result["passed"], result)
        self.assertLess(result["tooth_face_overlap_mm"], 0)

    def test_axis_distance_must_match_the_fixed_nominal_datum(self):
        from gondola.cad import translated_shape

        driver, output = self.gears()
        for shift in (-0.1, 0.05):
            with self.subTest(shift=shift):
                result = self.check(driver, translated_shape(output, x=shift))
                self.assertFalse(result["passed"], result)

    def test_nominal_axis_tolerance_cannot_hide_insufficient_contact_ratio(self):
        from gondola.cad import translated_shape

        driver, output = self.gears()
        result = self.check(driver, translated_shape(output, x=0.2))
        self.assertAlmostEqual(result["axis_distance_mm"], 16.2)
        self.assertLess(result["standard_involute_contact_ratio"], 1.3)
        self.assertFalse(result["passed"], result)

    def test_axial_float_reduces_real_tooth_face_engagement(self):
        from gondola.validation.propulsion import gear_mesh_check

        for travel, expected, passed in (
            ((-0.5, 0.5), 3.0, True),
            ((-0.2, 1.8), 2.2, False),
        ):
            with self.subTest(travel=travel):
                result = gear_mesh_check(
                    *self.gears(),
                    module=0.5,
                    driver_teeth=48,
                    output_teeth=16,
                    minimum_face_overlap=3,
                    output_axial_travel=travel,
                    minimum_face_overlap_under_travel=2.4,
                )
                self.assertAlmostEqual(result["tooth_face_overlap_mm"], 3)
                self.assertAlmostEqual(
                    result["minimum_tooth_face_overlap_under_travel_mm"], expected
                )
                self.assertEqual(result["passed"], passed, result)

    def test_invalid_axial_travel_cannot_claim_engagement(self):
        from gondola.validation.propulsion import gear_mesh_check

        for travel in ((float("nan"), 0.5), (0.5, -0.5), (0.2, 0.5)):
            with self.subTest(travel=travel), self.assertRaises(ValueError):
                gear_mesh_check(
                    *self.gears(),
                    module=0.5,
                    driver_teeth=48,
                    output_teeth=16,
                    minimum_face_overlap=3,
                    output_axial_travel=travel,
                )


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class BearingCaptureTests(unittest.TestCase):
    def setUp(self):
        from gondola.parts.propulsion import build_propulsion_module

        self.doc = App.newDocument("BearingCaptureTests")
        self.module = build_propulsion_module(self.doc)
        self.addCleanup(
            lambda name=self.doc.Name: (
                App.closeDocument(name) if name in App.listDocuments() else None
            )
        )

    def check(self):
        from gondola.validation.propulsion import output_bearing_stack_check

        return output_bearing_stack_check(self.doc, "Port", "Outboard")

    def test_nominal_split_stack_has_two_shoulder_witnesses_and_hard_cap_seats(self):
        result = self.check()
        self.assertTrue(result["passed"], result)
        self.assertEqual(result["bearing_endplay_each_direction_mm"], 0.25)
        self.assertTrue(result["cap_hard_seating"]["passed"])
        self.assertEqual(
            {row["bolt"] for row in result["cap_fasteners"]},
            {
                "PortBearingCapNegativeBolt",
                "PortBearingCapPositiveBolt",
                "PortBearingCapInputBolt",
            },
        )

    def test_missing_cap_cannot_claim_capture(self):
        self.doc.removeObject("PortBearingCap")
        self.doc.recompute()
        self.assertFalse(self.check()["passed"])

    def test_unseated_cap_fastener_cannot_claim_capture(self):
        self.doc.PortBearingCapPositiveBolt.Placement.Base.z += 0.2
        self.doc.recompute()
        result = self.check()
        self.assertFalse(result["passed"], result)
        self.assertTrue(any(not row["passed"] for row in result["cap_fasteners"]))

    def test_cap_registration_cannot_move_independently_of_bearing(self):
        self.doc.PortBearingCap.Placement.Base.x += 0.2
        self.doc.recompute()
        self.assertFalse(self.check()["passed"])

    def test_removed_outer_shoulder_cannot_claim_capture(self):
        cutter = Part.makeCylinder(
            3.01, 1.5, App.Vector(0, 42.5, 50), App.Vector(0, 1, 0)
        )
        for obj in (self.doc.PropulsionFixedFrame, self.doc.PortBearingCap):
            obj.Shape = obj.Shape.cut(cutter)
        self.doc.recompute()
        self.assertFalse(self.check()["passed"])

    def test_missing_guide_sector_cannot_claim_complete_support(self):
        self.doc.PortBearingCap.Shape = self.doc.PortBearingCap.Shape.cut(
            Part.makeBox(1, 3, 4, App.Vector(2.9, 39.5, 50))
        )
        self.doc.recompute()
        result = self.check()
        self.assertFalse(result["passed"], result)
        self.assertGreater(result["missing_complete_guide_wall_mm3"], 0)

    def test_offset_bearing_cannot_reuse_nominal_guide(self):
        self.doc.PortOutputBearingOutboard.Placement.Base.x += 0.1
        self.doc.recompute()
        self.assertFalse(self.check()["passed"])

    def test_flat_reaching_the_outboard_bearing_is_rejected(self):
        obj = self.doc.PortOutputShaftNegative
        obj.Shape = obj.Shape.cut(Part.makeBox(3, 14, 4, App.Vector(1, -34, -2)))
        self.doc.recompute()
        result = self.check()
        self.assertFalse(result["passed"], result)
        self.assertGreater(result["missing_complete_round_journal_mm3"], 0)

    def test_both_bearings_include_both_rotor_travel_limits(self):
        from gondola.validation.propulsion import output_bearing_stack_check

        for suffix in ("Inboard", "Outboard"):
            for field in ("negative_mm", "positive_mm"):
                stops = {"passed": True, "negative_mm": 0.5, "positive_mm": 0.5}
                stops[field] = 30
                result = output_bearing_stack_check(self.doc, "Port", suffix, stops)
                self.assertFalse(result["passed"], result)
                self.assertFalse(
                    result["nominal_3mm_journal_covers_bearing_and_carrier_motion"]
                )

    def test_reopened_native_stack_preserves_ordered_cap_and_bearing_service(self):
        from gondola.validation.propulsion import (
            _record_bearing_checks,
            input_drive_service_check,
        )
        from gondola.validation.propulsion_service import module_service_shapes

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "split-bearing-service.FCStd"
            members = {
                key: [obj.Name for obj in self.module[key]]
                for key in ("printed", "hardware", "references")
            }
            self.doc.MainPropulsionModule.Placement = App.Placement(
                App.Vector(12, -7, 4), App.Rotation(App.Vector(1, 2, 3), 11)
            )
            self.doc.recompute()
            self.doc.saveAs(str(path))
            App.closeDocument(self.doc.Name)
            saved = App.openDocument(str(path), hidden=True)
            try:
                saved.recompute()
                module = {
                    key: [saved.getObject(name) for name in names]
                    for key, names in members.items()
                }
                module["group"] = saved.MainPropulsionModule
                physical, missing = module_service_shapes(saved, module)
                self.assertFalse(missing)
                report = {
                    "bearing_stacks": [],
                    "bearing_service": [],
                    "input_bearing_service": [],
                    "input_drive_service": [
                        input_drive_service_check(saved, module, prefix)
                        for prefix in ("Port", "Starboard")
                    ],
                    "output_carrier_service": [],
                }
                for prefix in ("Port", "Starboard"):
                    _record_bearing_checks(report, saved, module, prefix, physical)
                self.assertEqual(len(report["bearing_service"]), 4)
                self.assertEqual(len(report["input_bearing_service"]), 2)
                self.assertTrue(
                    all(row["passed"] for rows in report.values() for row in rows),
                    report,
                )
            finally:
                App.closeDocument(saved.Name)

    def test_input_bearing_lift_requires_successful_prior_input_removal(self):
        from gondola.validation.propulsion import _record_bearing_checks
        from gondola.validation.propulsion_service import module_service_shapes

        physical, missing = module_service_shapes(self.doc, self.module)
        self.assertFalse(missing)
        for prefix in ("Port", "Starboard"):
            # Removing the journal alone leaves a geometrically clear bearing
            # lift, but is not evidence that the ordered input service passed.
            report = {
                "bearing_stacks": [],
                "bearing_service": [],
                "input_bearing_service": [],
                "output_carrier_service": [],
                "input_drive_service": [
                    {
                        "pod": prefix,
                        "passed": False,
                        "removed_parts": [prefix + "InputShaft"],
                    }
                ],
            }
            _record_bearing_checks(report, self.doc, self.module, prefix, physical)
            row = report["input_bearing_service"][0]
            self.assertTrue(row["cap_removal"]["passed"], row)
            self.assertTrue(row["bearing_removal"]["passed"], row)
            self.assertFalse(row["input_removal_passed"])
            self.assertFalse(row["passed"])

            report["input_drive_service"] = []
            report["input_bearing_service"] = []
            _record_bearing_checks(report, self.doc, self.module, prefix, physical)
            self.assertFalse(report["input_bearing_service"][0]["passed"])

    def test_parent_transform_and_tilt_preserve_the_capture_proof(self):
        root = self.doc.addObject("App::Part", "MovedRoot")
        root.addObject(self.module["group"])
        root.Placement = App.Placement(
            App.Vector(12, -47, 39), App.Rotation(App.Vector(2, 5, -3), 41)
        )
        self.doc.PortPod.Tilt = 71
        self.doc.recompute()
        result = self.check()
        self.assertTrue(result["passed"], result)


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class NativeGearedDriveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.parts import propulsion

        cls.doc = App.newDocument("GearedDriveRegression")
        cls.module = propulsion.build_propulsion_module(cls.doc)
        propulsion.build_fit_coupons(cls.doc)

    @classmethod
    def tearDownClass(cls):
        App.closeDocument(cls.doc.Name)

    def test_exact_datums_preserve_two_flat_shafts_and_gear_engagement(self):
        from gondola.cad import world_shape

        points = [
            self.doc.getObject(p + "Pod").getGlobalPlacement().Base
            for p in ("Port", "Starboard")
        ]
        self.assertAlmostEqual((points[0] - points[1]).Length, 150)
        self.assertTrue(all(abs(point.z - 50) < 1e-7 for point in points))
        for prefix, sign, suffix in (
            ("Port", 1, "Negative"),
            ("Starboard", -1, "Positive"),
        ):
            obj = self.doc.getObject(prefix + "OutputShaft" + suffix)
            shaft = world_shape(obj)
            gear = world_shape(self.doc.getObject(prefix + "OutputGear"))

            def canonical(shape):
                return sorted(
                    sign * v for v in (shape.BoundBox.YMin, shape.BoundBox.YMax)
                )

            self.assertEqual(obj.HardwareSKU, "SS304_CUT3_L42_FLAT5_GRIP11_A0")
            self.assertEqual(canonical(shaft), [13, 55])
            self.assertEqual(canonical(gear), [13.5, 23.5])
            flats = [
                f
                for f in shaft.Faces
                if type(f.Surface).__name__ == "Plane"
                and abs(f.CenterOfMass.x - 1) < 1e-7
                and abs(abs(f.normalAt(0, 0).x) - 1) < 1e-7
            ]
            self.assertEqual(sorted(canonical(f) for f in flats), [[13, 18], [44, 55]])
            screw = canonical(gear)[0] + 2.5
            self.assertEqual(min(screw - 13, 18 - screw), 2)

    def test_paired_inboard_support_and_mirrored_ten_mm_keyed_roots(self):
        from gondola.cad import world_shape
        from gondola.validation.propulsion import carrier_shaft_retention_check

        mirrored = self.doc.StarboardMotorCarrier.Shape.mirror(
            App.Vector(), App.Vector(0, 1, 0)
        )
        self.assertLess(self.doc.PortMotorCarrier.Shape.cut(mirrored).Volume, 1e-7)
        for prefix in ("Port", "Starboard"):
            bearings = [
                world_shape(self.doc.getObject(prefix + "OutputBearing" + suffix))
                for suffix in ("Inboard", "Outboard")
            ]
            self.assertAlmostEqual(
                abs(bearings[0].BoundBox.Center.y - bearings[1].BoundBox.Center.y), 13
            )
            self.assertTrue(carrier_shaft_retention_check(self.doc, prefix)["passed"])
            idle = (
                prefix
                + "OutputShaft"
                + ("Positive" if prefix == "Port" else "Negative")
            )
            self.assertIsNone(self.doc.getObject(idle))

    def test_inward_shaft_withdrawal_hits_opposite_shaft_but_outward_unit_route_clears(
        self,
    ):
        from gondola.cad import world_shape
        from gondola.validation.propulsion import output_carrier_service_check
        from gondola.validation.propulsion_service import continuous_path

        result = continuous_path(
            world_shape(self.doc.PortOutputShaftNegative),
            [(0, 0, 0), (0, -43, 0)],
            {"OppositeShaft": world_shape(self.doc.StarboardOutputShaftPositive)},
        )
        self.assertFalse(result["passed"])
        self.assertTrue(
            output_carrier_service_check(self.doc, self.module, "Port")["passed"]
        )

    def test_future_rotor_bulk_has_symmetric_clearance_and_reciprocal_service(self):
        from gondola.validation.propulsion import replacement_rotor_space_check

        for prefix in ("Port", "Starboard"):
            with self.subTest(pod=prefix):
                result = replacement_rotor_space_check(self.doc, self.module, prefix)
                self.assertTrue(result["passed"], result)
                self.assertEqual(result["future_propeller_reference_diameter_mm"], 50)
                self.assertEqual(result["bulk_half_width_mm"], 29)
                self.assertEqual(result["full_rotation_radius_mm"], 34)
                self.assertAlmostEqual(result["nominal_frame_gap_mm"], 2)
                for gap in result["post_face_gaps"]:
                    self.assertGreaterEqual(gap["nominal_post_face_gap_mm"], 2 - 1e-7)
                    # Accurate OCCT bounds include ~1e-7 mm edge tolerance;
                    # retain the nominal clearance, as for other CAD bounds.
                    self.assertGreaterEqual(gap["gap_at_axial_stop_mm"], 1.5 - 1e-6)
                self.assertGreaterEqual(
                    min(result["all_angle_gaps_with_axial_travel_mm"].values()),
                    1.25 - 1e-7,
                )
                self.assertIn(
                    prefix + "DriverGear",
                    result["all_angle_gaps_with_axial_travel_mm"],
                )
                self.assertTrue(result["rotor_bulk_removal"]["passed"])
                self.assertTrue(result["servo_module_removal_past_future_bulk"])
                paths = {
                    row["part"]: row
                    for row in result["servo_module_removal_past_future_bulk"]
                }
                for side, sign in (("Port", 1), ("Starboard", -1)):
                    for suffix, stage, points in (
                        (
                            "InputShaft",
                            "input_shaft_removal",
                            [(0, 0, 0), (0, sign * 32, 0), (sign * 60, sign * 32, 0)],
                        ),
                        (
                            "DriverGear",
                            "loose_driver_removal",
                            [(0, 0, 0), (sign * 60, 0, 0)],
                        ),
                        (
                            "Servo",
                            "servo_horn_adapter_removal",
                            [(0, 0, 0), (0, sign * 13, 0), (sign * 60, sign * 13, 0)],
                        ),
                    ):
                        row = paths[side + suffix]
                        self.assertEqual(row["service_stage"], stage)
                        self.assertEqual(row["waypoints_mm"], points)
                        self.assertTrue(row["passed"], row)
                self.assertEqual(len(result["input_grip_tools_past_future_bulk"]), 2)
                self.assertTrue(
                    all(
                        row["passed"]
                        for row in result["input_grip_tools_past_future_bulk"]
                    )
                )

    def test_future_space_does_not_claim_current_guard_accepts_fifty_mm_prop(self):
        from gondola.parts import propulsion

        carrier = self.doc.PortMotorCarrier.Shape
        current_prop = propulsion.cylinder(20, 5, (3.8, 0, 0), (1, 0, 0))
        future_prop = propulsion.cylinder(25, 5, (3.8, 0, 0), (1, 0, 0))
        self.assertLess(carrier.common(current_prop).Volume, 1e-7)
        self.assertGreater(carrier.common(future_prop).Volume, 100)
        guard = carrier.common(Part.makeBox(1.8, 2, 5, App.Vector(8.1, -1, 21)))
        self.assertAlmostEqual(guard.BoundBox.ZMax, 26, places=6)
        self.assertGreater(guard.BoundBox.ZMin, 22.97)

    def test_future_rotor_reserve_rejects_an_intruding_bearing_post(self):
        from gondola.validation.propulsion import replacement_rotor_space_check

        frame = self.doc.PropulsionFixedFrame
        original = frame.Shape.copy()
        try:
            intrusion = Part.makeBox(1.4, 5, 1, App.Vector(-4.6, 43.5, 49.5))
            frame.Shape = original.fuse(intrusion)
            self.doc.recompute()
            self.assertEqual(len(frame.Shape.Solids), 1)
            self.assertGreater(frame.Shape.Volume - original.Volume, 2)
            result = replacement_rotor_space_check(self.doc, self.module, "Port")
            self.assertFalse(result["passed"], result)
            self.assertLess(
                result["all_angle_gaps_with_axial_travel_mm"]["PropulsionFixedFrame"],
                1.25,
            )
        finally:
            frame.Shape = original
            self.doc.recompute()

    def test_future_rotor_service_rejects_an_outward_route_obstacle(self):
        from gondola.validation.propulsion import replacement_rotor_space_check

        frame = self.doc.PropulsionFixedFrame
        original = frame.Shape.copy()
        try:
            foot = Part.makeBox(4, 92, 3, App.Vector(-2, 40, 7.5))
            post = Part.makeBox(2, 2, 24, App.Vector(-1, 130, 7.5))
            # Join the remote service blocker to the raised beam without
            # introducing stock inside the nominal future rotor envelope.
            riser = Part.makeBox(4, 2, 20, App.Vector(-2, 40, 7.5))
            frame.Shape = original.fuse(foot).fuse(post).fuse(riser)
            self.doc.recompute()
            self.assertEqual(len(frame.Shape.Solids), 1)
            result = replacement_rotor_space_check(self.doc, self.module, "Port")
            self.assertGreaterEqual(
                result["all_angle_gaps_with_axial_travel_mm"]["PropulsionFixedFrame"],
                1.25 - 1e-7,
            )
            self.assertFalse(result["rotor_bulk_removal"]["passed"])
            self.assertFalse(result["passed"])
        finally:
            frame.Shape = original
            self.doc.recompute()

    def test_blended_bearing_post_roots_keep_the_complete_load_section(self):
        from gondola.validation.propulsion import bearing_post_roots_check

        rows = bearing_post_roots_check(self.doc)
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertTrue(row["passed"], row)
            self.assertEqual(row["root_section_mm"], [18, 19])
            self.assertEqual(row["root_blend_radius_mm"], 1.5)
            self.assertLess(row["missing_root_blend_mm3"], 1e-7)

    def test_missing_bearing_root_blend_is_rejected(self):
        from gondola.validation.propulsion import bearing_post_roots_check

        frame = self.doc.PropulsionFixedFrame
        original = frame.Shape.copy()
        try:
            frame.Shape = original.cut(
                Part.makeBox(18, 1.5, 1.5, App.Vector(-9, 23.5, 29.5))
            )
            self.doc.recompute()
            rows = bearing_post_roots_check(self.doc)
            self.assertEqual(sum(not row["passed"] for row in rows), 1)
            self.assertGreater(max(row["missing_root_blend_mm3"] for row in rows), 1)
        finally:
            frame.Shape = original
            self.doc.recompute()

    def test_inboard_posts_clear_continuous_output_rotation_and_axial_travel(self):
        from gondola.validation.motion_clearance import carrier_metal_clearance_check

        for prefix in ("Port", "Starboard"):
            result = carrier_metal_clearance_check(self.doc, prefix)
            self.assertTrue(result["passed"], result)
            self.assertEqual(len(result["frame_clearance"]), 6)

    def test_rear_servo_body_allowance_excludes_the_lower_ear(self):
        from gondola.parts import servo_bridge
        from gondola.validation.propulsion import servo_mount_check

        for prefix in ("Port", "Starboard"):
            with self.subTest(side=prefix):
                result = servo_mount_check(self.doc, prefix)
                self.assertTrue(result["passed"], result)
                allowance = result["rear_body_and_inward_lead_allowance"]
                self.assertAlmostEqual(allowance["rear_body_bottom_z_mm"], -15)
                self.assertAlmostEqual(allowance["servo_with_ears_bottom_z_mm"], -19)
                self.assertIsNone(allowance["rear_body_to_plate_gap_mm"])
                self.assertIsNone(allowance["plate_top_below_rear_body_z_mm"])
                self.assertTrue(allowance["rear_strip_open_below"])
                self.assertLess(
                    allowance["five_mm_rear_body_reserve_intrusion_mm3"], 1e-7
                )
                for actual, expected in zip(allowance["rear_body_section_mm"], (7, 20)):
                    self.assertAlmostEqual(actual, expected)
                self.assertAlmostEqual(
                    allowance["inward_planning_y_range_mm"][1],
                    servo_bridge.case_front_y() - 16.7,
                )
                self.assertAlmostEqual(
                    allowance["rear_then_outward_planning_volume_mm"][1], 1.8
                )
                self.assertCountEqual(
                    [
                        row["parts"]
                        for row in allowance["continuous_input_drive_clearance"]
                    ],
                    [
                        [prefix + "RearLeadAllowance", side + suffix]
                        for side in ("Port", "Starboard")
                        for suffix in (
                            "ServoHorn",
                            "HornGearAdapter",
                            "DriverGear",
                            "InputShaft",
                            "InputShaftClampBolt",
                            "InputShaftClampNut",
                            "HornGearClampNearBolt",
                            "HornGearClampFarBolt",
                            "HornGearClampNearNut",
                            "HornGearClampFarNut",
                        )
                    ],
                )
                self.assertIn(
                    "StarboardServoEarLowerNut", allowance["checked_physical_objects"]
                )

    def test_rear_servo_lead_allowance_detects_an_added_physical_obstacle(self):
        from gondola.parts import servo_bridge
        from gondola.validation.propulsion import servo_mount_check

        obstacle = self.doc.addObject("Part::Feature", "AddedServoLeadObstacle")
        self.doc.PortServoMount.addObject(obstacle)
        try:
            obstacle.Shape = Part.makeBox(
                1, 1, 2, App.Vector(-0.5, servo_bridge.case_front_y() - 17.6, -2)
            )
            self.doc.recompute()
            result = servo_mount_check(self.doc, "Port")
            self.assertLess(result["servo_frame_intersection_mm3"], 1e-5)
            self.assertTrue(all(row["passed"] for row in result["cases"]), result)
            allowance = result["rear_body_and_inward_lead_allowance"]
            self.assertFalse(result["passed"], result)
            self.assertIn(
                obstacle.Name,
                {row["part"] for row in allowance["planning_volume_collisions"]},
            )
        finally:
            self.doc.removeObject(obstacle.Name)
            self.doc.recompute()

    def test_rear_servo_lead_allowance_detects_opposite_drive_mid_sweep(self):
        from gondola.cad import world_shape
        from gondola.parts import servo_bridge
        from gondola.validation.propulsion import servo_mount_check

        obstacle = self.doc.addObject("Part::Feature", "MovingRearLeadBlocker")
        drive = self.doc.StarboardInputDrive
        drive.addObject(obstacle)
        try:
            # The protrusion is clear at neutral, but enters the opposite
            # servo's rear lead allowance during its independent input motion.
            shape = Part.makeBox(
                0.5, 0.5, 0.5, App.Vector(14, servo_bridge.case_front_y() - 17.6, 4)
            )
            shape.Placement = (
                drive.getGlobalPlacement()
                .inverse()
                .multiply(self.doc.PortServoMount.getGlobalPlacement())
                .multiply(shape.Placement)
            )
            shape.rotate(App.Vector(), App.Vector(0, 1, 0), -30)
            obstacle.Shape = shape
            self.doc.recompute()
            self.assertTrue(world_shape(obstacle).isValid())
            result = servo_mount_check(self.doc, "Port")
            allowance = result["rear_body_and_inward_lead_allowance"]
            self.assertEqual(allowance["planning_volume_collisions"], [])
            self.assertFalse(result["passed"], result)
            failures = [
                row
                for row in allowance["continuous_input_drive_clearance"]
                if not row["passed"]
            ]
            self.assertTrue(any(obstacle.Name in row["parts"] for row in failures))
        finally:
            self.doc.removeObject(obstacle.Name)
            self.doc.recompute()

    def test_rear_servo_allowance_rejects_a_clear_but_too_close_plate(self):
        from gondola.parts import servo_bridge
        from gondola.validation.propulsion import servo_mount_check

        bridge = self.doc.PropulsionFixedFrame
        original = bridge.Shape.copy()
        before = servo_mount_check(self.doc, "Port")[
            "rear_body_and_inward_lead_allowance"
        ]
        self.assertTrue(before["passed"], before)
        self.assertIsNone(before["rear_body_to_plate_gap_mm"])
        # This ledge joins the real lower crossbeam and intrudes0.5mm into
        # the required five-millimetre air reserve beneath the rear case.
        patch = Part.makeBox(
            7,
            8,
            1,
            App.Vector(-3.5, servo_bridge.case_front_y() - 16.6 + 0.5, -20.5),
        )
        patch.Placement = (
            bridge.getGlobalPlacement()
            .inverse()
            .multiply(self.doc.PortServoMount.getGlobalPlacement())
        )
        try:
            bridge.Shape = original.fuse(patch)
            self.doc.recompute()
            result = servo_mount_check(self.doc, "Port")
            allowance = result["rear_body_and_inward_lead_allowance"]
            self.assertEqual(allowance["planning_volume_collisions"], [])
            self.assertLess(result["servo_frame_intersection_mm3"], 1e-5)
            self.assertAlmostEqual(allowance["rear_body_to_plate_gap_mm"], 4.5)
            self.assertGreater(allowance["five_mm_rear_body_reserve_intrusion_mm3"], 3)
            self.assertLess(allowance["rear_body_to_plate_gap_mm"], 5)
            self.assertFalse(result["passed"], result)
        finally:
            bridge.Shape = original
            self.doc.recompute()

    def test_gear_metrics_distinguish_driver_and_output_face_width(self):
        metrics = self.module["metrics"]["gear_drive"]
        self.assertNotIn("face_width_mm", metrics)
        self.assertEqual(metrics["driver_face_width_mm"], 3.0)
        self.assertEqual(metrics["output_face_width_mm"], 5.0)
        self.assertEqual(metrics["nominal_full_face_overlap_mm"], 3.0)

    def test_side_rail_mount_access_preserves_the_complete_servo_module(self):
        from gondola.validation.propulsion import rail_mount_clearance_check

        row = rail_mount_clearance_check(self.doc, self.module)
        self.assertTrue(row["passed"], row)
        self.assertEqual(row["removed_before_access"], [])
        for name in (
            "PropulsionFixedFrame",
            "StarboardDriverGear",
            "PortServo",
            "PortOutputGear",
            "PropulsionFixedFrame",
        ):
            self.assertTrue(
                all(name in site["retained_during_access"] for site in row["sites"])
            )
        self.assertEqual(len(row["sites"]), 2)
        self.assertEqual(row["clamp_spacing_mm"], 28.0)
        for site in row["sites"]:
            self.assertEqual(site["side_bolt_axis_mm"], [14.0, 6.0])
            self.assertEqual(site["centred_load_zone_x_range_mm"], [9.0, 19.0])
            self.assertEqual(site["physical_shoe_pair_x_range_mm"], [-22, 22])
            self.assertEqual(
                site["shared_grip_contact_check"]["checked_centred_contact_length_mm"],
                10,
            )
            support = site["paired_spine_support"]
            self.assertTrue(support["passed"])
            self.assertEqual(support["shoe_pair_extent_mm"], 44)
            self.assertAlmostEqual(support["top_bearing_area_total_mm2"], 80)
            self.assertTrue(
                all(row["passed"] for row in support["coplanar_trim_cases"])
            )
            self.assertAlmostEqual(support["nominal_base_clearance_mm"], 1.0)
            self.assertFalse(support["independent_wall_tilt_claimed"])
            self.assertEqual(site["screw_length_mm"], 10)

    def test_new_frame_obstacle_cannot_hide_from_side_rail_access(self):
        from gondola.parts import rail
        from gondola.validation.propulsion import rail_mount_clearance_check

        frame = self.doc.PropulsionFixedFrame
        original = frame.Shape.copy()
        try:
            obstruction = Part.makeBox(
                8, 0.5, 4.5, App.Vector(13, -12, rail.BOLT_AXIS_Z - 2.25)
            )
            frame.Shape = original.fuse(obstruction)
            self.doc.recompute()
            row = rail_mount_clearance_check(self.doc, self.module)
            self.assertFalse(row["passed"], row)
            self.assertGreater(
                row["sites"][0]["driver_clearance_overlap_mm3"]["PropulsionFixedFrame"],
                0,
            )
        finally:
            frame.Shape = original
            self.doc.recompute()

    def test_native_output_limits_ratio_and_fixed_servo_datum(self):
        from gondola.validation.propulsion import (
            drive_motion_check,
            fixed_servo_datum_check,
        )

        for prefix in ("Port", "Starboard"):
            with self.subTest(prefix=prefix):
                result = drive_motion_check(self.doc, prefix)
                self.assertTrue(result["passed"], result)
                result = fixed_servo_datum_check(self.doc, prefix)
                self.assertTrue(result["passed"], result)

    def test_saved_gear_axial_offset_cannot_reuse_source_engagement(self):
        from gondola.validation.propulsion import gear_engagement_check

        gear = self.doc.PortOutputGear
        original = App.Placement(gear.Placement)
        try:
            result = gear_engagement_check(self.doc, "Port")
            self.assertTrue(result["passed"], result)
            # Move inward away from the new gear-side thrust stop, reducing
            # engagement without first embedding the gear in its housing.
            gear.Placement.Base.y -= 1.6
            self.doc.recompute()
            result = gear_engagement_check(self.doc, "Port")
            self.assertFalse(result["passed"], result)
            self.assertAlmostEqual(result["tooth_face_overlap_mm"], 2.4)
            # Accurate-bound padding is numerical, not extra physical engagement.
            self.assertAlmostEqual(
                result["minimum_tooth_face_overlap_under_travel_mm"],
                1.9,
                places=6,
            )
        finally:
            gear.Placement = original
            self.doc.recompute()

    def test_saved_engagement_follows_root_placement_and_live_tilt(self):
        from gondola.validation.propulsion import gear_engagement_check

        root = self.module["group"]
        original = App.Placement(root.Placement)
        angle = float(self.doc.StarboardPod.Tilt)
        try:
            root.Placement = App.Placement(
                App.Vector(12, 27, -34), App.Rotation(App.Vector(1, 3, -2), 57)
            )
            self.doc.StarboardPod.Tilt = 123.4
            self.doc.recompute()
            result = gear_engagement_check(self.doc, "Starboard")
            self.assertTrue(result["passed"], result)
            self.assertAlmostEqual(
                result["minimum_tooth_face_overlap_under_travel_mm"], 3.0
            )
        finally:
            root.Placement = original
            self.doc.StarboardPod.Tilt = angle
            self.doc.recompute()

    def test_direct_adapter_rejects_wrong_bought_gear_bore(self):
        from gondola.validation.propulsion import direct_adapter_fit_check

        for prefix in ("Port", "Starboard"):
            result = direct_adapter_fit_check(self.doc, prefix)
            self.assertTrue(result["passed"], result)
            self.assertAlmostEqual(result["metal_projection_beyond_gear_mm"], 19.0)
        gear = self.doc.PortDriverGear
        original = gear.Shape.copy()
        try:
            axis = App.Vector(0, 1, 0)
            origin = App.Vector(0, gear.Shape.BoundBox.YMin, 0)
            wrong_bore = Part.makeCylinder(1.5, 8, origin, axis).cut(
                Part.makeCylinder(1.1, 8, origin, axis)
            )
            gear.Shape = original.fuse(wrong_bore).removeSplitter()
            self.doc.recompute()
            result = direct_adapter_fit_check(self.doc, "Port")
            self.assertFalse(result["passed"], result)
            self.assertGreater(result["gear_bore_intrusion_mm3"], 1)
        finally:
            gear.Shape = original
            self.doc.recompute()

    def test_input_end_grip_reserve_rejects_former_18_mm_stub(self):
        from gondola.validation.propulsion import direct_adapter_fit_check

        shaft = self.doc.PortInputShaft
        original = shaft.Shape.copy()
        try:
            bounds = original.optimalBoundingBox(False, False)
            old_end = Part.makeBox(
                bounds.XLength + 2,
                2.1,
                bounds.ZLength + 2,
                App.Vector(bounds.XMin - 1, bounds.YMax - 2, bounds.ZMin - 1),
            )
            shaft.Shape = original.cut(old_end)
            self.doc.recompute()
            self.assertTrue(shaft.Shape.isValid())
            self.assertEqual(len(shaft.Shape.Solids), 1)
            result = direct_adapter_fit_check(self.doc, "Port")
            self.assertFalse(result["passed"], result)
            self.assertGreater(result["missing_gear_end_reserve_mm3"], 10)
            self.assertLess(result["missing_metal_gear_engagement_mm3"], 1e-7)
        finally:
            shaft.Shape = original
            self.doc.recompute()

    def test_input_stub_stop_and_radial_jack_contacts_are_required(self):
        from gondola.validation.propulsion import input_shaft_retention_check

        for suffix, displacement, contact_key in (
            ("InputShaft", App.Vector(0, 0.2, 0), "shaft_stop_contact_mm2"),
            (
                "InputShaftClampBolt",
                App.Rotation(App.Vector(0, 1, 0), 240).multVec(App.Vector(-0.2, 0, 0)),
                "screw_tip_to_flat_contact_mm2",
            ),
            (
                "InputShaftClampNut",
                App.Rotation(App.Vector(0, 1, 0), 240).multVec(App.Vector(-0.2, 0, 0)),
                "nut_to_retaining_wall_contact_mm2",
            ),
        ):
            part = self.doc.getObject("Port" + suffix)
            original = App.Placement(part.Placement)
            try:
                part.Placement.Base = original.Base + displacement
                self.doc.recompute()
                result = input_shaft_retention_check(self.doc, "Port")
                self.assertFalse(result["passed"], result)
                self.assertLess(result[contact_key], 1e-5, result)
            finally:
                part.Placement = original
                self.doc.recompute()

    def test_driver_removal_detects_a_midpath_obstacle_with_clear_endpoints(self):
        from gondola.cad import translated_shape, world_shape
        from gondola.parts import propulsion
        from gondola.validation.geometry import intersection_volume
        from gondola.validation.propulsion_service import driver_lateral_service_check

        for prefix, sign in (("Port", 1), ("Starboard", -1)):
            with self.subTest(pod=prefix):
                gear = world_shape(self.doc.getObject(prefix + "DriverGear"))
                start, end = (0, sign * 1.5, 0), (sign * 40, sign * 1.5, 0)
                obstacle = Part.makeBox(
                    0.1,
                    0.2,
                    0.2,
                    App.Vector(
                        sign * (SELECTED_DRIVE.input_x_mm + 20) - 0.05,
                        sign * (propulsion.GEAR_HUB_START_Y + 4) - 0.1,
                        SELECTED_DRIVE.input_z_mm - 0.1,
                    ),
                )
                for endpoint in (start, end):
                    self.assertEqual(
                        intersection_volume(
                            translated_shape(gear, *endpoint), obstacle
                        ),
                        0,
                    )
                self.assertGreater(
                    intersection_volume(
                        translated_shape(gear, x=sign * 16, y=sign * 1.5), obstacle
                    ),
                    0,
                )
                result = driver_lateral_service_check(
                    gear, start, end, {"thin_wall": obstacle}, SELECTED_DRIVE, sign
                )
                self.assertFalse(result["passed"], result)
                self.assertGreater(
                    result["segments"][0]["intersection_mm3"]["thin_wall"], 0
                )

    def test_driver_sweep_cannot_ignore_geometry_outside_the_catalog_envelope(self):
        from gondola.cad import world_shape
        from gondola.parts import propulsion
        from gondola.validation.propulsion_service import driver_lateral_service_check

        gear = world_shape(self.doc.PortDriverGear)
        start, end = (0, 1.5, 0), (40, 1.5, 0)
        baseline = driver_lateral_service_check(gear, start, end, {}, SELECTED_DRIVE, 1)
        self.assertTrue(baseline["passed"], baseline)
        protrusion = Part.makeBox(
            1,
            1,
            1,
            App.Vector(
                SELECTED_DRIVE.input_x_mm + 20,
                propulsion.GEAR_FACE_START_Y,
                SELECTED_DRIVE.input_z_mm,
            ),
        )
        result = driver_lateral_service_check(
            gear.fuse(protrusion), start, end, {}, SELECTED_DRIVE, 1
        )
        self.assertFalse(result["passed"], result)
        self.assertGreater(result["gear_outside_reference_envelope_mm3"], 0.9)

    def test_servo_removal_keeps_the_thin_ear_in_the_continuous_sweep(self):
        from gondola.cad import translated_shape, world_shape
        from gondola.parts import servo_bridge
        from gondola.validation.geometry import intersection_volume
        from gondola.validation.propulsion_service import servo_lateral_service_check

        for prefix, sign in (("Port", 1), ("Starboard", -1)):
            with self.subTest(pod=prefix):
                servo = world_shape(self.doc.getObject(prefix + "Servo"))
                start, end = (0, 0, 0), (sign * 40, 0, 0)
                obstacle = Part.makeBox(
                    0.2,
                    0.2,
                    0.2,
                    App.Vector(
                        sign * (SELECTED_DRIVE.input_x_mm + 20) - 0.1,
                        sign * (servo_bridge.case_front_y() - 4.7 - 8 + 0.5) - 0.1,
                        SELECTED_DRIVE.input_z_mm + 8.3,
                    ),
                )
                for endpoint in (start, end):
                    self.assertEqual(
                        intersection_volume(
                            translated_shape(servo, *endpoint), obstacle
                        ),
                        0,
                    )
                # This height lies in the mounting ear, above the main case.
                self.assertGreater(
                    intersection_volume(translated_shape(servo, x=sign * 20), obstacle),
                    0,
                )
                result = servo_lateral_service_check(
                    servo, start, end, {"ear_obstacle": obstacle}
                )
                self.assertFalse(result["passed"], result)
                self.assertLess(result["uncovered_servo_volume_mm3"], 1e-5)
                self.assertTrue(
                    any(
                        segment["intersection_mm3"]["ear_obstacle"] > 0
                        for segment in result["segments"]
                    ),
                    result,
                )

    def test_wrong_input_rotation_direction_is_rejected(self):
        from gondola.validation.propulsion import drive_motion_check

        drive = self.doc.PortInputDrive
        expression = next(
            str(value)
            for path, value in drive.ExpressionEngine
            if str(path).endswith("Rotation.Angle")
        )
        try:
            drive.setExpression(
                "Placement.Rotation.Angle",
                f"PortPod.Placement.Rotation.Angle / {SELECTED_DRIVE.ratio:g}",
            )
            result = drive_motion_check(self.doc, "Port")
            self.assertFalse(result["passed"], result)
        finally:
            drive.setExpression("Placement.Rotation.Angle", expression)
            self.doc.recompute()

    def test_real_tooth_outlines_clear_across_a_complete_tooth_phase(self):
        from gondola.validation.propulsion import gear_rotation_check

        for prefix in ("Port", "Starboard"):
            result = gear_rotation_check(self.doc, prefix)
            self.assertTrue(result["passed"], result)

    def test_four_output_bearings_are_captured(self):
        from gondola.validation.propulsion import output_bearing_stack_check

        for prefix in ("Port", "Starboard"):
            for suffix in ("Inboard", "Outboard"):
                result = output_bearing_stack_check(self.doc, prefix, suffix)
                self.assertTrue(result["passed"], (prefix, suffix, result))

    def test_outward_rotor_service_rejects_a_midpath_obstacle(self):
        from gondola.cad import translated_shape, world_shape
        from gondola.validation.propulsion import output_carrier_service_check

        obstacle = self.doc.addObject("Part::Feature", "RotorServiceBlocker")
        self.module["group"].addObject(obstacle)
        obstacle.Shape = Part.makeBox(0.2, 0.2, 0.2, App.Vector(9, 130, 50))
        modified = dict(self.module)
        modified["references"] = self.module["references"] + [obstacle]
        try:
            carrier = world_shape(self.doc.PortMotorCarrier)
            self.assertLess(carrier.common(obstacle.Shape).Volume, 1e-7)
            self.assertLess(
                translated_shape(carrier, y=60).common(obstacle.Shape).Volume, 1e-7
            )
            result = output_carrier_service_check(self.doc, modified, "Port")
            self.assertFalse(result["passed"], result)
            self.assertTrue(any(not row["passed"] for row in result["carrier_removal"]))
        finally:
            self.doc.removeObject(obstacle.Name)
            self.doc.recompute()

    def test_output_stubs_cannot_be_replaced_by_a_shaft_through_the_motor(self):
        from gondola.cad import world_shape
        from gondola.parts import propulsion
        from gondola.validation.propulsion import output_stub_check

        motor = world_shape(self.doc.PortMotor)
        pivot_y = self.doc.PortPod.getGlobalPlacement().Base.y
        for suffix in ("Negative",):
            result = output_stub_check(
                world_shape(self.doc.getObject("PortOutputShaft" + suffix)),
                motor,
                pivot_y,
            )
            self.assertTrue(result["passed"], result)
        through_shaft = Part.makeCylinder(
            1.5,
            60,
            App.Vector(0, pivot_y - 30, propulsion.PIVOT_Z),
            App.Vector(0, 1, 0),
        )
        result = output_stub_check(through_shaft, motor, pivot_y)
        self.assertFalse(result["passed"])
        self.assertGreater(result["motor_overlap_mm3"], 0)

    def clamp_stack(self):
        from gondola.cad import world_shape

        return (
            Part.makeCompound(
                [
                    world_shape(self.doc.PropulsionFixedFrame),
                    world_shape(self.doc.PortBearingCap),
                ]
            ),
            world_shape(self.doc.PortBearingCapPositiveBolt),
            world_shape(self.doc.PortBearingCapPositiveNut),
        )

    def test_split_clamp_has_seated_fasteners_and_full_nut_engagement(self):
        from gondola.validation.propulsion import clamp_fastener_check

        result = clamp_fastener_check(*self.clamp_stack())
        self.assertTrue(result["passed"], result)
        self.assertAlmostEqual(result["nut_engagement_length_mm"], 1.6)

    def test_servo_ear_fasteners_have_seated_heads_and_complete_smaller_nuts(self):
        from gondola.cad import world_shape
        from gondola.validation.propulsion import clamp_fastener_check

        for prefix in ("Port", "Starboard"):
            clamp = Part.makeCompound(
                [
                    world_shape(self.doc.getObject(prefix + "Servo")),
                    world_shape(self.doc.PropulsionFixedFrame),
                ]
            )
            for suffix in ("Lower", "Upper"):
                result = clamp_fastener_check(
                    clamp,
                    world_shape(
                        self.doc.getObject(prefix + "ServoEar" + suffix + "Bolt")
                    ),
                    world_shape(
                        self.doc.getObject(prefix + "ServoEar" + suffix + "Nut")
                    ),
                    thread_diameter=1.6,
                    nut_height=1.3,
                )
                self.assertTrue(result["passed"], (prefix, suffix, result))
                self.assertAlmostEqual(result["nut_engagement_length_mm"], 1.3)

    def test_unseated_clamp_nut_is_rejected(self):
        from gondola.cad import translated_shape
        from gondola.validation.propulsion import clamp_fastener_check

        clamp, bolt, nut = self.clamp_stack()
        result = clamp_fastener_check(clamp, bolt, translated_shape(nut, z=0.2))
        self.assertFalse(result["passed"], result)
        self.assertFalse(result["contacts"][1]["passed"])

    def test_bolt_must_cross_the_full_clamp_nut(self):
        from gondola.cad import translated_shape
        from gondola.validation.propulsion import clamp_fastener_check

        clamp, bolt, nut = self.clamp_stack()
        result = clamp_fastener_check(clamp, translated_shape(bolt, z=2), nut)
        self.assertFalse(result["passed"], result)
        self.assertGreater(result["missing_bolt_thread_core_mm3"], 0)

    def test_each_output_d_socket_has_keyed_torque_and_tip_retention(self):
        from gondola.validation.propulsion import carrier_shaft_retention_check

        for prefix in ("Port", "Starboard"):
            result = carrier_shaft_retention_check(self.doc, prefix)
            self.assertTrue(result["passed"], result)
            self.assertAlmostEqual(result["screw_head_to_carrier_gap_mm"], 2)

    def test_output_round_oversize_socket_cannot_claim_d_key_retention(self):
        from gondola.validation.propulsion import carrier_shaft_retention_check

        carrier = self.doc.PortMotorCarrier
        original = carrier.Shape.copy()
        try:
            carrier.Shape = original.cut(
                Part.makeCylinder(
                    1.6, 10.1, App.Vector(0, -30.55, 0), App.Vector(0, 1, 0)
                )
            )
            self.doc.recompute()
            result = carrier_shaft_retention_check(self.doc, "Port")
            self.assertFalse(result["passed"], result)
        finally:
            carrier.Shape = original
            self.doc.recompute()

    def test_output_jack_tip_gap_cannot_claim_shaft_grip(self):
        from gondola.validation.propulsion import carrier_shaft_retention_check

        bolt = self.doc.PortOutputClampNegativeBolt
        original = App.Placement(bolt.Placement)
        try:
            bolt.Placement.Base += App.Vector(0.2, 0, 0)
            self.doc.recompute()
            result = carrier_shaft_retention_check(self.doc, "Port")
            self.assertFalse(result["passed"], result)
            self.assertLess(result["screw_tip_to_flat_contact_mm2"], 1e-5)
        finally:
            bolt.Placement = original
            self.doc.recompute()

    def test_output_shaft_requires_the_literal_two_flat_stock(self):
        from gondola.validation.propulsion import carrier_shaft_retention_check

        shaft = self.doc.PortOutputShaftNegative
        original = shaft.Shape.copy()
        try:
            shaft.Shape = original.cut(
                Part.makeBox(0.5, 1, 4, App.Vector(-1.5, -25, -2))
            )
            self.doc.recompute()
            self.assertFalse(carrier_shaft_retention_check(self.doc, "Port")["passed"])
        finally:
            shaft.Shape = original
            self.doc.recompute()

    def test_bought_gears_bearings_and_shafts_are_never_print_parts(self):
        hardware = self.module["hardware"]
        self.assertEqual(
            sum(obj.HardwareSKU == "BEARING_3X6X2_5" for obj in hardware), 6
        )
        self.assertEqual(
            sum(
                str(obj.HardwareSKU).startswith("ALI_KAILASH_M05_") for obj in hardware
            ),
            4,
        )
        self.assertEqual(
            sum(str(obj.HardwareSKU).startswith("SS304_CUT3_") for obj in hardware), 4
        )
        self.assertTrue(
            all(not bool(getattr(obj, "PrintPart", False)) for obj in hardware)
        )
        self.assertTrue(
            all(len(obj.Shape.Solids) == 1 for obj in self.module["printed"])
        )


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class SelectedGearDriveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.parts import propulsion

        cls.configurations = {}
        for key, configuration in DRIVE_CONFIGURATIONS.items():
            doc = App.newDocument("SelectedDrive" + key)
            cls.configurations[key] = (
                doc,
                propulsion.build_propulsion_module(doc, drive=configuration),
            )
            propulsion.build_fit_coupons(doc)

    @classmethod
    def tearDownClass(cls):
        for doc, _ in cls.configurations.values():
            App.closeDocument(doc.Name)

    def test_selected_parts_match_asymmetric_gears_and_prepared_input_stubs(self):
        from gondola.validation.geometry import local_shape

        doc, module = self.configurations["48_16"]
        self.assertEqual(set(self.configurations), {"48_16"})
        self.assertEqual(doc.PropulsionFixedFrame.PrintSKU, "PropulsionFixedFrame")
        self.assertEqual(module["frame"].PrintSKU, "PropulsionFixedFrame")
        for prefix in ("Port", "Starboard"):
            for suffix, spec in (
                ("DriverGear", SELECTED_DRIVE.driver),
                ("OutputGear", SELECTED_DRIVE.output),
            ):
                gear = doc.getObject(prefix + suffix)
                self.assertEqual(gear.HardwareSKU, spec.sku)
                self.assertAlmostEqual(
                    gear.Shape.BoundBox.YLength, spec.total_length_mm
                )
            shaft = doc.getObject(prefix + "InputShaft")
            self.assertEqual(shaft.HardwareSKU, "SS304_CUT3_L35_FLAT16_A0")
            self.assertAlmostEqual(shaft.Shape.BoundBox.YLength, 35)
            canonical_shaft = local_shape(shaft)
            canonical_shaft.rotate(App.Vector(), App.Vector(0, 1, 0), -240)
            self.assertAlmostEqual(
                canonical_shaft.optimalBoundingBox(False, False).XLength, 3.0
            )
            self.assertAlmostEqual(
                canonical_shaft.optimalBoundingBox(False, False).ZLength, 3.0
            )
            self.assertFalse(bool(getattr(shaft, "PrintPart", False)))

    def test_integrated_support_and_ordered_gear_preparation(self):
        from gondola.validation.propulsion import (
            integrated_frame_check,
            servo_service_preparation_check,
        )

        for doc, module in self.configurations.values():
            fixed = integrated_frame_check(doc, module)
            self.assertTrue(fixed["passed"], fixed)
            self.assertEqual(fixed["registered_print_count"], 1)
            self.assertIsNone(doc.getObject("ServoDriveBridge"))
            result = servo_service_preparation_check(doc, module)
            self.assertTrue(result["passed"], result)
            self.assertEqual(
                result["removed_parts"], ["PortOutputGear", "StarboardOutputGear"]
            )
            self.assertIn("PropulsionFixedFrame", result["retained_parts"])
            for side in ("Port", "Starboard"):
                self.assertIn(side + "BearingCap", result["retained_parts"])
                self.assertIn(side + "OutputBearingInboard", result["retained_parts"])
                self.assertIn(side + "MotorCarrier", result["retained_parts"])

    def test_output_gear_preparation_rejects_a_midpath_obstacle(self):
        from gondola.cad import translated_shape, world_shape
        from gondola.validation.propulsion import (
            input_drive_service_check,
            servo_service_preparation_check,
        )

        doc, module = self.configurations["48_16"]
        witness = doc.addObject("Part::Feature", "GearPreparationBlocker")
        module["group"].addObject(witness)
        witness.Shape = Part.makeBox(0.2, 0.2, 0.2, App.Vector(2.4, 8, 63))
        modified = {**module, "references": module["references"] + [witness]}
        try:
            gear = world_shape(doc.PortOutputGear)
            for offset in ((0, 0, 0), (0, -11, 0), (0, -11, 20), (30, -11, 20)):
                self.assertLess(
                    translated_shape(gear, *offset).common(witness.Shape).Volume, 1e-7
                )
            self.assertGreater(
                translated_shape(gear, y=-11, z=12).common(witness.Shape).Volume, 0
            )
            result = servo_service_preparation_check(doc, modified)
            self.assertFalse(result["passed"], result)
            following = input_drive_service_check(
                doc, modified, "Port", module_release=result
            )
            self.assertFalse(following["passed"], following)
            self.assertFalse(following["preparation_passed"])
        finally:
            doc.removeObject(witness.Name)
            doc.recompute()

    def test_metal_input_parts_cannot_be_misclassified_as_fixed_obstacles(self):
        from unittest.mock import patch

        from gondola.validation.relative_motion import relative_motion_check

        doc, module = self.configurations["48_16"]
        for suffix in ("InputShaft", "InputShaftClampBolt", "InputShaftClampNut"):
            part = doc.getObject("Port" + suffix)
            try:
                doc.PortServoMount.addObject(part)
                doc.recompute()
                with patch(
                    "gondola.validation.relative_motion._certify_pair"
                ) as certify:
                    result = relative_motion_check(doc, module)
                    self.assertFalse(result["passed"], result)
                    self.assertIn("missing or misplaced", result["error"])
                    certify.assert_not_called()
            finally:
                doc.PortInputDrive.addObject(part)
                doc.recompute()

    def test_servo_parent_displacement_cannot_hide_behind_correct_local_datums(self):
        from gondola.validation.propulsion import fixed_servo_datum_check

        for key, (doc, _) in self.configurations.items():
            group = doc.ServoDriveModule
            original = App.Placement(group.Placement)
            local_datums = {
                prefix: App.Placement(doc.getObject(prefix + "ServoMount").Placement)
                for prefix in ("Port", "Starboard")
            }
            changes = (
                App.Placement(original.Base + App.Vector(0.2, 0, 0), original.Rotation),
                App.Placement(original.Base + App.Vector(0, 0, 0.2), original.Rotation),
                App.Placement(original.Base, App.Rotation(App.Vector(0, 1, 0), 0.1)),
            )
            try:
                for placement in changes:
                    group.Placement = placement
                    doc.recompute()
                    for prefix in ("Port", "Starboard"):
                        with self.subTest(
                            configuration=key, pod=prefix, placement=str(placement)
                        ):
                            self.assertTrue(
                                doc.getObject(prefix + "ServoMount").Placement.isSame(
                                    local_datums[prefix], 1e-7
                                )
                            )
                            result = fixed_servo_datum_check(doc, prefix)
                            self.assertFalse(result["passed"], result)
            finally:
                group.Placement = original
                doc.recompute()

    def test_shifted_integrated_frame_loses_actual_servo_seating(self):
        from gondola.validation.propulsion import servo_mount_check

        doc, module = self.configurations["48_16"]
        frame = doc.PropulsionFixedFrame
        original = App.Placement(frame.Placement)
        try:
            frame.Placement.Base.z += 0.2
            doc.recompute()
            self.assertEqual(frame.PrintSKU, "PropulsionFixedFrame")
            result = servo_mount_check(doc, "Port")
            self.assertFalse(result["passed"], result)
        finally:
            frame.Placement = original
            doc.recompute()

    def test_native_motion_teeth_and_mounts_follow_selected_configuration(self):
        from gondola.validation.propulsion import (
            drive_motion_check,
            fixed_servo_datum_check,
            rail_mount_clearance_check,
            servo_mount_check,
        )

        for key, (doc, module) in self.configurations.items():
            configuration = DRIVE_CONFIGURATIONS[key]
            for prefix in ("Port", "Starboard"):
                with self.subTest(configuration=key, pod=prefix):
                    motion = drive_motion_check(doc, prefix)
                    self.assertTrue(motion["passed"], motion)
                    for case in motion["cases"]:
                        self.assertAlmostEqual(
                            case["required_servo_deg"],
                            -case["bounded_output_deg"] / configuration.ratio,
                        )
                    for check in (
                        fixed_servo_datum_check,
                        servo_mount_check,
                    ):
                        result = check(doc, prefix)
                        self.assertTrue(result["passed"], result)
            row = rail_mount_clearance_check(doc, module)
            self.assertTrue(row["passed"], (key, row))

    def test_shaft_and_driver_leave_before_compact_servo_unit_service(self):
        from gondola.validation.propulsion import (
            input_drive_service_check,
            servo_case_service_check,
        )

        for doc, module in self.configurations.values():
            for prefix, sign in (("Port", 1), ("Starboard", -1)):
                result = input_drive_service_check(doc, module, prefix)
                self.assertTrue(result["passed"], result)
                moving = {
                    prefix + suffix
                    for suffix in (
                        "Servo",
                        "ServoHorn",
                        "HornGearAdapter",
                        "InputShaftClampBolt",
                        "InputShaftClampNut",
                        "HornGearClampNearBolt",
                        "HornGearClampFarBolt",
                        "HornGearClampNearNut",
                        "HornGearClampFarNut",
                    )
                }
                self.assertEqual(set(result["moving_parts"]), moving)
                self.assertEqual(
                    result["required_prior_check"], "servo_service_preparation"
                )
                self.assertTrue(result["preparation_passed"])
                self.assertIn("PropulsionFixedFrame", result["retained_parts"])
                self.assertIn(prefix + "BearingCap", result["retained_parts"])
                self.assertEqual({row["part"] for row in result["part_paths"]}, moving)
                for row in result["part_paths"]:
                    self.assertEqual(
                        row["waypoints_mm"],
                        [
                            (0, 0, 0),
                            (0, sign * 13, 0),
                            (sign * 60, sign * 13, 0),
                        ],
                    )
                    self.assertTrue(row["passed"], row)
                    obstacles = (
                        row["segments"][0]["obstacles"]
                        if row["part"].endswith("HornGearAdapter")
                        else row["obstacles"]
                    )
                    self.assertEqual(set(obstacles), set(result["retained_parts"]))
                    self.assertIn("PropulsionFixedFrame", obstacles)
                self.assertEqual(set(result["bench_members"]), moving)
                for key in (
                    "driver_gear_removal",
                    "input_stub_removal",
                    "input_jack_release",
                    "input_stub_grip_tool",
                    "output_rotor_parking",
                    "adapter_release_off_frame",
                ):
                    self.assertTrue(result[key]["passed"], result[key])
                self.assertTrue(
                    all(
                        row["passed"]
                        for row in result["ear_fastener_release"]
                        + result["rear_holding_tool_off_frame"]
                    )
                )
                self.assertIn(
                    "PropulsionFixedFrame", result["driver_gear_removal"]["obstacles"]
                )
                self.assertNotIn(
                    prefix + "InputShaft", result["driver_gear_removal"]["obstacles"]
                )
                self.assertIn(
                    prefix + "DriverGear", result["input_stub_removal"]["obstacles"]
                )
                self.assertEqual(result["service_mode"], "shaft_first_compact_frame")
                self.assertEqual(
                    result["input_stub_removal"]["waypoints_mm"],
                    [(0, 0, 0), (0, sign * 32, 0), (sign * 60, sign * 32, 0)],
                )
                parking = result["output_rotor_parking"]
                self.assertEqual(parking["angle_deg"], 90)
                self.assertTrue(parking["initial_input_and_output_neutral"])
                self.assertIn(prefix + "InputBearing", parking["retained_parts"])
                self.assertIn(prefix + "InputBearing", result["retained_parts"])
                self.assertEqual(
                    result["driver_gear_removal"]["waypoints_mm"],
                    [(0, 0, 0), (sign * 60, 0, 0)],
                )
                self.assertEqual(result["input_jack_release"]["backoff_mm"], 0.2)
                case = servo_case_service_check(
                    doc, module, prefix, prior_service=result
                )
                self.assertTrue(case["passed"])
                self.assertEqual(case["required_prior_check"], "input_drive_service")

    def test_horn_fastener_report_retains_the_other_joint_until_ordered_release(self):
        from gondola.cad import world_shape
        from gondola.validation.propulsion import (
            _record_bearing_checks,
            _record_fastener_checks,
            input_drive_service_check,
            output_carrier_service_check,
        )

        doc, module = self.configurations["48_16"]
        physical = {
            obj.Name: world_shape(obj)
            for obj in module["printed"] + module["hardware"] + module["references"]
        }
        report = {
            "fastener_stacks": [],
            "fastener_service": [],
            "output_carrier_service": [
                output_carrier_service_check(doc, module, prefix)
                for prefix in ("Port", "Starboard")
            ],
            "gear_service": [
                {"gear": prefix + "OutputGear", "passed": True}
                for prefix in ("Port", "Starboard")
            ],
            "input_drive_service": [
                input_drive_service_check(doc, module, prefix)
                for prefix in ("Port", "Starboard")
            ],
            "bearing_service": [],
            "input_bearing_service": [],
            "bearing_stacks": [],
        }
        for prefix in ("Port", "Starboard"):
            _record_bearing_checks(report, doc, module, prefix, physical)
        _record_fastener_checks(report, module, physical)
        for prefix in ("Port", "Starboard"):
            rows = {row["bolt"]: row for row in report["fastener_service"]}
            for side in ("Lower", "Upper"):
                bolt_name = prefix + "ServoEar" + side + "Bolt"
                ear = rows[bolt_name]
                self.assertFalse(ear["bolt_retained_in_servo_unit"])
                self.assertTrue(ear["screw_first_with_nut_held_in_guides"])
                self.assertNotIn(bolt_name, ear["retained_service_parts"])
                self.assertIn(bolt_name, ear["removed_local_parts"])
            far = rows[prefix + "HornGearClampFarBolt"]
            near = rows[prefix + "HornGearClampNearBolt"]
            self.assertTrue(far["passed"], far)
            self.assertTrue(near["passed"], near)
            self.assertIn(
                prefix + "HornGearClampNearBolt", far["retained_service_parts"]
            )
            self.assertIn(prefix + "HornGearClampFarNut", near["removed_local_parts"])
            for row, position in ((far, "Far"), (near, "Near")):
                self.assertEqual(
                    row["nut"], prefix + "HornGearClamp" + position + "Nut"
                )
                self.assertIn(row["nut"], row["removed_local_parts"])
                for kept in ("Near", "Far"):
                    name = prefix + "HornGearClamp" + kept + "Bolt"
                    self.assertIn(name, row["retained_service_parts"])
                    self.assertNotIn(name, row["removed_local_parts"])
            self.assertIn(
                {
                    "check": "fastener_service",
                    "object": prefix + "HornGearClampFarBolt",
                    "passed": True,
                },
                near["service_dependencies"],
            )

    def test_horn_obstruction_cannot_hide_from_ear_screw_first_removal(self):
        from gondola.validation.horn_coupling import assembled_servo_service_check

        doc, module = self.configurations["48_16"]
        adapter = doc.PortHornGearAdapter
        original = adapter.Shape.copy()
        try:
            # The fitted horn unit remains an obstacle while each ear screw
            # withdraws. This boss clears the seated head but blocks its path.
            obstruction = Part.makeBox(1, 1, 1, App.Vector(-0.5, 8, 6.5))
            obstruction.Placement = (
                adapter.Placement.multiply(adapter.getGlobalPlacement().inverse())
                .multiply(doc.PortServoMount.getGlobalPlacement())
                .multiply(obstruction.Placement)
            )
            adapter.Shape = Part.makeCompound([original, obstruction])
            result = assembled_servo_service_check(doc, module, "Port")
            self.assertFalse(result["passed"], result)
            upper = result["ear_fastener_release"][1]
            self.assertFalse(upper["bolt_axial_withdrawal"]["passed"], upper)
        finally:
            adapter.Shape = original
            doc.recompute()

    def test_lateral_servo_route_rejects_an_obstruction_between_endpoints(self):
        from gondola.cad import translated_shape, world_shape
        from gondola.validation.propulsion import servo_case_service_check

        doc, module = self.configurations["48_16"]
        case = world_shape(doc.PortServo)
        centre = doc.PortServoMount.getGlobalPlacement().multVec(
            App.Vector(0, -1.1, -5)
        ) + App.Vector(30, 13, 0)
        blocker = doc.addObject("Part::Feature", "LateralServoBlocker")
        module["group"].addObject(blocker)
        blocker.Shape = Part.makeBox(0.2, 0.2, 0.2, centre - App.Vector(0.1, 0.1, 0.1))
        modified = {**module, "references": module["references"] + [blocker]}
        try:
            self.assertLess(case.common(blocker.Shape).Volume, 1e-7)
            self.assertLess(
                translated_shape(case, x=60, y=13).common(blocker.Shape).Volume, 1e-7
            )
            self.assertGreater(
                translated_shape(case, x=30, y=13).common(blocker.Shape).Volume, 0
            )
            result = servo_case_service_check(doc, modified, "Port")
            self.assertFalse(result["passed"], result)
            self.assertFalse(
                next(row for row in result["part_paths"] if row["part"] == "PortServo")[
                    "passed"
                ]
            )
        finally:
            doc.removeObject(blocker.Name)
            doc.recompute()

    def test_service_cannot_omit_retained_or_removed_physical_parts(self):
        from gondola.validation.propulsion import (
            input_drive_service_check,
            servo_case_service_check,
            servo_service_preparation_check,
        )

        doc, module = self.configurations["48_16"]
        for name in (
            "PortInputShaft",
            "PortInputShaftClampBolt",
            "PortInputShaftClampNut",
            "PortHornGearClampNearBolt",
            "PortHornGearClampNearNut",
            "PortHornGearClampFarNut",
            "PortServoHorn",
            "PortHornGearAdapter",
            "PortOutputShaftNegative",
            "PortOutputBearingOutboard",
            "PortInputBearing",
            "PortBearingCapInputBolt",
            "PortBearingCapInputNut",
            "PropulsionFixedFrame",
            "PortBearingCap",
            "PortServoEarLowerNut",
        ):
            incomplete = {
                **module,
                **{
                    category: [obj for obj in module[category] if obj.Name != name]
                    for category in ("printed", "hardware", "references")
                },
            }
            for check in (input_drive_service_check, servo_case_service_check):
                with self.subTest(part=name, check=check.__name__):
                    result = check(doc, incomplete, "Port")
                    self.assertFalse(result["passed"], result)
                    self.assertEqual(result["missing_parts"], [name])
            with self.subTest(part=name, check="servo_service_preparation_check"):
                result = servo_service_preparation_check(doc, incomplete)
                self.assertFalse(result["passed"], result)
                self.assertEqual(result["missing_parts"], [name])

    def test_correct_direction_with_wrong_ratio_is_rejected(self):
        from gondola.validation.propulsion import drive_motion_check

        doc, _ = self.configurations["48_16"]
        drive = doc.PortInputDrive
        expression = next(
            str(value)
            for path, value in drive.ExpressionEngine
            if str(path).endswith("Rotation.Angle")
        )
        try:
            drive.setExpression(
                "Placement.Rotation.Angle", "-PortPod.Placement.Rotation.Angle / 3.2"
            )
            result = drive_motion_check(doc, "Port")
            self.assertFalse(result["passed"], result)
        finally:
            drive.setExpression("Placement.Rotation.Angle", expression)
            doc.recompute()

    def test_saved_contract_is_not_a_live_ratio_override(self):
        from gondola.contracts.drive import drive_for_document
        from gondola.validation.baseline import native_interface_metadata

        doc, _ = self.configurations["48_16"]
        module = doc.MainPropulsionModule
        original = module.DriveContract
        metadata = native_interface_metadata(doc)
        self.assertEqual(metadata[module.Name]["GearConfiguration"], "48_16")
        try:
            altered = json.loads(original)
            altered["angle_ratio"] = -3.2
            module.DriveContract = json.dumps(altered)
            self.assertNotEqual(native_interface_metadata(doc), metadata)
            with self.assertRaisesRegex(ValueError, "differs"):
                drive_for_document(doc)
        finally:
            module.DriveContract = original

    def test_shifted_or_rotated_servo_axis_is_rejected(self):
        from gondola.validation.propulsion import fixed_servo_datum_check

        for key, (doc, _) in self.configurations.items():
            mount = doc.PortServoMount
            original = App.Placement(mount.Placement)
            try:
                with self.subTest(configuration=key, change="position"):
                    mount.Placement.Base = original.Base + App.Vector(0.02, 0, 0)
                    doc.recompute()
                    result = fixed_servo_datum_check(doc, "Port")
                    self.assertFalse(result["passed"], result)
                with self.subTest(configuration=key, change="rotation"):
                    mount.Placement = App.Placement(
                        original.Base, App.Rotation(App.Vector(0, 1, 0), 0.1)
                    )
                    doc.recompute()
                    result = fixed_servo_datum_check(doc, "Port")
                    self.assertFalse(result["passed"], result)
            finally:
                mount.Placement = original
                doc.recompute()

    def test_stale_adjustment_property_or_live_datum_expression_is_rejected(self):
        from gondola.validation.propulsion import fixed_servo_datum_check

        doc, _ = self.configurations["48_16"]
        mount = doc.PortServoMount
        try:
            mount.addProperty("App::PropertyLength", "MeshClearance")
            result = fixed_servo_datum_check(doc, "Port")
            self.assertFalse(result["passed"], result)
        finally:
            mount.removeProperty("MeshClearance")
        try:
            # A currently correct expression would allow future drift.
            mount.setExpression("Placement.Base.x", f"{SELECTED_DRIVE.input_x_mm:g} mm")
            doc.recompute()
            result = fixed_servo_datum_check(doc, "Port")
            self.assertFalse(result["passed"], result)
        finally:
            mount.setExpression("Placement.Base.x", None)
            doc.recompute()

    def test_wrong_bridge_identity_is_rejected(self):
        from gondola.validation.propulsion import fixed_servo_datum_check

        doc, _ = self.configurations["48_16"]
        support = doc.PropulsionFixedFrame
        original = support.PrintSKU
        try:
            support.PrintSKU = "ServoDriveBridge60T"
            result = fixed_servo_datum_check(doc, "Port")
            self.assertFalse(result["passed"], result)
        finally:
            support.PrintSKU = original

    def test_shifted_cradle_geometry_is_rejected_with_correct_metadata(self):
        from gondola.validation.propulsion import servo_mount_check

        doc, _ = self.configurations["48_16"]
        bridge = doc.PropulsionFixedFrame
        original = bridge.Shape.copy()
        try:
            shifted = original.copy()
            shifted.translate(App.Vector(2, 0, 0))
            bridge.Shape = shifted
            doc.recompute()
            self.assertEqual(bridge.PrintSKU, "PropulsionFixedFrame")
            result = servo_mount_check(doc, "Port")
            self.assertFalse(result["passed"], result)
        finally:
            bridge.Shape = original
            doc.recompute()

    def test_servo_ear_seat_gap_is_rejected_without_changing_mount_datum(self):
        from gondola.validation.propulsion import (
            fixed_servo_datum_check,
            servo_mount_check,
        )

        doc, _ = self.configurations["48_16"]
        for prefix, sign in (("Port", 1), ("Starboard", -1)):
            servo = doc.getObject(prefix + "Servo")
            original = App.Placement(servo.Placement)
            try:
                # Moving only the case opens the actual ear/support joint while
                # the parent datum and the frame identity remain correct.
                servo.Placement.Base = original.Base + App.Vector(0, sign * 0.2, 0)
                doc.recompute()
                self.assertTrue(fixed_servo_datum_check(doc, prefix)["passed"])
                result = servo_mount_check(doc, prefix)
                self.assertFalse(result["passed"], (prefix, result))
            finally:
                servo.Placement = original
                doc.recompute()

    def test_servo_case_tolerance_leaves_point_one_mm_in_compact_closed_frame(self):
        from gondola.cad import box

        doc, _ = self.configurations["48_16"]
        x, z = SELECTED_DRIVE.input_x_mm, SELECTED_DRIVE.input_z_mm
        # Literal7x20 body enlarged0.2mm across both radial dimensions, with
        # the whole16.6mm body depth at the final8mm inward mounting offset.
        largest_case_section = box(7.2, 16.6, 20.2, (x - 3.6, 7.2 - 16.6 - 8, z - 15.1))
        opposite = largest_case_section.copy()
        opposite.rotate(App.Vector(), App.Vector(0, 0, 1), 180)
        frame = doc.PropulsionFixedFrame.Shape
        for section in (largest_case_section, opposite):
            self.assertLess(frame.common(section).Volume, 1e-7)
            self.assertAlmostEqual(frame.distToShape(section)[0], 0.1, places=6)

    def test_fixed_mount_checks_follow_the_whole_module_placement(self):
        from gondola.validation.propulsion import (
            fixed_servo_datum_check,
            input_drive_service_check,
            integrated_frame_check,
            servo_case_service_check,
            servo_mount_check,
            servo_service_preparation_check,
        )

        doc, module_parts = self.configurations["48_16"]
        module = doc.MainPropulsionModule
        original = App.Placement(module.Placement)
        try:
            module.Placement = App.Placement(
                App.Vector(36, 0.45, 2), App.Rotation(App.Vector(1, 2, 3), 13)
            )
            doc.recompute()
            result = integrated_frame_check(doc, module_parts)
            self.assertTrue(result["passed"], result)
            module_release = servo_service_preparation_check(doc, module_parts)
            self.assertTrue(module_release["passed"], module_release)
            for prefix in ("Port", "Starboard"):
                for check in (
                    fixed_servo_datum_check,
                    servo_mount_check,
                ):
                    with self.subTest(pod=prefix, check=check.__name__):
                        result = check(doc, prefix)
                        self.assertTrue(result["passed"], result)
                service = input_drive_service_check(
                    doc, module_parts, prefix, module_release=module_release
                )
                self.assertTrue(service["passed"], service)
                case_service = servo_case_service_check(
                    doc, module_parts, prefix, prior_service=service
                )
                self.assertTrue(case_service["passed"], case_service)
        finally:
            module.Placement = original
            doc.recompute()

    def test_servo_bridge_collision_is_rejected_even_with_seated_bolts(self):
        from gondola.cad import world_shape
        from gondola.validation.propulsion import servo_mount_check

        doc, _ = self.configurations["48_16"]
        bridge = doc.PropulsionFixedFrame
        original = bridge.Shape.copy()
        try:
            bridge.Shape = original.fuse(world_shape(doc.PortServo))
            doc.recompute()
            result = servo_mount_check(doc, "Port")
            self.assertFalse(result["passed"], result)
            self.assertGreater(result["servo_frame_intersection_mm3"], 1)
        finally:
            bridge.Shape = original
            doc.recompute()


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class SavedDriveManufacturingTests(unittest.TestCase):
    def test_wall_probes_follow_saved_selected_drive_and_root_transform(self):
        from gondola.parts import (
            equipment_mounts,
            instrument_mount,
            optical_mount,
            propulsion,
            rail,
        )
        from gondola.validation.manufacturing import review
        from gondola.validation.propulsion import _record_print_checks
        from gondola.validation.propulsion_evidence import PROPULSION_EVIDENCE_COUNTS
        from gondola.validation.propulsion_service import module_service_shapes

        selected = SELECTED_DRIVE
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "selected_drive.FCStd"
            doc = App.newDocument("SavedSelectedDriveWalls")
            try:
                module = propulsion.build_propulsion_module(doc, drive=selected)
                module_names = {
                    key: [obj.Name for obj in module[key]]
                    for key in ("printed", "hardware", "references")
                }
                # A nonzero module placement also exercises the measurement's
                # conversion from global coordinates back to the module frame.
                doc.MainPropulsionModule.Placement.Base = App.Vector(36, 0.45, 0)
                rail.build_rail(doc)
                host = doc.addObject("App::Part", "BatteryEquipmentModule")
                equipment_mounts.build_mount(doc, host, "battery")
                electronics = doc.addObject("App::Part", "ElectronicsEquipmentModule")
                instrument = instrument_mount.build_mount(doc, electronics)
                accessory = doc.addObject("App::Part", "AccessoryEquipmentModule")
                equipment_mounts.build_mount(doc, accessory, "accessory")
                optical_mount.build_optical_mount(doc, instrument["pitch_stage"])
                doc.recompute()
                doc.saveAs(str(path))
            finally:
                App.closeDocument(doc.Name)

            saved = App.openDocument(str(path), hidden=True)
            try:
                saved.recompute()
                registry = SimpleNamespace(
                    PrintedParts=[saved.PropulsionFixedFrame],
                    RailSegments=[saved.ContinuousRail],
                )
                result = review(saved, registry)
                measurements = {
                    row["feature"]: row for row in result["actual_feature_measurements"]
                }
                # Literal saved-shape expectations keep the probe datums from
                # drifting together with production constants. In particular,
                # the raised beam is not at the central rail-foot bottom.
                expected_sections = {
                    "frame_foot_thickness": 5.0,
                    "rail_straight_base_width": 6.0,
                    "carrier_roof": 3.0,
                    "carrier_nut_pocket_bottom_opening": 0,
                    "frame_crossbeam": 5.0,
                    "integrated_saddle_roof": 3.0,
                    "bearing_cap_roof": 1.5,
                    "bearing_cap_nut_floor": 2.5,
                    "guard_radial_wall": 3.0,
                    "guard_axial_wall": 3.0,
                    "guard_root_fan": 3.0,
                    "guard_rear_bridge": 3.0,
                    "guard_outer_return": 3.0,
                }
                for feature, expected in expected_sections.items():
                    with self.subTest(saved_section=feature):
                        row = measurements[feature]
                        self.assertAlmostEqual(row["nominal_expected_mm"], expected)
                        self.assertAlmostEqual(
                            row["measured_material_length_mm"], expected
                        )
                        self.assertTrue(row["passed"], row)
                beam = measurements["frame_foot_thickness"]
                self.assertEqual(beam["coordinate_frame"], "part local")
                self.assertEqual(
                    beam["sample_line_mm"], [(8, 20, 24.49), (8, 20, 29.51)]
                )
                from gondola.validation.manufacturing import material_length_on_line

                # Each3mm shoe roof is fused to the full-height central
                # pedestal. Read the complete literal roof stock interval.
                self.assertAlmostEqual(
                    material_length_on_line(
                        saved.PropulsionFixedFrame.Shape, (14, 0, 9.49), (14, 0, 12.5)
                    ),
                    3.0,
                )
                for centre_y in (-34.5, 34.5):
                    self.assertAlmostEqual(
                        material_length_on_line(
                            saved.PropulsionFixedFrame.Shape,
                            (-9.01, centre_y, 35),
                            (9.01, centre_y, 35),
                        ),
                        18,
                    )
                for feature, _, start, end, _ in propulsion.manufacturing_wall_probes(
                    drive=selected
                ):
                    with self.subTest(feature=feature):
                        row = measurements[feature]
                        self.assertEqual(row["sample_line_mm"], [start, end])
                        self.assertTrue(row["passed"], row)
                for feature in (
                    "fc_support_deck_thickness",
                    "accessory_plate_thickness",
                ):
                    row = measurements[feature]
                    self.assertAlmostEqual(row["measured_material_length_mm"], 2.0)
                    self.assertLess(
                        row["sample_line_mm"][0][2], equipment_mounts.DECK_BOTTOM_Z
                    )
                    self.assertTrue(row["passed"], row)
                assessment = result["equipment_mount_assessment"]
                self.assertEqual(
                    assessment["fc_support_deck_size_mm"], [66.0, 66.0, 2.0]
                )
                self.assertEqual(assessment["accessory_deck_size_mm"], (66.0, 66.0))
                self.assertTrue(result["passed"], result)
                # Exercise the actual release evidence generator against saved
                # geometry. A synthetic report sized from the contract cannot
                # detect a newly added probe whose required count was missed.
                saved_module = {
                    key: [saved.getObject(name) for name in names]
                    for key, names in module_names.items()
                }
                saved_module["group"] = saved.MainPropulsionModule
                physical, missing = module_service_shapes(saved, saved_module)
                self.assertFalse(missing)
                evidence = {"functional_wall_probes": [], "geometry": []}
                _record_print_checks(evidence, saved_module, physical)
                self.assertEqual(
                    len(evidence["functional_wall_probes"]),
                    PROPULSION_EVIDENCE_COUNTS["functional_wall_probes"],
                )
                self.assertIn(
                    "integrated_saddle_roof",
                    {row["feature"] for row in evidence["functional_wall_probes"]},
                )
                self.assertTrue(
                    all(row["passed"] for row in evidence["functional_wall_probes"])
                )
                # Removing real material must fail the same release probe;
                # changing the nominal bore did not relax the wall threshold.
                frame = saved.PropulsionFixedFrame
                original = frame.Shape.copy()
                try:
                    frame.Shape = original.cut(
                        Part.makeBox(1, 1, 0.1, App.Vector(5.75, 40.3, 49.5))
                    )
                    saved.recompute()
                    physical, missing = module_service_shapes(saved, saved_module)
                    self.assertFalse(missing)
                    evidence = {"functional_wall_probes": [], "geometry": []}
                    _record_print_checks(evidence, saved_module, physical)
                    wall = next(
                        row
                        for row in evidence["functional_wall_probes"]
                        if row["feature"] == "bearing_cap_nut_floor"
                    )
                    self.assertFalse(wall["passed"], wall)
                    self.assertAlmostEqual(wall["expected_wall_mm"], 2.5)
                    self.assertAlmostEqual(wall["measured_wall_mm"], 2.4)
                finally:
                    frame.Shape = original
                    saved.recompute()
            finally:
                App.closeDocument(saved.Name)


if __name__ == "__main__":
    unittest.main()
