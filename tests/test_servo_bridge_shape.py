"""Opposed shared clamps, clearanced U guide and ordered shaft-aware bench service."""

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

    def test_two_clamp_faces_and_central_seat_are_required_without_extra_pairs(self):
        result = self.joint()
        self.assertTrue(result["passed"], result)
        contacts = {row["interface"]: row for row in result["contacts"]}
        self.assertEqual(
            set(contacts),
            {
                "central_bulkhead_support",
                "shared_clamp_positive_x",
                "shared_clamp_negative_x",
            },
        )
        self.assertAlmostEqual(
            contacts["central_bulkhead_support"]["actual_contact_area_mm2"], 396
        )
        for name, y in (
            ("shared_clamp_positive_x", -5.25),
            ("shared_clamp_negative_x", 5.25),
        ):
            self.assertAlmostEqual(
                contacts[name]["actual_contact_area_mm2"], 206 - math.pi * 1.7**2
            )
            self.assertEqual(contacts[name]["plane_position_mm"], y)
        for side in ("Port", "Starboard"):
            for kind in ("Bolt", "Nut"):
                self.assertIsNone(self.doc.getObject("ServoBridge" + side + kind))
        self.assertEqual(result["wrap_fit"]["nominal_guide_side_clearance_mm"], 0.2)
        self.assertEqual(result["wrap_fit"]["clamp_axis_spacing_mm"], 34)

    def test_bridge_roof_and_both_guides_have_full_simple_stock(self):
        bridge = self.doc.ServoDriveBridge.Shape
        self.assertTrue(bridge.isValid())
        self.assertEqual(len(bridge.Solids), 1)
        roof = Part.makeBox(38, 26.4, 2, App.Vector(-19, -13.2, 12.5))
        self.assertLess(abs(roof.cut(bridge).Volume), 1e-7)
        for x in (-29, 19):
            removed_overhang = Part.makeBox(10, 26.4, 2, App.Vector(x, -13.2, 12.5))
            self.assertLess(abs(removed_overhang.common(bridge).Volume), 1e-7)
        for sign in (1, -1):
            guide = self.opposite(
                Part.makeBox(18, 2, 6.5, App.Vector(-9, 11.2, 8)), sign
            )
            gap = self.opposite(Part.makeBox(18, 0.2, 4.5, App.Vector(-9, 11, 8)), sign)
            with self.subTest(side=sign):
                self.assertLess(abs(guide.cut(bridge).Volume), 1e-7)
                self.assertLess(abs(gap.common(bridge).Volume), 1e-7)

    def test_both_heads_compress_complete_cheek_and_frame_lands(self):
        for sign in (1, -1):
            for name, y, thickness in (
                ("ServoDriveBridge", -7.75, 2.5),
                ("PropulsionFixedFrame", -5.25, 4),
            ):
                stock = Part.makeCylinder(
                    3, thickness, App.Vector(17, y, 7), App.Vector(0, 1, 0)
                ).cut(
                    Part.makeCylinder(
                        1.7,
                        thickness + 0.2,
                        App.Vector(17, y - 0.1, 7),
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
        for name, y in (("ServoDriveBridge", -7.75), ("PropulsionFixedFrame", -5.25)):
            obj = self.doc.getObject(name)
            original = obj.Shape.copy()
            for sign in (1, -1):
                try:
                    loss = self.opposite(
                        Part.makeBox(1, 0.5, 0.3, App.Vector(16.5, y, 9.2)), sign
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
                Part.makeBox(18, 22, 0.2, App.Vector(-9, -11, 12.4))
            )
            self.doc.recompute()
            result = self.joint()
            self.assertFalse(result["passed"], result)
            self.assertTrue(result["wrap_fit"]["passed"], result)
            contacts = {row["interface"]: row for row in result["contacts"]}
            self.assertAlmostEqual(
                contacts["central_bulkhead_support"]["actual_contact_area_mm2"], 0
            )
            self.assertTrue(contacts["shared_clamp_positive_x"]["passed"])
            self.assertTrue(contacts["shared_clamp_negative_x"]["passed"])
        finally:
            frame.Shape = original
            self.doc.recompute()

    def test_each_guide_is_required_and_its_clearance_cannot_be_filled(self):
        bridge = self.doc.ServoDriveBridge
        original = bridge.Shape.copy()
        for sign in (1, -1):
            for kind, size, origin in (
                ("missing", (2, 0.4, 2), (-1, 11.2, 9)),
                ("tight", (2, 0.2, 2), (-1, 11, 9)),
            ):
                try:
                    change = self.opposite(
                        Part.makeBox(*size, App.Vector(*origin)), sign
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
                    Part.makeBox(1, 0.2, 0.5, App.Vector(25, -5.35, 10)), sign
                )
                frame.Shape = original.cut(loss)
                self.doc.recompute()
                result = self.joint()
                self.assertFalse(result["passed"], result)
                name = (
                    "shared_clamp_positive_x" if sign > 0 else "shared_clamp_negative_x"
                )
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
        frame_seat = Part.makeBox(18, 22, 4.5, App.Vector(-9, -11, 8))
        self.assertLess(abs(frame_seat.common(envelope).Volume), 1e-7)

    def test_ordered_service_keeps_shifted_driven_shafts_as_obstacles(self):
        from gondola.validation.servo_module import servo_module_service_check

        result = servo_module_service_check(self.doc, self.module)
        self.assertTrue(result["passed"], result)
        self.assertEqual(
            result["removed_output_gears"], ["PortOutputGear", "StarboardOutputGear"]
        )
        self.assertEqual(result["released_fasteners"], [])
        self.assertIn("both shared M3x12", result["prerequisites"])
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
