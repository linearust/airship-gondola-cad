"""Native CAD regressions; run with the installed FreeCAD Python runtime."""

import json
import math
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

    def test_horn_nut_exit_checks_the_space_between_clear_endpoints(self):
        from gondola.cad import translated_shape
        from gondola.parts import purchased_hardware as hardware
        from gondola.validation.propulsion import _horn_clamp_service_check

        bolt = hardware.servo_screw_shape().copy()
        nut = translated_shape(hardware.servo_nut_shape(), z=5.2)
        baseline = _horn_clamp_service_check(bolt, nut, {}, (1, 0, 0))
        self.assertTrue(baseline["passed"], baseline)
        self.assertAlmostEqual(baseline["measured_head_envelope_diameter_mm"], 3.5)
        self.assertAlmostEqual(baseline["measured_head_envelope_height_mm"], 1.6)
        self.assertEqual(len(baseline["nut_axial_removal"]["segments"]), 2)
        obstacle = Part.makeBox(0.1, 0.2, 0.2, App.Vector(12.5, -0.1, 8.3))
        for offset in ((0, 0, 0), (0, 0, 3), (25, 0, 3)):
            self.assertLess(
                translated_shape(nut, *offset).common(obstacle).Volume, 1e-7
            )
        result = _horn_clamp_service_check(
            bolt, nut, {"intermediate_obstacle": obstacle}, (1, 0, 0)
        )
        self.assertFalse(result["passed"], result)
        self.assertGreater(
            result["nut_axial_removal"]["segments"][1]["intersection_mm3"][
                "intermediate_obstacle"
            ],
            0.001,
        )

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
        self.addCleanup(App.closeDocument, self.doc.Name)

    def check(self):
        from gondola.validation.propulsion import output_bearing_stack_check

        return output_bearing_stack_check(self.doc, "Port", "Positive")

    def test_nominal_spacerless_stack_keeps_two_hooks_and_fixed_guidance(self):
        result = self.check()
        self.assertTrue(result["passed"], result)
        self.assertAlmostEqual(result["maximum_bearing_inward_travel_mm"], 0.2)
        self.assertAlmostEqual(result["maximum_bearing_outward_travel_mm"], 0)
        capture = result["capture_geometry"]
        self.assertAlmostEqual(capture["complete_guide_length_mm"], 2.1)
        self.assertAlmostEqual(
            capture["complete_guide_overlap_at_inward_limit_mm"], 1.9
        )
        self.assertEqual(len(result["hook_contact_patch_areas_mm2"]), 2)
        self.assertGreater(min(result["hook_contact_patch_areas_mm2"]), 0.5)
        self.assertIsNone(self.doc.getObject("PortOutputBearingSpacerPositive"))

    def test_missing_one_integral_hook_cannot_claim_inward_capture(self):
        from gondola.cad import translated_shape
        from gondola.parts import bearing_retention, propulsion

        frame = self.doc.PropulsionFixedFrame
        hook = translated_shape(
            bearing_retention.hook_shape(1),
            y=propulsion.PIVOT_HALF_SPAN + propulsion.BEARING_START_Y,
            z=propulsion.PIVOT_Z,
        )
        frame.Shape = frame.Shape.cut(hook)
        self.doc.recompute()
        self.assertFalse(self.check()["passed"])

    def test_removed_integral_outer_shoulder_cannot_claim_capture(self):
        from gondola.parts.propulsion import (
            BEARING_SHOULDER_Y,
            PIVOT_HALF_SPAN,
            PIVOT_Z,
        )

        frame = self.doc.PropulsionFixedFrame
        frame.Shape = frame.Shape.cut(
            Part.makeCylinder(
                3.01,
                2,
                App.Vector(0, PIVOT_HALF_SPAN + BEARING_SHOULDER_Y - 0.01, PIVOT_Z),
                App.Vector(0, 1, 0),
            )
        )
        self.doc.recompute()
        self.assertFalse(self.check()["passed"])

    def test_missing_guide_or_outer_shoulder_sector_cannot_claim_complete_support(self):
        from gondola.parts.propulsion import PIVOT_HALF_SPAN, PIVOT_Z

        frame = self.doc.PropulsionFixedFrame
        original = frame.Shape.copy()
        for local_y, depth in ((28.91, 1.5), (31.01, 0.5)):
            with self.subTest(local_y=local_y):
                frame.Shape = original.cut(
                    Part.makeBox(
                        6, depth, 6, App.Vector(0, PIVOT_HALF_SPAN + local_y, PIVOT_Z)
                    )
                )
                self.doc.recompute()
                self.assertFalse(self.check()["passed"])
        frame.Shape = original

    def test_offset_bearing_cannot_reuse_the_nominal_guide(self):
        self.doc.PortOutputBearingPositive.Placement.Base.x += 0.2
        self.doc.recompute()
        self.assertFalse(self.check()["passed"])

    def test_carrier_protrusion_toward_bearing_shield_is_rejected(self):
        carrier = self.doc.PortMotorCarrier
        carrier.Shape = carrier.Shape.fuse(
            Part.makeCylinder(2.7, 2.6, App.Vector(0, 26, 0), App.Vector(0, 1, 0))
        )
        self.doc.recompute()
        result = self.check()
        self.assertFalse(result["passed"], result)

    def test_extra_carrier_travel_cannot_reuse_the_nominal_face_clearance(self):
        from gondola.validation.propulsion import output_bearing_stack_check

        result = output_bearing_stack_check(
            self.doc,
            "Port",
            "Positive",
            {"passed": True, "negative_mm": 1.5, "positive_mm": 0.5},
        )
        self.assertFalse(result["passed"], result)
        self.assertLess(result["minimum_carrier_to_bearing_face_gap_mm"], 1.8)
        # The fixed hooks still capture the bearing independently of the carrier.
        self.assertTrue(result["capture_geometry"]["passed"], result)

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

    def test_plain_bearing_post_roots_keep_the_complete_load_section(self):
        from gondola.validation.propulsion import bearing_post_roots_check

        rows = bearing_post_roots_check(self.doc)
        self.assertEqual(len(rows), 4)
        for row in rows:
            self.assertTrue(row["passed"], row)

    def test_plain_posts_clear_continuous_output_rotation_and_axial_travel(self):
        from gondola.cad import belongs_to_group, world_shape
        from gondola.parts import propulsion
        from gondola.validation.motion_clearance import carrier_axial_travel

        # Added web material occupies local Y26.5..30.5 and Y-30.5..-26.5,
        # ending 9.2 mm below the output axis. Rotation leaves Y unchanged.
        # Each real moving solid must either remain within the opposed inner
        # planes at both axial limits, or fit radially inside the web top.
        minimum_web_radius = propulsion.PIVOT_Z - 39.0
        physical = [
            *self.module["printed"],
            *self.module["hardware"],
            *self.module["references"],
        ]
        for prefix in ("Port", "Starboard"):
            pod = self.doc.getObject(prefix + "Pod")
            travel = carrier_axial_travel(self.doc, prefix)
            self.assertTrue(travel["passed"], travel)
            for obj in physical:
                if not belongs_to_group(obj, pod):
                    continue
                shape = world_shape(obj)
                shape.Placement = (
                    pod.getGlobalPlacement().inverse().multiply(shape.Placement)
                )
                bounds = shape.optimalBoundingBox(False, False)
                inside_axial_planes = (
                    bounds.YMin - travel["negative_mm"] >= -26.5 - 1e-7
                    and bounds.YMax + travel["positive_mm"] <= 26.5 + 1e-7
                )
                radial_bound = math.hypot(
                    max(abs(bounds.XMin), abs(bounds.XMax)),
                    max(abs(bounds.ZMin), abs(bounds.ZMax)),
                )
                with self.subTest(object=obj.Name):
                    self.assertTrue(
                        inside_axial_planes or radial_bound < minimum_web_radius,
                        (obj.Name, bounds, radial_bound, travel),
                    )

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
                self.assertGreaterEqual(allowance["rear_body_to_plate_gap_mm"], 5)
                for actual, expected in zip(allowance["rear_body_section_mm"], (7, 20)):
                    self.assertAlmostEqual(actual, expected)
                self.assertAlmostEqual(
                    allowance["inward_planning_y_range_mm"][1],
                    servo_bridge.case_front_y() - 16.7,
                )
                self.assertAlmostEqual(allowance["inward_planning_volume_mm"][1], 13.9)
                self.assertEqual(len(allowance["continuous_input_drive_clearance"]), 20)
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
                1, 1, 2, App.Vector(-0.5, servo_bridge.case_front_y() - 23.6, -2)
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
                0.5,
                1,
                0.5,
                App.Vector(9, servo_bridge.case_front_y() - 22.2, 19),
            )
            axis = App.Vector(-SELECTED_DRIVE.input_x_mm, 0, SELECTED_DRIVE.input_z_mm)
            shape.rotate(axis, App.Vector(0, 1, 0), -30)
            shape.Placement = (
                drive.getGlobalPlacement()
                .inverse()
                .multiply(self.doc.MainPropulsionModule.getGlobalPlacement())
                .multiply(shape.Placement)
            )
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

        bridge = self.doc.ServoDriveBridge
        original = bridge.Shape.copy()
        before = servo_mount_check(self.doc, "Port")[
            "rear_body_and_inward_lead_allowance"
        ]
        self.assertTrue(before["passed"], before)
        patch = Part.makeBox(
            7,
            1,
            0.5,
            App.Vector(
                -3.5,
                servo_bridge.case_front_y() - 16.6 + 0.5,
                before["plate_top_below_rear_body_z_mm"],
            ),
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

    def test_rail_key_clears_complete_fixed_module_on_both_sides(self):
        from gondola.validation.propulsion import rail_key_access_check

        rows = rail_key_access_check(self.doc, self.module)
        self.assertEqual(
            {row["approach_side_y"] for row in rows},
            {1, -1},
        )
        for row in rows:
            self.assertTrue(row["passed"], row)
            for name in ("PropulsionFixedFrame", "StarboardDriverGear", "PortServo"):
                self.assertIn(name, row["checked_objects"])

    def test_new_frame_obstacle_cannot_hide_from_whole_module_key_check(self):
        from gondola.validation.propulsion import rail_key_access_check

        frame = self.doc.PropulsionFixedFrame
        original = frame.Shape.copy()
        try:
            frame.Shape = original.fuse(Part.makeBox(4, 2, 3, App.Vector(-2, 19, 5)))
            self.doc.recompute()
            rows = rail_key_access_check(self.doc, self.module)
            self.assertFalse(rows[0]["passed"], rows)
            self.assertIn(
                "PropulsionFixedFrame", {hit["part"] for hit in rows[0]["collisions"]}
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
            gear.Placement.Base.y += 1.6
            self.doc.recompute()
            result = gear_engagement_check(self.doc, "Port")
            self.assertFalse(result["passed"], result)
            self.assertAlmostEqual(result["tooth_face_overlap_mm"], 2.4)
            self.assertAlmostEqual(
                result["minimum_tooth_face_overlap_under_travel_mm"], 1.9
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
        from gondola.parts import propulsion
        from gondola.validation.propulsion import direct_adapter_fit_check

        for prefix in ("Port", "Starboard"):
            result = direct_adapter_fit_check(self.doc, prefix)
            self.assertTrue(result["passed"], result)
        gear = self.doc.PortDriverGear
        original = gear.Shape.copy()
        try:
            axis = App.Vector(0, 1, 0)
            origin = App.Vector(0, propulsion.GEAR_HUB_START_Y, 0)
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

    def test_input_stub_stop_and_radial_jack_contacts_are_required(self):
        from gondola.validation.propulsion import input_shaft_retention_check

        for suffix, displacement, contact_key in (
            ("InputShaft", App.Vector(0, 0.2, 0), "shaft_stop_contact_mm2"),
            (
                "InputShaftClampBolt",
                App.Vector(0, 0, -0.2),
                "screw_tip_to_flat_contact_mm2",
            ),
            (
                "InputShaftClampNut",
                App.Vector(0, 0, 0.2),
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
        from gondola.validation.propulsion import servo_lateral_service_check

        for prefix, sign in (("Port", 1), ("Starboard", -1)):
            with self.subTest(pod=prefix):
                servo = world_shape(self.doc.getObject(prefix + "Servo"))
                start, end = (0, sign * 12.5, 0), (sign * 40, sign * 12.5, 0)
                obstacle = Part.makeBox(
                    0.2,
                    0.2,
                    0.2,
                    App.Vector(
                        sign * (SELECTED_DRIVE.input_x_mm + 20) - 0.1,
                        sign * (servo_bridge.case_front_y() - 4.7 + 12.5 + 0.5) - 0.1,
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
                    intersection_volume(
                        translated_shape(servo, x=sign * 20, y=sign * 12.5), obstacle
                    ),
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
            for suffix in ("Negative", "Positive"):
                result = output_bearing_stack_check(self.doc, prefix, suffix)
                self.assertTrue(result["passed"], (prefix, suffix, result))

    def test_output_carrier_service_rejects_an_obstacle_between_clear_endpoints(self):
        from gondola.cad import translated_shape, world_shape
        from gondola.parts.propulsion import PIVOT_HALF_SPAN, PIVOT_Z
        from gondola.validation.propulsion import output_carrier_service_check

        obstacle = self.doc.addObject("Part::Feature", "CarrierServiceObstacle")
        self.module["group"].addObject(obstacle)
        obstacle.Shape = Part.makeBox(
            0.4, 0.4, 0.4, App.Vector(19.8, PIVOT_HALF_SPAN + 23.3, PIVOT_Z - 0.2)
        )
        modified = {**self.module, "references": self.module["references"] + [obstacle]}
        try:
            self.doc.recompute()
            carrier = world_shape(self.doc.PortMotorCarrier)
            self.assertLess(carrier.common(obstacle.Shape).Volume, 1e-7)
            self.assertLess(
                translated_shape(carrier, x=40).common(obstacle.Shape).Volume, 1e-7
            )
            self.assertGreater(
                translated_shape(carrier, x=8).common(obstacle.Shape).Volume, 1e-4
            )
            result = output_carrier_service_check(self.doc, modified, "Port")
            self.assertFalse(result["passed"], result)
            self.assertEqual(
                set(result["moving_parts"]),
                {
                    "PortMotorCarrier",
                    "PortMotor",
                    "PortPropellerDisk",
                    "PortShaft",
                    "PortOutputClampPositiveBolt",
                    "PortOutputClampPositiveNut",
                    "PortOutputClampNegativeBolt",
                    "PortOutputClampNegativeNut",
                },
            )
            carrier_row = next(
                row
                for row in result["carrier_removal"]
                if row["part"] == "PortMotorCarrier"
            )
            self.assertFalse(carrier_row["passed"])
        finally:
            self.doc.removeObject(obstacle.Name)
            self.doc.recompute()

    def test_output_stubs_cannot_be_replaced_by_a_shaft_through_the_motor(self):
        from gondola.cad import world_shape
        from gondola.parts import propulsion
        from gondola.validation.propulsion import output_stub_check

        motor = world_shape(self.doc.PortMotor)
        pivot_y = self.doc.PortPod.getGlobalPlacement().Base.y
        for suffix in ("Negative", "Positive"):
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

        return tuple(
            world_shape(self.doc.getObject(name))
            for name in (
                "PortMotorCarrier",
                "PortOutputClampPositiveBolt",
                "PortOutputClampPositiveNut",
            )
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
                    world_shape(self.doc.ServoDriveBridge),
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
        result = clamp_fastener_check(clamp, translated_shape(bolt, z=-2), nut)
        self.assertFalse(result["passed"], result)
        self.assertGreater(result["missing_bolt_thread_core_mm3"], 0)

    def test_bought_gears_bearings_and_shafts_are_never_print_parts(self):
        hardware = self.module["hardware"]
        self.assertEqual(
            sum(obj.HardwareSKU == "BEARING_3X6X2_5" for obj in hardware), 4
        )
        self.assertEqual(
            sum(
                str(obj.HardwareSKU).startswith("ALI_KAILASH_M05_") for obj in hardware
            ),
            4,
        )
        self.assertEqual(
            sum(str(obj.HardwareSKU).startswith("SS304_CUT3_") for obj in hardware), 6
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
        doc, module = self.configurations["48_16"]
        self.assertEqual(set(self.configurations), {"48_16"})
        self.assertEqual(doc.ServoDriveBridge.PrintSKU, "ServoDriveBridge48T")
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
            self.assertEqual(shaft.HardwareSKU, "SS304_CUT3_L18_FLAT18_A0")
            self.assertAlmostEqual(shaft.Shape.BoundBox.YLength, 18)
            self.assertAlmostEqual(shaft.Shape.BoundBox.ZLength, 2.5)
            self.assertFalse(bool(getattr(shaft, "PrintPart", False)))

    def test_selected_servo_module_has_seated_joint_and_checked_service(
        self,
    ):
        from gondola.validation.propulsion import (
            bridge_joint_check,
            servo_module_service_check,
        )

        for key, (doc, module) in self.configurations.items():
            for check in (bridge_joint_check, servo_module_service_check):
                with self.subTest(configuration=key, check=check.__name__):
                    result = check(doc, module)
                    self.assertTrue(result["passed"], result)
                    if check is servo_module_service_check:
                        self.assertEqual(
                            set(result["moving_parts"]), self.servo_package_names()
                        )
                        self.assertEqual(
                            result["removed_output_gears"],
                            ["PortOutputGear", "StarboardOutputGear"],
                        )
                        self.assertEqual(
                            set(result["released_fasteners"]),
                            {
                                "ServoBridge" + side + kind
                                for side in ("Port", "Starboard")
                                for kind in ("Bolt", "Nut")
                            },
                        )
                        retained = {"PropulsionFixedFrame"} | {
                            prefix + "Output" + part + side
                            for prefix in ("Port", "Starboard")
                            for part in ("Shaft", "Bearing")
                            for side in ("Negative", "Positive")
                        }
                        self.assertTrue(retained.issubset(result["retained_parts"]))
                        self.assertEqual(
                            {row["part"] for row in result["part_paths"]},
                            self.servo_package_names(),
                        )
                        for category in (
                            "output_gear_removal",
                            "mount_fastener_release",
                            "part_paths",
                        ):
                            self.assertTrue(
                                all(row["passed"] for row in result[category])
                            )

    @staticmethod
    def servo_package_names():
        return {"ServoDriveBridge"} | {
            prefix + suffix
            for prefix in ("Port", "Starboard")
            for suffix in (
                "Servo",
                "ServoHorn",
                "DriverGear",
                "InputShaft",
                "InputShaftClampBolt",
                "InputShaftClampNut",
                "HornGearAdapter",
                "HornGearClampNearBolt",
                "HornGearClampFarBolt",
                "HornGearClampNearNut",
                "HornGearClampFarNut",
                "ServoEarLowerBolt",
                "ServoEarLowerNut",
                "ServoEarUpperBolt",
                "ServoEarUpperNut",
            )
        }

    def test_servo_module_service_rejects_a_midpath_obstacle_with_clear_endpoints(self):
        from gondola.cad import translated_shape, world_shape
        from gondola.parts import servo_bridge
        from gondola.validation.geometry import intersection_volume
        from gondola.validation.propulsion import servo_module_service_check

        doc, module = self.configurations["48_16"]
        spec = DRIVE_CONFIGURATIONS["48_16"]
        witness = doc.addObject("Part::Feature", "ServiceMidpathWitness")
        module["group"].addObject(witness)
        try:
            witness.Shape = Part.makeBox(
                0.2,
                0.2,
                0.2,
                App.Vector(
                    spec.input_x_mm + 40 - 0.1,
                    servo_bridge.case_front_y() - 10,
                    spec.input_z_mm - 5 + 0.5,
                ),
            )
            doc.recompute()
            obstacle = world_shape(witness)
            for name in self.servo_package_names():
                shape = world_shape(doc.getObject(name))
                for endpoint in (shape, translated_shape(shape, x=80, z=0.5)):
                    self.assertLess(intersection_volume(endpoint, obstacle), 1e-5, name)
            middle = translated_shape(world_shape(doc.PortServo), x=40, z=0.5)
            self.assertGreater(intersection_volume(middle, obstacle), 0)
            with_obstacle = {**module, "references": [*module["references"], witness]}
            result = servo_module_service_check(doc, with_obstacle)
            self.assertFalse(result["passed"], result)
            servo_path = next(
                row for row in result["part_paths"] if row["part"] == "PortServo"
            )
            self.assertFalse(servo_path["passed"], servo_path)
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

    def test_bridge_joint_rejects_an_unseated_bridge_with_unchanged_metadata(self):
        from gondola.validation.propulsion import bridge_joint_check

        for key, (doc, module) in self.configurations.items():
            bridge = doc.ServoDriveBridge
            original = App.Placement(bridge.Placement)
            try:
                bridge.Placement.Base = original.Base + App.Vector(0, 0, 0.2)
                doc.recompute()
                self.assertEqual(bridge.PrintSKU, DRIVE_CONFIGURATIONS[key].bridge_sku)
                result = bridge_joint_check(doc, module)
                self.assertFalse(result["passed"], result)
            finally:
                bridge.Placement = original
                doc.recompute()

    def test_native_motion_teeth_and_mounts_follow_selected_configuration(self):
        from gondola.validation.propulsion import (
            drive_motion_check,
            fixed_servo_datum_check,
            rail_key_access_check,
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
            for row in rail_key_access_check(doc, module):
                self.assertTrue(row["passed"], (key, row))

    def test_servo_and_adapter_have_checked_removal_paths(self):
        from gondola.validation.propulsion import (
            input_drive_service_check,
            servo_case_service_check,
        )

        for key, (doc, module) in self.configurations.items():
            for prefix in ("Port", "Starboard"):
                with self.subTest(configuration=key, pod=prefix):
                    # Resolving an assembly compound can expose a dynamic Shape
                    # on its App::Part. It is not another missing bought part.
                    assembly_shape = Part.getShape(doc.getObject(prefix + "Assembly"))
                    self.assertGreater(assembly_shape.Volume, 0)
                    result = input_drive_service_check(doc, module, prefix)
                    self.assertTrue(result["passed"], result)
                    self.assertEqual(
                        set(result["moving_parts"]),
                        {
                            prefix + suffix
                            for suffix in (
                                "HornGearAdapter",
                                "DriverGear",
                                "InputShaft",
                                "InputShaftClampBolt",
                                "InputShaftClampNut",
                            )
                        },
                    )
                    self.assertEqual(
                        result["removed_output_gear"], prefix + "OutputGear"
                    )
                    self.assertTrue(result["output_gear_removal"]["passed"])
                    self.assertTrue(result["adapter_clamp_release"]["passed"])
                    clamp_release = result["adapter_clamp_release"]
                    self.assertEqual(clamp_release["release_order"], ["Far", "Near"])
                    far, near = clamp_release["fasteners"]
                    self.assertIn(
                        prefix + "HornGearClampNearBolt", far["retained_parts"]
                    )
                    self.assertIn(
                        prefix + "HornGearClampNearNut", far["retained_parts"]
                    )
                    for kind in ("Bolt", "Nut"):
                        name = prefix + "HornGearClampFar" + kind
                        self.assertIn(name, near["removed_prior_parts"])
                        self.assertNotIn(name, near["retained_parts"])
                    for joint in (far, near):
                        self.assertEqual(len(joint["nut_axial_removal"]["segments"]), 2)
                        self.assertAlmostEqual(
                            joint["measured_head_envelope_diameter_mm"], 3.5
                        )
                        self.assertAlmostEqual(
                            joint["measured_head_envelope_height_mm"], 1.6
                        )
                    self.assertEqual(
                        set(result["released_fasteners"]),
                        {
                            prefix + "HornGearClamp" + position + kind
                            for position in ("Near", "Far")
                            for kind in ("Bolt", "Nut")
                        },
                    )
                    case_service = servo_case_service_check(doc, module, prefix)
                    self.assertTrue(case_service["passed"], case_service)
                    self.assertEqual(
                        set(case_service["moving_parts"]),
                        {prefix + "Servo", prefix + "ServoHorn"},
                    )
                    self.assertEqual(
                        set(case_service["released_fasteners"]),
                        {
                            prefix + "ServoEar" + side + kind
                            for side in ("Lower", "Upper")
                            for kind in ("Bolt", "Nut")
                        },
                    )
                    self.assertEqual(
                        case_service["required_prior_check"], "input_drive_service"
                    )
                    retained = (
                        {
                            prefix + "Output" + part + side
                            for part in ("Shaft", "Bearing")
                            for side in ("Negative", "Positive")
                        }
                        | {"PropulsionFixedFrame", "ServoDriveBridge"}
                        | {
                            "ServoBridge" + side + kind
                            for side in ("Port", "Starboard")
                            for kind in ("Bolt", "Nut")
                        }
                    )
                    for service in (result, case_service):
                        self.assertTrue(retained.issubset(service["retained_parts"]))
                        for row in service["part_paths"]:
                            self.assertTrue(row["passed"], row)
                            self.assertTrue(retained.issubset(row["obstacles"]))

    def test_horn_fastener_report_retains_the_other_joint_until_ordered_release(self):
        from gondola.cad import world_shape
        from gondola.validation.propulsion import _record_fastener_checks

        doc, module = self.configurations["48_16"]
        physical = {
            obj.Name: world_shape(obj)
            for obj in module["printed"] + module["hardware"] + module["references"]
        }
        report = {
            "fastener_stacks": [],
            "fastener_service": [],
            "gear_service": [
                {"gear": prefix + "OutputGear", "passed": True}
                for prefix in ("Port", "Starboard")
            ],
            "input_drive_service": [
                {"pod": prefix, "passed": True} for prefix in ("Port", "Starboard")
            ],
        }
        _record_fastener_checks(report, module, physical)
        for prefix in ("Port", "Starboard"):
            rows = {row["bolt"]: row for row in report["fastener_service"]}
            far = rows[prefix + "HornGearClampFarBolt"]
            near = rows[prefix + "HornGearClampNearBolt"]
            self.assertTrue(far["passed"], far)
            self.assertTrue(near["passed"], near)
            self.assertIn(
                prefix + "HornGearClampNearBolt", far["retained_service_parts"]
            )
            self.assertIn(prefix + "HornGearClampFarBolt", near["removed_local_parts"])
            self.assertIn(
                {
                    "check": "fastener_service",
                    "object": prefix + "HornGearClampFarBolt",
                    "passed": True,
                },
                near["service_dependencies"],
            )

    def test_servo_case_service_rejects_a_midpath_cradle_obstruction(self):
        from gondola.cad import translated_shape, world_shape
        from gondola.parts import servo_bridge
        from gondola.validation.geometry import intersection_volume
        from gondola.validation.propulsion import servo_case_service_check

        doc, module = self.configurations["48_16"]
        bridge = doc.ServoDriveBridge
        original = bridge.Shape.copy()
        try:
            # A lip ahead of the case leaves both endpoints clear but blocks
            # its first withdrawal segment. The stem joins the bridge cradle.
            drive = DRIVE_CONFIGURATIONS["48_16"]
            stem_left = -servo_bridge.CASE_WINDOW_WIDTH / 2 - 0.2
            stem_width = -3.6 - stem_left
            origin = App.Vector(
                drive.input_x_mm + stem_left,
                servo_bridge.case_front_y() - 5.7,
                drive.input_z_mm - 10,
            )
            stem = Part.makeBox(stem_width, 7.2, 2, origin)
            lip = Part.makeBox(stem_width + 0.5, 0.2, 2, origin + App.Vector(0, 7, 0))
            bridge.Shape = original.fuse(stem).fuse(lip).removeSplitter()
            doc.recompute()
            self.assertEqual(len(bridge.Shape.Solids), 1)
            case = world_shape(doc.PortServo)
            obstacle = world_shape(bridge)
            for endpoint in (case, translated_shape(case, x=40, y=12.5)):
                self.assertLess(intersection_volume(endpoint, obstacle), 1e-5)
            self.assertGreater(
                intersection_volume(translated_shape(case, y=5), obstacle), 0
            )
            result = servo_case_service_check(doc, module, "Port")
            self.assertFalse(result["passed"], result)
            case_row = next(
                row for row in result["part_paths"] if row["part"] == "PortServo"
            )
            self.assertFalse(case_row["passed"], case_row)
        finally:
            bridge.Shape = original
            doc.recompute()

    def test_service_cannot_omit_retained_or_removed_physical_parts(self):
        from gondola.validation.propulsion import (
            input_drive_service_check,
            servo_case_service_check,
            servo_module_service_check,
        )

        doc, module = self.configurations["48_16"]
        for name in (
            "PortInputShaft",
            "PortInputShaftClampBolt",
            "PortInputShaftClampNut",
            "PortHornGearClampNearNut",
            "PortServoHorn",
            "PortHornGearAdapter",
            "PortOutputShaftPositive",
            "PortOutputBearingPositive",
            "PropulsionFixedFrame",
            "ServoDriveBridge",
            "ServoBridgePortNut",
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
            with self.subTest(part=name, check="servo_module_service_check"):
                result = servo_module_service_check(doc, incomplete)
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
        support = doc.ServoDriveBridge
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
        bridge = doc.ServoDriveBridge
        original = bridge.Shape.copy()
        try:
            shifted = original.copy()
            shifted.translate(App.Vector(2, 0, 0))
            bridge.Shape = shifted
            doc.recompute()
            self.assertEqual(bridge.PrintSKU, "ServoDriveBridge48T")
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

    def test_servo_case_tolerance_does_not_consume_the_open_cradle_clearance(self):
        from gondola.cad import box
        from gondola.parts import servo_bridge

        spec = SELECTED_DRIVE
        x, z = spec.input_x_mm, spec.input_z_mm
        y = servo_bridge.case_front_y() - 4.7 - servo_bridge.MOUNT_DEPTH
        # Published 7 x20 body dimensions are each allowed +0.2 mm. The body
        # must clear the cradle independently of its accurately placed ears.
        largest_case_section = box(7.2, 7, 20.2, (x - 3.6, y - 1, z - 15.1))
        bridge = servo_bridge.bridge_shape()
        for section in (
            largest_case_section,
            servo_bridge.opposite(largest_case_section),
        ):
            self.assertLess(bridge.common(section).Volume, 1e-7)
            self.assertGreaterEqual(bridge.distToShape(section)[0], 0.4 - 1e-7)

    def test_fixed_mount_checks_follow_the_whole_module_placement(self):
        from gondola.validation.propulsion import (
            bridge_joint_check,
            fixed_servo_datum_check,
            input_drive_service_check,
            servo_case_service_check,
            servo_module_service_check,
            servo_mount_check,
        )

        doc, module_parts = self.configurations["48_16"]
        module = doc.MainPropulsionModule
        original = App.Placement(module.Placement)
        try:
            module.Placement = App.Placement(
                App.Vector(36, 0.45, 2), App.Rotation(App.Vector(1, 2, 3), 13)
            )
            doc.recompute()
            for check in (bridge_joint_check, servo_module_service_check):
                result = check(doc, module_parts)
                self.assertTrue(result["passed"], result)
            for prefix in ("Port", "Starboard"):
                for check in (
                    fixed_servo_datum_check,
                    servo_mount_check,
                ):
                    with self.subTest(pod=prefix, check=check.__name__):
                        result = check(doc, prefix)
                        self.assertTrue(result["passed"], result)
                case_service = servo_case_service_check(doc, module_parts, prefix)
                self.assertTrue(case_service["passed"], case_service)
                service = input_drive_service_check(doc, module_parts, prefix)
                self.assertTrue(service["passed"], service)
        finally:
            module.Placement = original
            doc.recompute()

    def test_servo_bridge_collision_is_rejected_even_with_seated_bolts(self):
        from gondola.cad import world_shape
        from gondola.validation.propulsion import servo_mount_check

        doc, _ = self.configurations["48_16"]
        bridge = doc.ServoDriveBridge
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
        from gondola.parts import equipment_mounts, optical_mount, propulsion, rail
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
                equipment_mounts.build_mount(doc, electronics, "electronics")
                optical_mount.build_optical_mount(doc, host)
                doc.recompute()
                doc.saveAs(str(path))
            finally:
                App.closeDocument(doc.Name)

            saved = App.openDocument(str(path), hidden=True)
            try:
                saved.recompute()
                registry = SimpleNamespace(
                    PrintedParts=[saved.PropulsionFixedFrame, saved.ServoDriveBridge],
                    RailSegments=[saved.ContinuousRail],
                )
                result = review(saved, registry)
                measurements = {
                    row["feature"]: row for row in result["actual_feature_measurements"]
                }
                for feature, _, start, end, _ in propulsion.manufacturing_wall_probes(
                    drive=selected
                ):
                    with self.subTest(feature=feature):
                        row = measurements[feature]
                        self.assertEqual(row["sample_line_mm"], [start, end])
                        self.assertTrue(row["passed"], row)
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
                    "servo_common_cradle_central_web",
                    {row["feature"] for row in evidence["functional_wall_probes"]},
                )
                self.assertTrue(
                    all(row["passed"] for row in evidence["functional_wall_probes"])
                )
            finally:
                App.closeDocument(saved.Name)


if __name__ == "__main__":
    unittest.main()
