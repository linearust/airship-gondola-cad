"""One fixed servo/output frame: connected stock, real lands and no separate saddle."""

import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class IntegratedServoFrameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.parts import propulsion

        cls.doc = App.newDocument("IntegratedServoFrame")
        cls.module = propulsion.build_propulsion_module(cls.doc)

    @classmethod
    def tearDownClass(cls):
        App.closeDocument(cls.doc.Name)

    def check(self):
        from gondola.validation.servo_module import integrated_frame_check

        return integrated_frame_check(self.doc, self.module)

    @staticmethod
    def opposite(shape, sign):
        if sign < 0:
            shape.rotate(App.Vector(), App.Vector(0, 0, 1), 180)
        return shape

    def test_one_mirrored_connected_print_carries_both_servo_supports(self):
        result = self.check()
        self.assertTrue(result["passed"], result)
        self.assertEqual(result["registered_print_count"], 1)
        self.assertTrue(result["single_valid_solid"])
        self.assertLess(result["half_turn_symmetry_difference_mm3"], 1e-7)
        self.assertEqual(result["obsolete_separate_supports"], [])
        self.assertIsNone(self.doc.getObject("ServoDriveBridge"))
        self.assertEqual(self.doc.PropulsionFixedFrame.PrintSKU, "PropulsionFixedFrame")
        # Both per-servo datums move8mm inward. The organizational parent is
        # retained; it is not an independently removable printed support.
        self.assertAlmostEqual(self.doc.PortServoMount.Placement.Base.x, 16)
        self.assertAlmostEqual(self.doc.PortServoMount.Placement.Base.z, 50)
        self.assertAlmostEqual(self.doc.StarboardServoMount.Placement.Base.x, -16)
        self.assertAlmostEqual(self.doc.StarboardServoMount.Placement.Base.z, 50)
        self.assertAlmostEqual(self.doc.PortServoMount.Placement.Base.y, -8)
        self.assertAlmostEqual(self.doc.StarboardServoMount.Placement.Base.y, 8)

    def test_global_parent_transform_preserves_integrated_shape_check(self):
        group = self.module["group"]
        original = group.Placement.copy()
        try:
            group.Placement = App.Placement(
                App.Vector(19, -31, 8), App.Rotation(App.Vector(2, 1, 3), 47)
            )
            self.doc.recompute()
            result = self.check()
            self.assertTrue(result["passed"], result)
        finally:
            group.Placement = original
            self.doc.recompute()

    def test_unregistered_duplicate_or_wrong_identity_frame_is_rejected(self):
        frame = self.doc.PropulsionFixedFrame
        original = list(self.module["printed"])
        sku = frame.PrintSKU
        try:
            self.module["printed"] = [obj for obj in original if obj is not frame]
            self.assertFalse(self.check()["passed"])
            self.module["printed"] = original + [frame]
            result = self.check()
            self.assertFalse(result["passed"], result)
            self.assertEqual(result["registered_print_count"], 2)
            self.module["printed"] = original
            frame.PrintSKU = "ObsoleteSeparateSupport"
            self.assertFalse(self.check()["passed"])
        finally:
            frame.PrintSKU = sku
            self.module["printed"] = original

    def test_returned_removable_saddle_is_rejected(self):
        obj = self.doc.addObject("Part::Feature", "ServoDriveBridge")
        try:
            result = self.check()
            self.assertFalse(result["passed"], result)
            self.assertEqual(result["obsolete_separate_supports"], ["ServoDriveBridge"])
        finally:
            self.doc.removeObject(obj.Name)

    def test_symmetric_disconnected_stock_cannot_pass_as_one_frame(self):
        frame = self.doc.PropulsionFixedFrame
        original = frame.Shape.copy()
        cube = Part.makeBox(1, 1, 1, App.Vector(100, 100, 20))
        try:
            frame.Shape = Part.makeCompound(
                [original, cube, self.opposite(cube.copy(), -1)]
            )
            result = self.check()
            self.assertFalse(result["passed"], result)
            self.assertFalse(result["single_valid_solid"])
            self.assertLess(result["half_turn_symmetry_difference_mm3"], 1e-7)
        finally:
            frame.Shape = original

    def test_asymmetric_missing_stock_is_rejected_while_solid_stays_connected(self):
        frame = self.doc.PropulsionFixedFrame
        original = frame.Shape.copy()
        loss = Part.makeBox(1, 1, 0.5, App.Vector(16, -0.5, 13))
        self.assertAlmostEqual(original.common(loss).Volume, 0.5)
        try:
            frame.Shape = original.cut(loss)
            result = self.check()
            self.assertFalse(result["passed"], result)
            self.assertTrue(result["single_valid_solid"])
            self.assertAlmostEqual(result["half_turn_symmetry_difference_mm3"], 1.0)
        finally:
            frame.Shape = original

    def test_individual_closed_frames_retain_full_walls_and_service_windows(self):
        from gondola.validation.propulsion import servo_mount_check

        for prefix in ("Port", "Starboard"):
            with self.subTest(side=prefix):
                result = servo_mount_check(self.doc, prefix)
                self.assertTrue(result["passed"], result)
                stock = result["cradle_stock_and_case_window"]
                self.assertEqual(stock["complete_inboard_web_thickness_mm"], 3)
                self.assertEqual(stock["complete_outboard_web_thickness_mm"], 3)
                self.assertEqual(stock["closed_service_window_mm"], [7.4, 20.4])
                self.assertEqual(stock["nominal_case_clearance_per_face_mm"], 0.2)
                self.assertLess(stock["unrequested_central_upper_stock_mm3"], 1e-7)
                self.assertLess(stock["missing_complete_cradle_stock_mm3"], 1e-7)
                self.assertLess(stock["outward_case_window_intrusion_mm3"], 1e-7)
                self.assertTrue(
                    all(
                        v < 1e-7 for v in stock["missing_connection_stock_mm3"].values()
                    )
                )

    def test_missing_closed_side_walls_and_lower_connection_are_rejected(self):
        from gondola.validation.propulsion import servo_mount_check

        frame = self.doc.PropulsionFixedFrame
        original = frame.Shape.copy()
        cutters = {
            "inboard_wall": (Part.makeBox(0.5, 1, 1, App.Vector(9.3, -9, 42)), 0.5),
            "outboard_wall": (Part.makeBox(3, 5, 1, App.Vector(19.7, -10.5, 45)), 15),
            "lower_foot": (Part.makeBox(5, 5, 1, App.Vector(17, -10.5, 25)), 25),
        }
        try:
            for name, (cutter, volume) in cutters.items():
                for prefix, sign in (("Port", 1), ("Starboard", -1)):
                    with self.subTest(stock=name, side=prefix):
                        frame.Shape = original.cut(self.opposite(cutter.copy(), sign))
                        self.assertTrue(frame.Shape.isValid())
                        self.assertEqual(len(frame.Shape.Solids), 1)
                        result = servo_mount_check(self.doc, prefix)
                        stock = result["cradle_stock_and_case_window"]
                        self.assertFalse(stock["passed"], stock)
                        self.assertFalse(result["passed"], result)
                        key = "missing_complete_cradle_stock_mm3"
                        if name == "lower_foot":
                            self.assertAlmostEqual(
                                stock["missing_connection_stock_mm3"][
                                    prefix.lower() + "_foot"
                                ],
                                volume,
                            )
                        else:
                            self.assertAlmostEqual(stock[key], volume)
        finally:
            frame.Shape = original

    def test_no_upper_inter_servo_tie_is_present(self):
        frame = self.doc.PropulsionFixedFrame.Shape
        gap = Part.makeBox(18.6, 21, 30.7, App.Vector(-9.3, -10.5, 29.5))
        self.assertLess(abs(frame.common(gap).Volume), 1e-7)
        for sign in (1, -1):
            wall = self.opposite(
                Part.makeBox(3, 5, 20.4, App.Vector(19.7, -10.5, 34.8)), sign
            )
            self.assertLess(abs(wall.cut(frame).Volume), 1e-7)

    def test_axial_driver_sweep_catches_obstacle_between_clear_endpoints(self):
        from gondola.contracts.drive import SELECTED_DRIVE
        from gondola.validation.propulsion_service import (
            driver_service_segment_check,
            module_service_shapes,
        )

        shapes, missing = module_service_shapes(self.doc, self.module)
        self.assertEqual(missing, [])
        for prefix, sign in (("Port", 1), ("Starboard", -1)):
            with self.subTest(side=prefix):
                gear = shapes[prefix + "DriverGear"]
                blocker = self.opposite(
                    Part.makeBox(0.5, 0.5, 0.5, App.Vector(31, 26, 50)), sign
                )
                start, end = (sign * 7, 0, 0), (sign * 7, sign * 14, 0)
                for point in (start, end):
                    endpoint = gear.copy()
                    endpoint.translate(App.Vector(*point))
                    self.assertLess(abs(endpoint.common(blocker).Volume), 1e-7)
                result = driver_service_segment_check(
                    gear, start, end, {"midway_blocker": blocker}, SELECTED_DRIVE, sign
                )
                self.assertLess(result["gear_outside_reference_envelope_mm3"], 1e-7)
                self.assertFalse(result["passed"], result)
                self.assertAlmostEqual(
                    result["segments"][0]["intersection_mm3"]["midway_blocker"], 0.125
                )
                self.assertTrue(
                    driver_service_segment_check(
                        gear, start, end, {}, SELECTED_DRIVE, sign
                    )["passed"]
                )

    def test_compact_feet_do_not_restore_the_broad_lower_plate(self):
        frame = self.doc.PropulsionFixedFrame.Shape
        for sign in (1, -1):
            unused = self.opposite(
                Part.makeBox(13, 10, 5, App.Vector(9.2, -5, 24.5)), sign
            )
            self.assertLess(abs(frame.common(unused).Volume), 1e-7)
            foot = self.opposite(
                Part.makeBox(16.7, 5, 5, App.Vector(6, -10.5, 24.5)), sign
            )
            self.assertLess(abs(foot.cut(frame).Volume), 1e-7)

    def test_case_size_tolerance_leaves_clearance_without_an_interference_fit(self):
        frame = self.doc.PropulsionFixedFrame.Shape
        for sign in (1, -1):
            # Published+0.2mm total case size leaves0.1mm at each centred face.
            maximum = self.opposite(
                Part.makeBox(7.2, 5, 20.2, App.Vector(12.4, -10.5, 34.9)), sign
            )
            self.assertLess(abs(frame.common(maximum).Volume), 1e-7)
            self.assertAlmostEqual(frame.distToShape(maximum)[0], 0.1, places=6)
            oversized = self.opposite(
                Part.makeBox(7.6, 5, 20.6, App.Vector(12.2, -10.5, 34.7)), sign
            )
            self.assertGreater(frame.common(oversized).Volume, 1)

    def test_shaft_dogleg_catches_a_midway_lateral_obstacle(self):
        from gondola.validation.propulsion_service import (
            continuous_path,
            module_service_shapes,
        )
        from gondola.validation.servo_module import input_shaft_service_waypoints

        shapes, _ = module_service_shapes(self.doc, self.module)
        for prefix, sign in (("Port", 1), ("Starboard", -1)):
            shaft = shapes[prefix + "InputShaft"]
            blocker = self.opposite(
                Part.makeBox(0.5, 0.5, 0.5, App.Vector(45.75, 34.75, 49.75)), sign
            )
            points = input_shaft_service_waypoints(prefix)
            for point in points:
                endpoint = shaft.copy()
                endpoint.translate(App.Vector(*point))
                self.assertLess(abs(endpoint.common(blocker).Volume), 1e-7)
            result = continuous_path(shaft, points, {"midway_blocker": blocker})
            self.assertFalse(result["passed"], result)

    def test_short_input_shaft_cannot_claim_the_four_mm_grip_tip(self):
        from gondola.validation.horn_coupling import input_stub_grip_stock_check
        from gondola.validation.propulsion_service import module_service_shapes

        shapes, _ = module_service_shapes(self.doc, self.module)
        for prefix, sign in (("Port", 1), ("Starboard", -1)):
            shaft = shapes[prefix + "InputShaft"]
            self.assertTrue(input_stub_grip_stock_check(shaft, prefix)["passed"])
            cutter = self.opposite(
                Part.makeBox(4, 2.1, 4, App.Vector(14, 24.5, 48)), sign
            )
            shortened = shaft.cut(cutter)
            result = input_stub_grip_stock_check(shortened, prefix)
            self.assertFalse(result["passed"], result)
            self.assertGreater(result["missing_grip_stock_mm3"], 10)

    def test_plier_closing_envelope_cannot_ignore_a_thin_obstruction(self):
        from gondola.validation.horn_coupling import assembled_servo_service_check

        blocker = self.doc.addObject("Part::Feature", "PlierClosingBlocker")
        self.module["group"].addObject(blocker)
        # Above the initial lower-jaw face48.5, below its closed limit48.6,
        # and outside the shaft: an open-jaw-only screen would miss this.
        blocker.Shape = Part.makeBox(0.2, 0.2, 0.03, App.Vector(20, 23, 48.55))
        modified = {**self.module, "references": self.module["references"] + [blocker]}
        try:
            result = assembled_servo_service_check(self.doc, modified, "Port")
            self.assertFalse(result["passed"], result)
            self.assertFalse(result["input_stub_grip_tool"]["passed"])
            self.assertTrue(result["input_stub_grip_tool"]["tip_stock"]["passed"])
        finally:
            self.doc.removeObject(blocker.Name)

    def test_driver_service_rejects_mixed_axis_and_unstaged_axial_release(self):
        from gondola.contracts.drive import SELECTED_DRIVE
        from gondola.validation.propulsion_service import (
            driver_service_segment_check,
            module_service_shapes,
            servo_lateral_service_check,
        )

        shapes, _ = module_service_shapes(self.doc, self.module)
        fixed = {"PropulsionFixedFrame": shapes["PropulsionFixedFrame"]}
        for prefix, sign in (("Port", 1), ("Starboard", -1)):
            gear = shapes[prefix + "DriverGear"]
            self.assertFalse(
                driver_service_segment_check(
                    gear,
                    (0, 0, 0),
                    (sign * 7, sign * 14, 0),
                    fixed,
                    SELECTED_DRIVE,
                    sign,
                )["passed"]
            )
            self.assertFalse(
                driver_service_segment_check(
                    gear, (0, 0, 0), (0, sign * 14, 0), fixed, SELECTED_DRIVE, sign
                )["passed"]
            )
            self.assertFalse(
                servo_lateral_service_check(
                    shapes[prefix + "Servo"], (0, 0, 0), (sign * 60, 0, 0), fixed
                )["passed"]
            )

    def test_case_window_requires_nominal_clearance_even_without_case_collision(self):
        from gondola.validation.propulsion import servo_mount_check

        frame = self.doc.PropulsionFixedFrame
        original = frame.Shape.copy()
        intrusion = Part.makeBox(0.1, 1, 1, App.Vector(12.3, -9, 42))
        try:
            frame.Shape = original.fuse(intrusion)
            result = servo_mount_check(self.doc, "Port")
            self.assertLess(result["servo_frame_intersection_mm3"], 1e-7)
            stock = result["cradle_stock_and_case_window"]
            self.assertAlmostEqual(stock["outward_case_window_intrusion_mm3"], 0.1)
            self.assertFalse(stock["passed"], stock)
            self.assertFalse(result["passed"], result)
        finally:
            frame.Shape = original

    def test_integrated_frame_clears_every_other_installed_physical_part(self):
        from gondola.cad import world_shape

        frame = world_shape(self.doc.PropulsionFixedFrame)
        for group in ("printed", "hardware", "references"):
            for obj in self.module[group]:
                if obj.Name != "PropulsionFixedFrame":
                    with self.subTest(part=obj.Name):
                        self.assertLess(
                            abs(frame.common(world_shape(obj)).Volume), 1e-7
                        )


if __name__ == "__main__":
    unittest.main()
