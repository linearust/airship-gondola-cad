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
        from gondola.validation.propulsion import continuous_path

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
    def stack(self):
        axis = App.Vector(0, 1, 0)

        def annulus(outer, inner, length, y):
            origin = App.Vector(0, y, 0)
            return Part.makeCylinder(outer, length, origin, axis).cut(
                Part.makeCylinder(inner, length, origin, axis)
            )

        bearing = annulus(3, 1.5, 2.5, 0)
        shaft = Part.makeCylinder(1.5, 6, App.Vector(0, -1, 0), axis)
        seat = annulus(4.5, 2, 1.5, -1.5).fuse(annulus(4.5, 3.2, 2.5, 0))
        cap = annulus(4.5, 2, 1.5, 2.5)
        return bearing, shaft, seat, cap

    def test_nominal_stock_bearing_is_captured_with_clear_full_length_shaft(self):
        from gondola.validation.propulsion import bearing_stack_check

        result = bearing_stack_check(*self.stack())
        self.assertTrue(result["passed"], result)

    def test_missing_cap_is_not_axial_retention(self):
        from gondola.validation.propulsion import bearing_stack_check

        bearing, shaft, seat, _ = self.stack()
        result = bearing_stack_check(bearing, shaft, seat, Part.Shape())
        self.assertFalse(result["passed"])
        self.assertFalse(result["axial_capture"][1]["passed"])

    def test_offset_bearing_fails_even_when_the_stock_dimensions_match(self):
        from gondola.cad import translated_shape
        from gondola.validation.propulsion import bearing_stack_check

        bearing, shaft, seat, cap = self.stack()
        result = bearing_stack_check(translated_shape(bearing, x=0.2), shaft, seat, cap)
        self.assertFalse(result["passed"])
        self.assertAlmostEqual(result["shaft_axis_error_mm"], 0.2)

    def test_short_shaft_cannot_claim_full_inner_ring_engagement(self):
        from gondola.validation.propulsion import bearing_stack_check

        bearing, _, seat, cap = self.stack()
        short_shaft = Part.makeCylinder(
            1.5, 1.5, App.Vector(0, 0, 0), App.Vector(0, 1, 0)
        )
        result = bearing_stack_check(bearing, short_shaft, seat, cap)
        self.assertFalse(result["passed"])
        self.assertAlmostEqual(result["shaft_through_bearing_length_mm"], 1.5)


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class NativeGearedDriveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.parts import propulsion

        cls.doc = App.newDocument("GearedDriveRegression")
        cls.module = propulsion.build_propulsion_module(cls.doc)

    @classmethod
    def tearDownClass(cls):
        App.closeDocument(cls.doc.Name)

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
                App.Vector(0.2, 0, 0),
                "screw_tip_to_flat_contact_mm2",
            ),
            (
                "InputShaftClampNut",
                App.Vector(-0.2, 0, 0),
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
        from gondola.validation.propulsion import driver_lateral_service_check

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
        from gondola.validation.propulsion import driver_lateral_service_check

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
        from gondola.cad import world_shape
        from gondola.validation.propulsion import bearing_stack_check

        for prefix in ("Port", "Starboard"):
            for suffix in ("Negative", "Positive"):
                result = bearing_stack_check(
                    world_shape(self.doc.getObject(prefix + "OutputBearing" + suffix)),
                    world_shape(self.doc.getObject(prefix + "OutputShaft" + suffix)),
                    world_shape(self.module["frame"]),
                    world_shape(
                        self.doc.getObject(prefix + "OutputBearingCap" + suffix)
                    ),
                )
                self.assertTrue(result["passed"], (prefix, suffix, result))

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
            sum(str(obj.HardwareSKU).startswith("AL6061_CUT3_") for obj in hardware), 6
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
            self.assertEqual(shaft.HardwareSKU, "AL6061_CUT3_L16_FLAT16_A0")
            self.assertAlmostEqual(shaft.Shape.BoundBox.YLength, 16)
            self.assertAlmostEqual(shaft.Shape.BoundBox.XLength, 2.5)
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
                            for part in ("Shaft", "Bearing", "BearingCap")
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
                "HornGearRetainer",
                "HornGearClampBolt",
                "HornGearClampNut",
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
                                "HornGearRetainer",
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
                    self.assertEqual(
                        set(result["released_fasteners"]),
                        {prefix + "HornGearClamp" + kind for kind in ("Bolt", "Nut")},
                    )
                    self.assertEqual(
                        result["part_paths"][0]["part"], prefix + "HornGearRetainer"
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
                            for part in ("Shaft", "Bearing", "BearingCap")
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

    def test_servo_case_service_rejects_a_midpath_cradle_obstruction(self):
        from gondola.cad import translated_shape, world_shape
        from gondola.validation.geometry import intersection_volume
        from gondola.validation.propulsion import servo_case_service_check

        doc, module = self.configurations["48_16"]
        bridge = doc.ServoDriveBridge
        original = bridge.Shape.copy()
        try:
            # A lip ahead of the case leaves both endpoints clear but blocks
            # its first withdrawal segment. The stem joins the bridge cradle.
            drive = DRIVE_CONFIGURATIONS["48_16"]
            origin = App.Vector(drive.input_x_mm - 4.2, 25, drive.input_z_mm - 10)
            stem = Part.makeBox(0.6, 7.2, 2, origin)
            lip = Part.makeBox(1.1, 0.2, 2, origin + App.Vector(0, 7, 0))
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
            "PortHornGearClampNut",
            "PortServoHorn",
            "PortHornGearAdapter",
            "PortOutputShaftPositive",
            "PortOutputBearingCapPositive",
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

        selected = SELECTED_DRIVE
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "selected_drive.FCStd"
            doc = App.newDocument("SavedSelectedDriveWalls")
            try:
                propulsion.build_propulsion_module(doc, drive=selected)
                # A nonzero module placement also exercises the measurement's
                # conversion from global coordinates back to the module frame.
                doc.MainPropulsionModule.Placement.Base = App.Vector(36, 0.45, 0)
                rail.build_rail(doc)
                host = doc.addObject("App::Part", "BatteryEquipmentModule")
                equipment_mounts.build_mount(doc, host, "battery")
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
            finally:
                App.closeDocument(saved.Name)


if __name__ == "__main__":
    unittest.main()
