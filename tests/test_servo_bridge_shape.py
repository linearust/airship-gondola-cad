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
            "direct_servo_plinth": (
                Part.makeBox(5, 5, 1, App.Vector(17, -10.5, 25)),
                25,
            ),
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
                        if name == "direct_servo_plinth":
                            self.assertAlmostEqual(
                                stock["missing_connection_stock_mm3"][name],
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

    def test_closed_cradles_bear_directly_on_the_complete_central_plinth(self):
        frame = self.doc.PropulsionFixedFrame.Shape
        plinth = Part.makeBox(45.4, 21, 9.5, App.Vector(-22.7, -10.5, 20))
        self.assertLess(abs(plinth.cut(frame).Volume), 1e-7)
        for sign in (1, -1):
            seating = self.opposite(
                Part.makeBox(13.4, 5, 0.2, App.Vector(9.3, -10.5, 29.4)), sign
            )
            self.assertLess(abs(seating.cut(frame).Volume), 1e-7)

    def test_gap_below_cradle_is_rejected_despite_other_connected_material(self):
        from gondola.validation.propulsion import servo_mount_check

        frame = self.doc.PropulsionFixedFrame
        original = frame.Shape.copy()
        gap = Part.makeBox(4, 5, 0.2, App.Vector(17, -10.5, 29.3))
        try:
            frame.Shape = original.cut(gap)
            self.assertEqual(len(frame.Shape.Solids), 1)
            result = servo_mount_check(self.doc, "Port")
            self.assertFalse(result["passed"], result)
            self.assertAlmostEqual(
                result["cradle_stock_and_case_window"]["missing_connection_stock_mm3"][
                    "direct_servo_plinth"
                ],
                4,
            )
        finally:
            frame.Shape = original

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
                Part.makeBox(0.5, 0.5, 0.5, App.Vector(45.75, 44.75, 49.75)), sign
            )
            points = input_shaft_service_waypoints(prefix)
            for point in points:
                endpoint = shaft.copy()
                endpoint.translate(App.Vector(*point))
                self.assertLess(abs(endpoint.common(blocker).Volume), 1e-7)
            midpoint = shaft.copy()
            midpoint.translate(App.Vector(sign * 30, sign * 32, 0))
            self.assertGreater(midpoint.common(blocker).Volume, 0.1)
            result = continuous_path(shaft, points, {"midway_blocker": blocker})
            self.assertFalse(result["passed"], result)

    def test_short_input_shaft_cannot_claim_the_accessible_round_grip_tip(self):
        from gondola.validation.horn_coupling import input_stub_grip_stock_check
        from gondola.validation.propulsion_service import module_service_shapes

        shapes, _ = module_service_shapes(self.doc, self.module)
        for prefix, sign in (("Port", 1), ("Starboard", -1)):
            shaft = shapes[prefix + "InputShaft"]
            self.assertTrue(input_stub_grip_stock_check(shaft, prefix)["passed"])
            cutter = self.opposite(
                Part.makeBox(4, 2.1, 4, App.Vector(14, 39.5, 48)), sign
            )
            shortened = shaft.cut(cutter)
            result = input_stub_grip_stock_check(shortened, prefix)
            self.assertFalse(result["passed"], result)
            self.assertGreater(result["missing_grip_stock_mm3"], 10)

    def test_side_entry_plier_envelope_cannot_ignore_a_thin_obstruction(self):
        from gondola.validation.horn_coupling import assembled_servo_service_check

        blocker = self.doc.addObject("Part::Feature", "PlierEntryBlocker")
        self.module["group"].addObject(blocker)
        # Outside the shaft and its removal path, but within the actual lower
        # side-entry jaw. Checking only the moving shaft would miss this.
        blocker.Shape = Part.makeBox(0.2, 0.2, 0.03, App.Vector(20, 38, 48.2))
        modified = {**self.module, "references": self.module["references"] + [blocker]}
        try:
            result = assembled_servo_service_check(self.doc, modified, "Port")
            self.assertFalse(result["passed"], result)
            self.assertFalse(result["input_stub_grip_tool"]["passed"])
            self.assertTrue(result["input_stub_grip_tool"]["tip_stock"]["passed"])
        finally:
            self.doc.removeObject(blocker.Name)

    def test_unmeshed_rotor_parking_preserves_input_and_fixed_bearing_poses(self):
        from gondola.validation.propulsion_service import module_service_shapes
        from gondola.validation.servo_module import park_output_rotor_for_input_service

        shapes, missing = module_service_shapes(self.doc, self.module)
        self.assertFalse(missing)
        removed = {p + "OutputGear" for p in ("Port", "Starboard")}
        for prefix in ("Port", "Starboard"):
            original = self.doc.getObject(prefix + "InputDrive").getGlobalPlacement()
            parked, report = park_output_rotor_for_input_service(
                self.doc, self.module, prefix, shapes, removed
            )
            self.assertTrue(report["passed"], report)
            self.assertEqual(report["angle_deg"], 90)
            self.assertTrue(report["input_remains_neutral"])
            self.assertNotIn(prefix + "OutputGear", report["moving_parts"])
            self.assertIn(prefix + "InputBearing", report["retained_parts"])
            for name in report["retained_parts"]:
                self.assertTrue(
                    parked[name].Placement.isSame(shapes[name].Placement, 1e-7)
                )
            self.assertTrue(
                original.isSame(
                    self.doc.getObject(prefix + "InputDrive").getGlobalPlacement(), 1e-7
                )
            )

    def test_rotor_parking_rejects_an_obstacle_between_clear_endpoint_poses(self):
        from gondola.validation.propulsion_service import module_service_shapes
        from gondola.validation.servo_module import park_output_rotor_for_input_service

        shapes, _ = module_service_shapes(self.doc, self.module)
        bolt = shapes["PortOutputClampNegativeBolt"]
        point = App.Vector(14, 49.5, 50)
        pivot = App.Vector(0, 75, 50)
        point = pivot + App.Rotation(App.Vector(0, 1, 0), 45).multVec(point - pivot)
        blocker = Part.makeBox(0.2, 0.2, 0.2, point - App.Vector(0.1, 0.1, 0.1))
        for angle in (0, 90):
            endpoint = bolt.copy()
            endpoint.rotate(pivot, App.Vector(0, 1, 0), angle)
            self.assertLess(abs(endpoint.common(blocker).Volume), 1e-7)
        middle = bolt.copy()
        middle.rotate(pivot, App.Vector(0, 1, 0), 45)
        self.assertGreater(middle.common(blocker).Volume, 0.001)
        obj = self.doc.addObject("Part::Feature", "RotorParkingBlocker")
        self.module["group"].addObject(obj)
        obj.Shape = blocker
        try:
            shapes[obj.Name] = blocker
            _, result = park_output_rotor_for_input_service(
                self.doc,
                self.module,
                "Port",
                shapes,
                {"PortOutputGear", "StarboardOutputGear"},
            )
            self.assertFalse(result["passed"], result)
            row = next(
                r
                for r in result["continuous_rotation"]
                if r["part"] == "PortOutputClampNegativeBolt"
            )
            self.assertGreater(row["intersection_mm3"][obj.Name], 0.001)
        finally:
            self.doc.removeObject(obj.Name)

    def test_parking_requires_unmeshing_and_a_neutral_initial_input(self):
        from gondola.validation.propulsion_service import module_service_shapes
        from gondola.validation.servo_module import park_output_rotor_for_input_service

        shapes, _ = module_service_shapes(self.doc, self.module)
        _, meshed = park_output_rotor_for_input_service(
            self.doc, self.module, "Port", shapes, set()
        )
        self.assertFalse(meshed["passed"])
        pod = self.doc.PortPod
        original = float(pod.Tilt)
        try:
            pod.Tilt = 30
            self.doc.recompute()
            shapes, _ = module_service_shapes(self.doc, self.module)
            _, nonneutral = park_output_rotor_for_input_service(
                self.doc,
                self.module,
                "Port",
                shapes,
                {"PortOutputGear", "StarboardOutputGear"},
            )
            self.assertFalse(nonneutral["initial_input_and_output_neutral"])
            self.assertFalse(nonneutral["passed"])
        finally:
            pod.Tilt = original
            self.doc.recompute()

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
