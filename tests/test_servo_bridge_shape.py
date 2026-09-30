"""Shared keyed clamp: positive location, broad support and ordered bench service."""

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

        cls.doc = App.newDocument("SharedKeyedServoBridge")
        cls.module = propulsion.build_propulsion_module(cls.doc)

    @classmethod
    def tearDownClass(cls):
        App.closeDocument(cls.doc.Name)

    def joint(self):
        from gondola.validation.servo_module import bridge_joint_check

        return bridge_joint_check(self.doc, self.module)

    def test_keyed_clamp_preserves_full_central_support_without_extra_pairs(self):
        result = self.joint()
        self.assertTrue(result["passed"], result)
        contacts = {row["interface"]: row for row in result["contacts"]}
        self.assertEqual(
            set(contacts), {"central_bulkhead_support", "shared_clamp_vertical_face"}
        )
        self.assertAlmostEqual(
            contacts["central_bulkhead_support"]["actual_contact_area_mm2"], 396
        )
        self.assertAlmostEqual(
            contacts["shared_clamp_vertical_face"]["actual_contact_area_mm2"],
            18 * 10.3 - 5.4 * 5.9 - 3.141592653589793 * 1.7**2,
        )
        self.assertEqual(
            contacts["central_bulkhead_support"]["plane_position_mm"], 12.5
        )
        self.assertEqual(
            contacts["shared_clamp_vertical_face"]["plane_position_mm"], -5.25
        )
        for side in ("Port", "Starboard"):
            for kind in ("Bolt", "Nut"):
                self.assertIsNone(self.doc.getObject("ServoBridge" + side + kind))
        self.assertEqual(result["key_fit"]["nominal_side_clearance_mm"], 0.2)
        self.assertEqual(result["key_fit"]["nominal_depth_clearance_mm"], 0.2)
        self.assertEqual(result["key_fit"]["remaining_cheek_skin_mm"], 1.8)

    def test_simple_bridge_has_no_outer_arms_and_retains_a_broad_cheek_root(self):
        bridge = self.doc.ServoDriveBridge.Shape
        self.assertTrue(bridge.isValid())
        self.assertEqual(len(bridge.Solids), 1)
        for y in (-30, 11):
            opening = Part.makeBox(60, 19, 12, App.Vector(-30, y, 2))
            self.assertLess(abs(bridge.common(opening).Volume), 1e-7)
        roof = Part.makeBox(18, 22, 2, App.Vector(9, -11, 12.5))
        self.assertLess(abs(roof.cut(bridge).Volume), 1e-7)
        skin = Part.makeBox(5.4, 1.8, 1, App.Vector(19.8, -9.75, 6))
        self.assertLess(abs(skin.cut(bridge).Volume), 1e-7)
        # Independently bound every recess rim, including the formerly thin
        # outer and bottom lips; the 2.5 mm locating boss is not a free wall.
        for name, size, origin in (
            ("back", (5.4, 1.8, 5.9), (19.8, -9.75, 3.8)),
            ("right", (1.8, 4.5, 5.9), (25.2, -9.75, 3.8)),
            ("bottom", (5.4, 4.5, 1.6), (19.8, -9.75, 2.2)),
            ("top", (5.4, 4.5, 2.8), (19.8, -9.75, 9.7)),
            ("left", (1.6, 4.5, 5.9), (18.2, -9.75, 3.8)),
        ):
            with self.subTest(recess_stock=name):
                stock = Part.makeBox(*size, App.Vector(*origin))
                self.assertLess(abs(stock.cut(bridge).Volume), 1e-7)

    def test_head_load_passes_through_solid_cheek_and_frame_without_a_pocket_gap(self):
        # Literal design head envelope and screw-bore radius, independent of
        # the pocket builder: neither printed layer may bridge an internal void.
        for name, first_y, thickness in (
            ("ServoDriveBridge", -7.75, 2.5),
            ("PropulsionFixedFrame", -5.25, 4.0),
        ):
            with self.subTest(part=name):
                compression_land = Part.makeCylinder(
                    3.0, thickness, App.Vector(15, first_y, 7), App.Vector(0, 1, 0)
                ).cut(
                    Part.makeCylinder(
                        1.7,
                        thickness + 0.2,
                        App.Vector(15, first_y - 0.1, 7),
                        App.Vector(0, 1, 0),
                    )
                )
                self.assertLess(
                    abs(compression_land.cut(self.doc.getObject(name).Shape).Volume),
                    1e-7,
                )

    def test_missing_central_seat_is_rejected_despite_intact_key_and_clamp_face(self):
        frame = self.doc.PropulsionFixedFrame
        original = frame.Shape.copy()
        try:
            frame.Shape = original.cut(
                Part.makeBox(18, 22, 0.2, App.Vector(-9, -11, 12.4))
            )
            self.doc.recompute()
            result = self.joint()
            self.assertFalse(result["passed"], result)
            self.assertTrue(result["key_fit"]["passed"], result)
            contacts = {row["interface"]: row for row in result["contacts"]}
            self.assertAlmostEqual(
                contacts["central_bulkhead_support"]["actual_contact_area_mm2"], 0
            )
            self.assertTrue(contacts["shared_clamp_vertical_face"]["passed"])
        finally:
            frame.Shape = original
            self.doc.recompute()

    def test_small_contact_loss_is_rejected_instead_of_masked_by_other_faces(self):
        frame = self.doc.PropulsionFixedFrame
        original = frame.Shape.copy()
        for name, size, point, lost_area in (
            ("central_bulkhead_support", (2, 2, 0.2), (-7, -7, 12.4), 4),
            ("shared_clamp_vertical_face", (1, 0.2, 0.5), (24, -5.35, 10), 0.5),
        ):
            with self.subTest(contact=name):
                try:
                    frame.Shape = original.cut(Part.makeBox(*size, App.Vector(*point)))
                    self.doc.recompute()
                    result = self.joint()
                    self.assertFalse(result["passed"], result)
                    row = next(
                        row for row in result["contacts"] if row["interface"] == name
                    )
                    self.assertAlmostEqual(
                        row["required_contact_area_mm2"]
                        - row["actual_contact_area_mm2"],
                        lost_area,
                    )
                finally:
                    frame.Shape = original
                    self.doc.recompute()

    def test_missing_frame_key_cannot_pass_on_seating_and_clamp_contact_alone(self):
        frame = self.doc.PropulsionFixedFrame
        original = frame.Shape.copy()
        try:
            frame.Shape = original.cut(
                Part.makeBox(5, 2.5, 5.5, App.Vector(20, -7.75, 4))
            )
            self.doc.recompute()
            result = self.joint()
            self.assertFalse(result["passed"], result)
            self.assertGreater(result["key_fit"]["missing_key_mm3"], 30)
            self.assertTrue(all(row["passed"] for row in result["contacts"]), result)
        finally:
            frame.Shape = original
            self.doc.recompute()

    def test_each_recess_wall_and_skin_is_required_independently(self):
        bridge = self.doc.ServoDriveBridge
        original = bridge.Shape.copy()
        for name, size, point in (
            ("left", (0.4, 1, 2), (19.4, -7.85, 5)),
            ("right", (0.4, 1, 2), (25.2, -7.85, 5)),
            ("lower", (2, 1, 0.4), (20, -7.85, 3.4)),
            ("upper", (2, 1, 0.4), (20, -7.85, 9.7)),
            ("skin", (2, 0.4, 2), (20, -8.35, 5)),
        ):
            with self.subTest(missing=name):
                try:
                    bridge.Shape = original.cut(Part.makeBox(*size, App.Vector(*point)))
                    self.doc.recompute()
                    result = self.joint()
                    self.assertFalse(result["passed"], result)
                    self.assertGreater(
                        result["key_fit"]["missing_pocket_walls_mm3"], 0.5
                    )
                finally:
                    bridge.Shape = original
                    self.doc.recompute()

    def test_over_tight_and_over_large_key_recesses_are_rejected(self):
        bridge = self.doc.ServoDriveBridge
        original = bridge.Shape.copy()
        for name, modified, evidence in (
            (
                "tight",
                original.fuse(Part.makeBox(1, 1, 2, App.Vector(21, -7.7, 5))),
                "key_in_pocket_interference_mm3",
            ),
            (
                "loose",
                original.cut(Part.makeBox(5.8, 2.9, 6.3, App.Vector(19.6, -8.15, 3.6))),
                "missing_pocket_walls_mm3",
            ),
        ):
            with self.subTest(fit=name):
                try:
                    bridge.Shape = modified
                    self.doc.recompute()
                    result = self.joint()
                    self.assertFalse(result["passed"], result)
                    self.assertGreater(result["key_fit"][evidence], 0.5)
                finally:
                    bridge.Shape = original
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

    def test_service_envelope_retains_open_recess_and_contains_the_actual_bridge(self):
        from gondola.parts import servo_bridge

        envelope = servo_bridge.bridge_blank()
        self.assertLess(abs(self.doc.ServoDriveBridge.Shape.cut(envelope).Volume), 1e-7)
        key = Part.makeBox(5, 2.5, 5.5, App.Vector(20, -7.75, 4))
        self.assertLess(abs(key.common(envelope).Volume), 1e-7)

    def test_ordered_service_disengages_key_before_lift_and_lateral_withdrawal(self):
        from gondola.validation.servo_module import servo_module_service_check

        result = servo_module_service_check(self.doc, self.module)
        self.assertTrue(result["passed"], result)
        self.assertEqual(
            result["removed_output_gears"], ["PortOutputGear", "StarboardOutputGear"]
        )
        self.assertEqual(result["released_fasteners"], [])
        self.assertIn("shared M3x12", result["prerequisites"])
        for row in result["part_paths"]:
            self.assertEqual(
                row["waypoints_mm"],
                [(0, 0, 0), (0, -2.7, 0), (0, -2.7, 0.5), (80, -2.7, 0.5)],
            )

    def test_continuous_service_detects_midpath_obstacle_with_clear_endpoints(self):
        from gondola.validation.servo_module import servo_module_service_check

        frame = self.doc.PropulsionFixedFrame
        original = frame.Shape.copy()
        obstacle = Part.makeBox(1, 1, 1, App.Vector(40, 0, 13.5))
        bridge = self.doc.ServoDriveBridge.Shape.copy()
        self.assertLess(abs(bridge.common(obstacle).Volume), 1e-7)
        bridge.translate(App.Vector(80, -2.7, 0.5))
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
