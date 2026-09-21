"""Native CAD regressions; run with the installed FreeCAD Python runtime."""

import unittest

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
        def gear(radius, hub_radius, x):
            axis = App.Vector(0, 1, 0)
            origin = App.Vector(x, 0, 0)
            return Part.makeCylinder(radius, 3, origin, axis).fuse(
                Part.makeCylinder(hub_radius, 8, origin, axis)
            )

        return gear(15.5, 6, 0), gear(5.5, 3.5, 20)

    def check(self, driver, output):
        from gondola.validation.propulsion import gear_mesh_check

        return gear_mesh_check(
            driver,
            output,
            module=0.5,
            driver_teeth=60,
            output_teeth=20,
            minimum_face_overlap=3,
        )

    def test_aligned_tooth_faces_pass_positioning_check(self):
        result = self.check(*self.gears())
        self.assertTrue(result["passed"], result)
        self.assertAlmostEqual(result["tooth_face_overlap_mm"], 3)

    def test_overlapping_hub_lengths_cannot_hide_disengaged_tooth_faces(self):
        from gondola.cad import translated_shape

        driver, output = self.gears()
        output = translated_shape(output, y=3.2)
        self.assertLess(output.BoundBox.YMin, driver.BoundBox.YMax)
        result = self.check(driver, output)
        self.assertFalse(result["passed"], result)
        self.assertLess(result["tooth_face_overlap_mm"], 0)

    def test_axis_distance_cannot_be_below_nominal_or_beyond_adjustment(self):
        from gondola.cad import translated_shape

        driver, output = self.gears()
        for shift in (-0.1, 0.51):
            with self.subTest(shift=shift):
                result = self.check(driver, translated_shape(output, x=shift))
                self.assertFalse(result["passed"], result)

    def test_nominal_axis_tolerance_cannot_hide_insufficient_contact_ratio(self):
        from gondola.cad import translated_shape

        driver, output = self.gears()
        result = self.check(driver, translated_shape(output, x=0.2))
        self.assertAlmostEqual(result["axis_distance_mm"], 20.2)
        self.assertLess(result["standard_involute_contact_ratio"], 1.3)
        self.assertFalse(result["passed"], result)


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

    def test_rail_key_clears_complete_module_on_both_sides_and_mesh_limits(self):
        from gondola.validation.propulsion import rail_key_access_check

        rows = rail_key_access_check(self.doc, self.module)
        self.assertEqual(
            {(row["approach_side_y"], row["mesh_clearance_mm"]) for row in rows},
            {(1, 0), (-1, 0), (1, 0.19), (-1, 0.19)},
        )
        for row in rows:
            self.assertTrue(row["passed"], row)
            for name in ("PortInputSupport", "StarboardDriverGear60T", "PortServo"):
                self.assertIn(name, row["checked_objects"])

    def test_closed_input_flange_blocks_key_even_when_fixed_frame_is_clear(self):
        from gondola.parts import propulsion
        from gondola.validation.propulsion import rail_key_access_check

        support = self.doc.PortInputSupport
        original = support.Shape.copy()
        try:
            obstruction = Part.makeBox(
                4, 2, 3, App.Vector(-10, 19, 5 - propulsion.INPUT_AXIS_Z)
            )
            support.Shape = support.Shape.fuse(obstruction).removeSplitter()
            self.doc.recompute()
            rows = rail_key_access_check(self.doc, self.module)
            for row in rows:
                if row["approach_side_y"] > 0:
                    self.assertFalse(row["passed"], row)
                    self.assertEqual(
                        {hit["part"] for hit in row["collisions"]},
                        {"PortInputSupport"},
                    )
                else:
                    self.assertTrue(row["passed"], row)
        finally:
            support.Shape = original
            self.doc.recompute()

    def test_native_output_limits_ratio_and_mesh_adjustment(self):
        from gondola.validation.propulsion import (
            drive_motion_check,
            mesh_adjustment_check,
        )

        for prefix in ("Port", "Starboard"):
            with self.subTest(prefix=prefix):
                result = drive_motion_check(self.doc, prefix)
                self.assertTrue(result["passed"], result)
                result = mesh_adjustment_check(self.doc, prefix)
                self.assertTrue(result["passed"], result)

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
                "Placement.Rotation.Angle", "PortPod.Placement.Rotation.Angle / 3"
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

    def test_all_output_and_input_bearings_are_captured(self):
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
            for suffix in ("Inner", "Outer"):
                result = bearing_stack_check(
                    world_shape(self.doc.getObject(prefix + "InputBearing" + suffix)),
                    world_shape(self.doc.getObject(prefix + "InputShaft")),
                    world_shape(self.doc.getObject(prefix + "InputSupport")),
                    world_shape(
                        self.doc.getObject(prefix + "InputBearingCap" + suffix)
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
        self.assertAlmostEqual(result["nut_engagement_length_mm"], 1.2)

    def test_servo_ear_fasteners_have_seated_heads_and_complete_smaller_nuts(self):
        from gondola.cad import world_shape
        from gondola.validation.propulsion import clamp_fastener_check

        for prefix in ("Port", "Starboard"):
            clamp = Part.makeCompound(
                [
                    world_shape(self.doc.getObject(prefix + "Servo")),
                    world_shape(self.doc.getObject(prefix + "InputSupport")),
                ]
            )
            for suffix in ("Negative", "Positive"):
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

    def test_input_mounts_allow_bolt_first_removal_and_lateral_nut_exit(self):
        from gondola.cad import world_shape
        from gondola.validation.propulsion import fastener_service_check

        objects = (
            self.module["printed"] + self.module["hardware"] + self.module["references"]
        )
        shapes = {obj.Name: world_shape(obj) for obj in objects}
        for prefix in ("Port", "Starboard"):
            for suffix in ("Negative", "Positive"):
                bolt_name = prefix + "InputMount" + suffix + "Bolt"
                nut_name = prefix + "InputMount" + suffix + "Nut"
                nut = shapes[nut_name]
                result = fastener_service_check(
                    shapes[bolt_name],
                    nut,
                    {
                        name: shape
                        for name, shape in shapes.items()
                        if name not in (bolt_name, nut_name)
                    },
                    nut_lateral_direction=(
                        1 if nut.BoundBox.Center.x > 0 else -1,
                        0,
                        0,
                    ),
                )
                self.assertTrue(result["passed"], (bolt_name, result))

    def test_outer_bearing_cap_nut_can_disengage_with_horn_clamp_installed(self):
        from gondola.cad import world_shape
        from gondola.validation.propulsion import fastener_service_check

        objects = (
            self.module["printed"] + self.module["hardware"] + self.module["references"]
        )
        shapes = {obj.Name: world_shape(obj) for obj in objects}
        for prefix in ("Port", "Starboard"):
            bolt_name = prefix + "InputBearingCapOuterBolt"
            nut_name = prefix + "InputBearingCapOuterNut"
            result = fastener_service_check(
                shapes[bolt_name],
                shapes[nut_name],
                {
                    name: shape
                    for name, shape in shapes.items()
                    if name not in (bolt_name, nut_name)
                },
            )
            self.assertTrue(result["passed"], (bolt_name, result))
            self.assertAlmostEqual(result["nut_thread_disengagement_travel_mm"], 2.7)

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
        self.assertEqual(sum(obj.HardwareSKU == "MR63ZZ" for obj in hardware), 8)
        self.assertEqual(
            sum(str(obj.HardwareSKU).startswith("GEABP") for obj in hardware), 4
        )
        self.assertEqual(
            sum(str(obj.HardwareSKU).startswith("PSFU") for obj in hardware), 6
        )
        self.assertTrue(
            all(not bool(getattr(obj, "PrintPart", False)) for obj in hardware)
        )
        self.assertTrue(
            all(len(obj.Shape.Solids) == 1 for obj in self.module["printed"])
        )


if __name__ == "__main__":
    unittest.main()
