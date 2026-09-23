"""Continuous rotation rejects between-pose hazards and restores native state."""

import unittest
from unittest.mock import patch

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires FreeCAD")
class RelativeRotationCertificateTests(unittest.TestCase):
    def moving(self):
        from gondola.validation.relative_motion import _part

        return _part(
            Part.makeBox(1, 1, 1, App.Vector(3, -0.5, -0.5)),
            "moving",
            group="PortPod",
            prefix="Port",
            rate=1,
        )

    def test_thin_between_pose_obstacle_is_rejected(self):
        from gondola.validation.relative_motion import _certify_pair, _part

        moving = self.moving()
        obstacle = _part(
            Part.makeBox(0.02, 0.2, 0.02, App.Vector(-0.01, -0.1, -3.51)), "obstacle"
        )
        for angle in (-180, 0, 180):
            body = moving["shape"].copy()
            body.rotate(App.Vector(), App.Vector(0, 1, 0), angle)
            self.assertGreater(body.distToShape(obstacle["shape"])[0], 1)
        result = _certify_pair(moving, obstacle)
        self.assertFalse(result["passed"], result)
        self.assertLessEqual(result["gap_mm"], 0.1)
        self.assertGreater(result["intersection_mm3"], 0)

    def test_moving_a_clear_obstacle_into_the_orbit_changes_the_result(self):
        from gondola.validation.relative_motion import _certify_pair, _part

        clear = Part.makeBox(0.1, 0.1, 0.1, App.Vector(12, 0, 0))
        self.assertTrue(
            _certify_pair(self.moving(), _part(clear, "obstacle"))["passed"]
        )
        clear.translate(App.Vector(-12, 0, -3.5))
        self.assertFalse(
            _certify_pair(self.moving(), _part(clear, "obstacle"))["passed"]
        )

    def test_small_positive_gap_does_not_meet_the_clearance_policy(self):
        from gondola.validation.relative_motion import _certify_pair, _part

        obstacle = _part(Part.makeBox(1, 1, 1, App.Vector(3, 0.55, -0.5)), "near_wall")
        result = _certify_pair(self.moving(), obstacle)
        self.assertFalse(result["passed"], result)
        self.assertAlmostEqual(result["gap_mm"], 0.05)

    def test_independent_axes_are_not_treated_as_synchronized(self):
        from gondola.validation.relative_motion import _certify_pair, _part

        other = _part(
            Part.makeBox(1, 1, 1, App.Vector(-4, -0.5, -0.5)),
            "other",
            group="StarboardPod",
            prefix="Starboard",
            rate=1,
        )
        result = _certify_pair(self.moving(), other)
        self.assertFalse(result["passed"], result)
        self.assertIn("Independent axes", result["error"])

    def test_unfinished_interval_fails_closed(self):
        from gondola.validation.relative_motion import _certify_pair, _part

        obstacle = _part(
            Part.makeBox(0.1, 0.1, 0.1, App.Vector(0, 0, -3.5)), "obstacle"
        )
        result = _certify_pair(self.moving(), obstacle, max_depth=0)
        self.assertFalse(result["passed"], result)
        self.assertIn("unresolved_interval_deg", result)

    def test_fully_contained_obstacle_is_not_mistaken_for_a_surface_gap(self):
        from gondola.validation.relative_motion import _certify_pair, _part

        moving = _part(
            Part.makeBox(10, 10, 10), "outer", group="PortPod", prefix="Port", rate=1
        )
        obstacle = _part(Part.makeBox(1, 1, 1, App.Vector(3, 3, 3)), "inner")
        result = _certify_pair(moving, obstacle)
        self.assertFalse(result["passed"], result)
        self.assertGreater(result["intersection_mm3"], 0.9)


@unittest.skipIf(App is None, "Requires FreeCAD")
class NativeRelativeMotionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.parts.propulsion import build_propulsion_module

        cls.doc = App.newDocument("RelativeMotionRegression")
        cls.module = build_propulsion_module(cls.doc)

    @classmethod
    def tearDownClass(cls):
        App.closeDocument(cls.doc.Name)

    def check_without_repeating_all_pair_geometry(self, module=None):
        from gondola.validation.relative_motion import relative_motion_check

        # The certificate is exercised geometrically above. These integration
        # tests target inventory, native kinematics and functional-fit identity.
        with patch(
            "gondola.validation.relative_motion._certify_pair",
            return_value={"passed": True, "test_pair_stub": True},
        ):
            return relative_motion_check(self.doc, module or self.module)

    def horn_and_servo_parts(self, prefix):
        from gondola.cad import world_shape
        from gondola.validation.relative_motion import _part

        inverse = self.doc.MainPropulsionModule.getGlobalPlacement().inverse()
        mount = self.doc.getObject(prefix + "ServoMount")
        axis = inverse.multiply(mount.getGlobalPlacement()).Base
        result = []
        for suffix in ("ServoHorn", "Servo"):
            obj = self.doc.getObject(prefix + suffix)
            shape = world_shape(obj)
            shape.Placement = inverse.multiply(shape.Placement)
            arguments = (
                dict(
                    group=prefix + "InputDrive",
                    prefix=prefix,
                    axis=tuple(axis),
                    rate=-1 / 3,
                )
                if suffix == "ServoHorn"
                else {}
            )
            result.append(_part(shape, obj.Name, **arguments))
        return result

    def test_both_mirrored_horns_clear_actual_cases_and_ears_continuously(self):
        from gondola.validation.relative_motion import _horn_case_clearance

        for prefix in ("Port", "Starboard"):
            with self.subTest(side=prefix):
                result = _horn_case_clearance(*self.horn_and_servo_parts(prefix))
                self.assertTrue(result["passed"], result)
                self.assertGreater(result["guaranteed_gap_mm"], 0.1)
                self.assertLessEqual(result["guaranteed_gap_mm"], 0.2 + 1e-7)
                interval = result["excluded_spline_axial_interval_mm"]
                self.assertAlmostEqual(interval[1] - interval[0], 2.7)

    def test_case_lobe_entering_horn_orbit_is_not_hidden_as_spline_contact(self):
        from gondola.parts import servo_bridge
        from gondola.validation.relative_motion import _horn_case_clearance

        servo = self.doc.PortServo
        original = servo.Shape.copy()
        try:
            # The lobe joins the actual case but clears the neutral horn; its
            # forward face enters the blade orbit at intermediate input angles.
            lobe = Part.makeBox(
                9, 5, 1, App.Vector(0, servo_bridge.case_front_y() - 1, -6)
            )
            servo.Shape = original.fuse(lobe)
            self.doc.recompute()
            horn, body = self.horn_and_servo_parts("Port")
            self.assertLess(horn["shape"].common(body["shape"]).Volume, 1e-7)
            result = _horn_case_clearance(horn, body)
            self.assertFalse(result["passed"], result)
            self.assertGreater(result["intersection_mm3"], 0)
            # The top-level functional classification must consume this new
            # guard, instead of accepting the old whole-servo exemption.
            with patch(
                "gondola.validation.relative_motion._horn_case_clearance",
                return_value=result,
            ):
                result = self.check_without_repeating_all_pair_geometry()
            self.assertFalse(result["passed"], result)
        finally:
            servo.Shape = original
            self.doc.recompute()

    def test_changed_spline_projection_cannot_expand_the_contact_exemption(self):
        from gondola.validation.relative_motion import _horn_case_clearance

        servo = self.doc.PortServo
        original = servo.Shape.copy()
        try:
            extension = Part.makeCylinder(
                1.95, 0.4, App.Vector(0, 33.4, 0), App.Vector(0, 1, 0)
            )
            servo.Shape = original.fuse(extension).removeSplitter()
            self.doc.recompute()
            result = _horn_case_clearance(*self.horn_and_servo_parts("Port"))
            self.assertFalse(result["passed"], result)
            self.assertIn("unique sourced servo spline", result["error"])
        finally:
            servo.Shape = original
            self.doc.recompute()

    def test_transformed_root_and_independent_poses_are_restored(self):
        root = self.doc.MainPropulsionModule
        original = App.Placement(root.Placement)
        poses = [float(self.doc.PortPod.Tilt), float(self.doc.StarboardPod.Tilt)]
        try:
            root.Placement = App.Placement(
                App.Vector(13, -27, 41), App.Rotation(App.Vector(1, 2, 3), 47)
            )
            self.doc.PortPod.Tilt, self.doc.StarboardPod.Tilt = 23, -71
            self.doc.recompute()
            before = App.Placement(root.Placement)
            result = self.check_without_repeating_all_pair_geometry()
            self.assertTrue(result["passed"], result)
            self.assertEqual(float(self.doc.PortPod.Tilt), 23)
            self.assertEqual(float(self.doc.StarboardPod.Tilt), -71)
            self.assertLess((root.Placement.Base - before.Base).Length, 1e-9)
            self.assertTrue(root.Placement.Rotation.isSame(before.Rotation, 1e-9))
            self.assertEqual(len(result["functional_interfaces"]), 8)
            self.assertTrue(
                all(
                    not row["continuous_clearance_claimed"]
                    for row in result["functional_interfaces"]
                )
            )
        finally:
            root.Placement = original
            self.doc.PortPod.Tilt, self.doc.StarboardPod.Tilt = poses
            self.doc.recompute()

    def test_omitted_module_obstacle_fails_and_restores_pose(self):
        modified = dict(self.module)
        modified["hardware"] = [
            obj
            for obj in self.module["hardware"]
            if obj.Name != "PortOutputBearingCapNegativeNut"
        ]
        old = float(self.doc.PortPod.Tilt)
        try:
            self.doc.PortPod.Tilt = 63
            result = self.check_without_repeating_all_pair_geometry(modified)
            self.assertFalse(result["passed"], result)
            self.assertIn("PortOutputBearingCapNegativeNut", result["error"])
            self.assertEqual(float(self.doc.PortPod.Tilt), 63)
        finally:
            self.doc.PortPod.Tilt = old
            self.doc.recompute()

    def test_moved_bearing_is_not_exempted_by_its_name(self):
        bearing = self.doc.PortOutputBearingNegative
        original = App.Placement(bearing.Placement)
        try:
            bearing.Placement.Base.x += 0.5
            self.doc.recompute()
            result = self.check_without_repeating_all_pair_geometry()
            self.assertFalse(result["passed"], result)
            row = next(
                row
                for row in result["functional_interfaces"]
                if bearing.Name in row["parts"]
            )
            self.assertFalse(row["classification_passed"], row)
        finally:
            bearing.Placement = original
            self.doc.recompute()

    def test_broken_native_ratio_expression_fails_closed(self):
        drive = self.doc.PortInputDrive
        expression = dict(drive.ExpressionEngine)[".Placement.Rotation.Angle"]
        try:
            # This nonlinear expression agrees at zero and one degree. A probe
            # at one degree alone must not authorize the complete angle range.
            drive.setExpression(
                "Placement.Rotation.Angle",
                "-PortPod.Placement.Rotation.Angle ^ 2 / (3 * 1 deg)",
            )
            self.doc.recompute()
            result = self.check_without_repeating_all_pair_geometry()
            self.assertFalse(result["passed"], result)
            self.assertIn("Native motion", result["error"])
        finally:
            drive.setExpression("Placement.Rotation.Angle", expression)
            self.doc.recompute()

    def test_an_obstacle_declared_fixed_cannot_follow_the_tilt(self):
        obstacle = self.doc.PortOutputBearingCapNegativeNut
        original = App.Placement(obstacle.Placement)
        try:
            obstacle.setExpression(
                "Placement.Base.x",
                f"{original.Base.x:g} mm + PortPod.Tilt / (1 deg) * 1 mm",
            )
            self.doc.recompute()
            result = self.check_without_repeating_all_pair_geometry()
            self.assertFalse(result["passed"], result)
            self.assertIn(obstacle.Name + ".Placement.Base.x", result["error"])
        finally:
            obstacle.setExpression("Placement.Base.x", None)
            obstacle.Placement = original
            self.doc.recompute()

    def test_nonlinear_motion_on_a_child_or_parent_is_rejected_without_sampling(self):
        # Zero at both neutral and the one-degree kinematics probe. The closed
        # expression contract must still reject its intermediate/future motion.
        nonlinear = "PortPod.Tilt * (PortPod.Tilt - 1 deg) / (1 deg ^ 2) * 1 mm"
        for name in ("PortHornGearAdapter", "PortServoMount"):
            obj = self.doc.getObject(name)
            original = App.Placement(obj.Placement)
            try:
                obj.setExpression(
                    "Placement.Base.x", f"{original.Base.x:g} mm + " + nonlinear
                )
                self.doc.recompute()
                result = self.check_without_repeating_all_pair_geometry()
                self.assertFalse(result["passed"], result)
                self.assertIn(name + ".Placement.Base.x", result["error"])
            finally:
                obj.setExpression("Placement.Base.x", None)
                obj.Placement = original
                self.doc.recompute()

    def test_indirect_expression_on_a_manual_station_control_is_rejected(self):
        root = self.doc.MainPropulsionModule
        original = App.Placement(root.Placement)
        helper = self.doc.addObject("App::FeaturePython", "IndirectMotionControl")
        helper.addProperty("App::PropertyDistance", "Offset")
        root.addProperty("App::PropertyDistance", "RailPositionX")
        try:
            # The final placement formula itself is canonical. Its two-step
            # input chain introduces the forbidden dependency on tilt.
            helper.setExpression(
                "Offset", "PortPod.Tilt * (PortPod.Tilt - 1 deg) / (1 deg ^ 2) * 1 mm"
            )
            root.setExpression("RailPositionX", "IndirectMotionControl.Offset")
            root.setExpression("Placement.Base.x", "RailPositionX")
            self.doc.recompute()
            result = self.check_without_repeating_all_pair_geometry()
            self.assertFalse(result["passed"], result)
            self.assertIn("expression contract rejects", result["error"])
        finally:
            root.setExpression("Placement.Base.x", None)
            root.setExpression("RailPositionX", None)
            root.removeProperty("RailPositionX")
            self.doc.removeObject(helper.Name)
            root.Placement = original
            self.doc.recompute()

    def test_a_motion_dependent_output_limit_is_rejected(self):
        pod = self.doc.PortPod
        try:
            pod.setExpression(
                "MinimumTilt", "-180 deg + Tilt * (Tilt - 1 deg) / (1 deg)"
            )
            self.doc.recompute()
            result = self.check_without_repeating_all_pair_geometry()
            self.assertFalse(result["passed"], result)
            self.assertIn("PortPod.MinimumTilt", result["error"])
        finally:
            pod.setExpression("MinimumTilt", None)
            pod.MinimumTilt = -180
            self.doc.recompute()


if __name__ == "__main__":
    unittest.main()
