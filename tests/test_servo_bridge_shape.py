"""Continuous nested U joint, full clamp lands and shaft-aware bench service."""

import math
import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class ServoBridgeShapeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.parts import propulsion

        cls.doc = App.newDocument("SymmetricServoBridge")
        cls.module = propulsion.build_propulsion_module(cls.doc)

    @classmethod
    def tearDownClass(cls):
        App.closeDocument(cls.doc.Name)

    def joint(self):
        from gondola.validation.servo_module import bridge_joint_check

        return bridge_joint_check(self.doc, self.module)

    @staticmethod
    def opposite(shape, sign):
        if sign < 0:
            shape.rotate(App.Vector(), App.Vector(0, 0, 1), 180)
        return shape

    def test_full_roof_and_both_fitted_walls_require_no_extra_pairs(self):
        result = self.joint()
        self.assertTrue(result["passed"], result)
        contacts = {row["interface"]: row for row in result["contacts"]}
        self.assertEqual(
            set(contacts),
            {
                "full_roof_support",
                "negative_y_beam_roof",
                "positive_y_beam_roof",
                "negative_y_wall",
                "positive_y_wall",
            },
        )
        self.assertAlmostEqual(
            contacts["full_roof_support"]["actual_contact_area_mm2"], 456
        )
        # At the Y±6 planes the lower crowns remove two circular segments
        # from each pair of 9.8mm wall contacts. Derive the area independently.
        radius, height = 4.5, 3.8  # Z6 bolt axis minus Z2.2 bridge bottom
        tangent = math.sqrt(radius**2 - height**2)
        circular_loss = height * (radius - tangent) - (
            radius**2 * math.pi / 4
            - (tangent * height + radius**2 * math.asin(tangent / radius)) / 2
        )
        lower_relief_area = 4 * circular_loss + 2 * 0.8 * height
        for name, y in (
            ("negative_y_wall", -6),
            ("positive_y_wall", 6),
        ):
            self.assertAlmostEqual(
                contacts[name]["actual_contact_area_mm2"],
                19.6 * 10.3 - 2 * math.pi * 1.7**2 - lower_relief_area,
            )
            self.assertEqual(contacts[name]["plane_position_mm"], y)
        for side in ("Port", "Starboard"):
            for kind in ("Bolt", "Nut"):
                self.assertIsNone(self.doc.getObject("ServoBridge" + side + kind))
        self.assertEqual(result["wrap_fit"]["nominal_fitted_side_gap_mm"], 0.0)
        self.assertEqual(result["wrap_fit"]["clamp_axis_spacing_mm"], 28)

    def test_bridge_roof_is_flat_and_beam_relief_is_functional(self):
        bridge = self.doc.ServoDriveBridge.Shape
        self.assertTrue(bridge.isValid())
        self.assertEqual(len(bridge.Solids), 1)
        # Full two-mm lower roof stock and bottom seating datum survive the
        # exposed R0.5 top rim; the upper inset stock is also uninterrupted.
        roof = Part.makeBox(38, 22, 2, App.Vector(-19, -11, 12.5)).fuse(
            Part.makeBox(37, 21, 0.5, App.Vector(-18.5, -10.5, 14.5))
        )
        self.assertLess(abs(roof.cut(bridge).Volume), 1e-7)
        relief = Part.makeBox(18.4, 22, 10.3, App.Vector(-9.2, -11, 2.2))
        self.assertLess(abs(relief.common(bridge).Volume), 1e-7)
        for sign in (1, -1):
            wall = self.opposite(
                Part.makeBox(9.8, 5, 1, App.Vector(-19, -11, 11)), sign
            )
            self.assertLess(abs(wall.cut(bridge).Volume), 1e-7)

    def test_outboard_head_release_preserves_inner_floors_and_nut_rims(self):
        for name in ("PropulsionFixedFrame", "ServoDriveBridge"):
            shape = self.doc.getObject(name).Shape
            self.assertAlmostEqual(shape.BoundBox.XMin, -19)
            self.assertAlmostEqual(shape.BoundBox.XMax, 19)
        bridge = self.doc.ServoDriveBridge.Shape
        frame = self.doc.PropulsionFixedFrame.Shape
        for sign in (1, -1):
            with self.subTest(side=sign):
                opening = self.opposite(
                    Part.makeBox(5, 2, 7, App.Vector(14, -11, 2.2)), sign
                )
                self.assertLess(abs(opening.common(bridge).Volume), 1e-7)
                # Removing the outer lip must leave the head floor intact.
                head_floor_end = self.opposite(
                    Part.makeBox(2.2, 3, 0.2, App.Vector(16.8, -9, 5.9)), sign
                )
                frame_end = self.opposite(
                    Part.makeBox(2.2, 4.75, 0.2, App.Vector(16.8, -6, 6.1)), sign
                )
                nut_rim = self.opposite(
                    Part.makeBox(1.8, 3, 4, App.Vector(17.2, 8, 4)), sign
                )
                for witness, shape in (
                    (head_floor_end, bridge),
                    (frame_end, frame),
                    (nut_rim, bridge),
                ):
                    self.assertLess(abs(witness.cut(shape).Volume), 1e-7)

    def test_small_cradle_root_blends_retain_servo_ear_clearance(self):
        bridge = self.doc.ServoDriveBridge.Shape
        # Independent radius1 concave witness, well away from end corners.
        blend = Part.makeBox(6, 1, 1, App.Vector(-3, 2.5, 15)).cut(
            Part.makeCylinder(1, 6, App.Vector(-3, 3.5, 16), App.Vector(1, 0, 0))
        )
        for sign in (1, -1):
            with self.subTest(side=sign):
                self.assertLess(
                    abs(self.opposite(blend.copy(), sign).cut(bridge).Volume), 1e-7
                )
        for servo_name in ("PortServo", "StarboardServo"):
            servo = self.doc.getObject(servo_name).Shape.copy()
            servo.Placement = self.doc.getObject(servo_name).getGlobalPlacement()
            self.assertLess(abs(bridge.common(servo).Volume), 1e-7)

    def test_heads_and_nuts_compress_both_bridge_and_frame_legs(self):
        for sign in (1, -1):
            for name, y, thickness in (
                ("ServoDriveBridge", -9, 3),
                ("ServoDriveBridge", 6, 2),
                ("PropulsionFixedFrame", -6, 4.75),
                ("PropulsionFixedFrame", 1.25, 4.75),
            ):
                stock = Part.makeCylinder(
                    3, thickness, App.Vector(14, y, 6), App.Vector(0, 1, 0)
                ).cut(
                    Part.makeCylinder(
                        1.7,
                        thickness + 0.2,
                        App.Vector(14, y - 0.1, 6),
                        App.Vector(0, 1, 0),
                    )
                )
                with self.subTest(side=sign, part=name):
                    self.assertLess(
                        abs(
                            self.opposite(stock, sign)
                            .cut(self.doc.getObject(name).Shape)
                            .Volume
                        ),
                        1e-7,
                    )

    def test_either_missing_head_or_frame_land_fails_independently(self):
        for name, y in (
            ("ServoDriveBridge", -9),
            ("ServoDriveBridge", 6),
            ("PropulsionFixedFrame", -6),
            ("PropulsionFixedFrame", 1.25),
        ):
            obj = self.doc.getObject(name)
            original = obj.Shape.copy()
            for sign in (1, -1):
                try:
                    loss = self.opposite(
                        Part.makeBox(1, 0.5, 0.3, App.Vector(13.5, y, 8.2)), sign
                    )
                    obj.Shape = original.cut(loss)
                    self.doc.recompute()
                    with self.subTest(part=name, side=sign):
                        self.assertFalse(self.joint()["passed"])
                finally:
                    obj.Shape = original
                    self.doc.recompute()

    def test_missing_central_seat_is_rejected_with_both_clamp_faces_intact(self):
        frame = self.doc.PropulsionFixedFrame
        original = frame.Shape.copy()
        try:
            frame.Shape = original.cut(
                Part.makeBox(38, 12, 0.2, App.Vector(-19, -6, 12.4))
            )
            self.doc.recompute()
            result = self.joint()
            self.assertFalse(result["passed"], result)
            contacts = {row["interface"]: row for row in result["contacts"]}
            self.assertAlmostEqual(
                contacts["full_roof_support"]["actual_contact_area_mm2"], 0
            )
        finally:
            frame.Shape = original
            self.doc.recompute()

    def test_each_wall_is_required_and_beam_relief_cannot_be_filled(self):
        bridge = self.doc.ServoDriveBridge
        original = bridge.Shape.copy()
        for sign in (1, -1):
            for kind, origin in (("missing", (17, -11, 10)), ("blocked", (-1, -8, 4))):
                try:
                    change = self.opposite(
                        Part.makeBox(2, 0.4, 1, App.Vector(*origin)), sign
                    )
                    bridge.Shape = (
                        original.cut(change)
                        if kind == "missing"
                        else original.fuse(change)
                    )
                    self.doc.recompute()
                    with self.subTest(side=sign, kind=kind):
                        self.assertFalse(self.joint()["passed"])
                finally:
                    bridge.Shape = original
                    self.doc.recompute()

    def test_lost_material_on_either_clamp_contact_face_is_rejected(self):
        frame = self.doc.PropulsionFixedFrame
        original = frame.Shape.copy()
        for sign in (1, -1):
            try:
                loss = self.opposite(
                    Part.makeBox(1, 0.2, 0.5, App.Vector(17.5, -6.1, 10)), sign
                )
                frame.Shape = original.cut(loss)
                self.doc.recompute()
                result = self.joint()
                self.assertFalse(result["passed"], result)
                name = "negative_y_wall" if sign > 0 else "positive_y_wall"
                row = next(
                    row for row in result["contacts"] if row["interface"] == name
                )
                self.assertAlmostEqual(
                    row["required_contact_area_mm2"] - row["actual_contact_area_mm2"],
                    0.5,
                )
            finally:
                frame.Shape = original
                self.doc.recompute()

    def test_changed_prints_clear_every_other_installed_module_part(self):
        from gondola.cad import world_shape

        shapes = {
            obj.Name: world_shape(obj)
            for group in ("printed", "hardware", "references")
            for obj in self.module[group]
        }
        for name in ("PropulsionFixedFrame", "ServoDriveBridge"):
            for other, shape in shapes.items():
                if name != other:
                    with self.subTest(part=name, obstacle=other):
                        self.assertLess(abs(shapes[name].common(shape).Volume), 1e-7)

    def test_service_envelope_contains_actual_bridge_and_leaves_u_open(self):
        from gondola.parts import servo_bridge

        envelope = servo_bridge.bridge_blank()
        self.assertLess(abs(self.doc.ServoDriveBridge.Shape.cut(envelope).Volume), 1e-7)
        frame_seat = Part.makeBox(38, 12, 7.1, App.Vector(-19, -6, 5.4))
        self.assertLess(abs(frame_seat.common(envelope).Volume), 1e-7)

    def test_ordered_service_keeps_shifted_driven_shafts_as_obstacles(self):
        from gondola.validation.servo_module import servo_module_service_check

        result = servo_module_service_check(self.doc, self.module)
        self.assertTrue(result["passed"], result)
        self.assertEqual(
            result["removed_output_gears"], ["PortOutputGear", "StarboardOutputGear"]
        )
        self.assertEqual(result["released_fasteners"], [])
        self.assertIn("both shared M3x20", result["prerequisites"])
        self.assertEqual(
            result["loosened_carrier_clamps"],
            ["PortOutputClampNegative", "StarboardOutputClampPositive"],
        )
        for row, name, offset in zip(
            result["shaft_staging"],
            ("PortOutputShaftNegative", "StarboardOutputShaftPositive"),
            ([0, 12, 0], [0, -12, 0]),
            strict=True,
        ):
            self.assertEqual(row["part"], name)
            self.assertEqual(row["staged_offset_mm"], offset)
            self.assertIn(name, result["retained_parts"])
            self.assertEqual(row["segments"][0]["end_mm"], offset)
        for row in result["part_paths"]:
            self.assertEqual(row["waypoints_mm"], [(0, 0, 0), (0, 0, 11), (80, 0, 11)])
            self.assertIn("PortOutputShaftNegative", row["obstacles"])
            self.assertIn("StarboardOutputShaftPositive", row["obstacles"])

    def test_partial_shared_rail_fastener_inventory_fails_before_service(self):
        from gondola.validation.servo_module import servo_module_service_check

        obj = self.doc.addObject(
            "Part::Feature", self.module["group"].Name + "OppositeRailMountNut"
        )
        self.module["group"].addObject(obj)
        obj.Shape = Part.makeBox(1, 1, 1, App.Vector(200, 200, 200))
        self.module["hardware"].append(obj)
        try:
            result = servo_module_service_check(self.doc, self.module)
            self.assertFalse(result["passed"])
            self.assertEqual(len(result["missing_parts"]), 3)
        finally:
            self.module["hardware"].remove(obj)
            self.doc.removeObject(obj.Name)
            self.doc.recompute()

    def test_continuous_service_detects_midpath_obstacle_with_clear_endpoints(self):
        from gondola.validation.servo_module import servo_module_service_check

        frame = self.doc.PropulsionFixedFrame
        original = frame.Shape.copy()
        obstacle = Part.makeBox(1, 1, 1, App.Vector(40, 0, 25))
        bridge = self.doc.ServoDriveBridge.Shape.copy()
        self.assertLess(abs(bridge.common(obstacle).Volume), 1e-7)
        bridge.translate(App.Vector(80, 0, 11))
        self.assertLess(abs(bridge.common(obstacle).Volume), 1e-7)
        try:
            frame.Shape = original.fuse(obstacle)
            self.doc.recompute()
            result = servo_module_service_check(self.doc, self.module)
            self.assertFalse(result["passed"], result)
            row = next(
                row for row in result["part_paths"] if row["part"] == "ServoDriveBridge"
            )
            self.assertFalse(row["passed"], row)
        finally:
            frame.Shape = original
            self.doc.recompute()


if __name__ == "__main__":
    unittest.main()
