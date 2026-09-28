"""Open connector plate, broad load paths and installed fastener regressions."""

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

        cls.doc = App.newDocument("OpenServoConnectorPlate")
        cls.module = propulsion.build_propulsion_module(cls.doc)

    @classmethod
    def tearDownClass(cls):
        App.closeDocument(cls.doc.Name)

    def check_mount(self, prefix, bridge=None):
        from gondola.cad import world_shape
        from gondola.validation.propulsion import clamp_fastener_check

        if bridge is None:
            bridge = world_shape(self.doc.ServoDriveBridge)
        clamp = Part.makeCompound([world_shape(self.doc.PropulsionFixedFrame), bridge])
        return clamp_fastener_check(
            clamp,
            world_shape(self.doc.getObject("ServoBridge" + prefix + "Bolt")),
            world_shape(self.doc.getObject("ServoBridge" + prefix + "Nut")),
        )

    def test_flat_mounting_arms_retain_existing_m2x8_clamping_stack(self):
        from gondola.parts import servo_bridge

        self.assertEqual(servo_bridge.MOUNT_GRIP, 5)
        self.assertEqual(servo_bridge.MOUNT_BOLT_SEAT_Z, 13.4)
        self.assertEqual(servo_bridge.NUT_SEAT_Z, 8.4)
        for prefix in ("Port", "Starboard"):
            with self.subTest(side=prefix):
                bolt = self.doc.getObject("ServoBridge" + prefix + "Bolt")
                self.assertEqual(bolt.HardwareSKU, "M2X8_BUTTON_HEAD")
                result = self.check_mount(prefix)
                self.assertTrue(result["passed"], result)

    def test_unused_side_regions_are_open_to_the_plate_edges(self):
        from gondola.parts import servo_bridge

        bridge = self.doc.ServoDriveBridge.Shape
        # Two large open-edge regions on each side expose the underlying
        # frame without retaining a thin outer ring around a viewing hole.
        openings = (
            Part.makeBox(17.3, 15, 2, App.Vector(-13.4, 11, 11.4)),
            Part.makeBox(6.1, 34, 2, App.Vector(-19.5, -8, 11.4)),
        )
        for opening in openings:
            for side in (opening, servo_bridge.opposite(opening)):
                self.assertLess(bridge.common(side).Volume, 1e-7)
        self.assertTrue(bridge.isValid())
        self.assertEqual(len(bridge.Solids), 1)

    def test_each_mounting_arm_has_a_broad_continuous_connection(self):
        from gondola.parts import servo_bridge

        bridge = self.doc.ServoDriveBridge.Shape
        # The full 9.5 mm attachment breadth continues from the central stock
        # into each mounting arm; its through bore is farther outward.
        link = Part.makeBox(9.5, 6, 2, App.Vector(3.9, 8, 11.4))
        for side in (link, servo_bridge.opposite(link)):
            self.assertLess(side.cut(bridge).Volume, 1e-7)

    def test_a_raised_screw_seat_cannot_pass_the_installed_stack_check(self):
        from gondola.cad import world_shape
        from gondola.parts import servo_bridge

        bridge = world_shape(self.doc.ServoDriveBridge)
        origin = App.Vector(
            servo_bridge.BOLT_X,
            servo_bridge.BOLT_Y,
            servo_bridge.MOUNT_BOLT_SEAT_Z,
        )
        fill = Part.makeCylinder(3, 2.7, origin).cut(
            Part.makeCylinder(1.1, 2.7, origin)
        )
        result = self.check_mount("Port", bridge.fuse(fill))
        self.assertFalse(result["passed"], result)
        self.assertGreater(result["fastener_clamp_overlap_mm3"], 1)

    def test_underside_and_screw_bearing_annuli_share_one_flat_plate(self):
        bridge = self.doc.ServoDriveBridge.Shape
        self.assertAlmostEqual(bridge.BoundBox.ZMin, 11.4)
        for sign in (-1, 1):
            origin = App.Vector(sign * 14.5, sign * 18, 11.4)
            annulus = Part.makeCylinder(3, 2, origin).cut(
                Part.makeCylinder(1.1, 2, origin)
            )
            self.assertLess(annulus.cut(bridge).Volume, 1e-7)

    def test_each_coplanar_support_and_unilateral_datum_has_complete_contact(self):
        from gondola.validation.servo_module import bridge_joint_check

        result = bridge_joint_check(self.doc, self.module)
        self.assertTrue(result["passed"], result)
        contacts = {row["interface"]: row for row in result["contacts"]}
        for name, area in (
            ("positive_outer_seat", 191.1986728891564),
            ("negative_outer_seat", 191.1986728891564),
            ("central_bulkhead_support", 396),
        ):
            with self.subTest(contact=name):
                row = contacts[name]
                self.assertEqual(row["plane_position_mm"], 11.4)
                self.assertAlmostEqual(row["actual_contact_area_mm2"], area)
                self.assertIsNotNone(row["support_region_xy_mm"])
        self.assertAlmostEqual(
            contacts["outside_x_datum"]["actual_contact_area_mm2"], 6
        )
        self.assertAlmostEqual(
            contacts["outside_y_datum"]["actual_contact_area_mm2"], 31.2
        )
        self.assertEqual(contacts["outside_y_datum"]["plane_position_mm"], -26)

    def test_other_coplanar_contacts_cannot_mask_a_missing_support(self):
        from gondola.validation.servo_module import bridge_joint_check

        frame = self.doc.PropulsionFixedFrame
        original = frame.Shape.copy()
        for name, origin, width, length in (
            ("positive_outer_seat", (3.9, 13.5, 11.3), 15.6, 12.5),
            ("negative_outer_seat", (-19.5, -26, 11.3), 15.6, 12.5),
            ("central_bulkhead_support", (-9, -11, 11.3), 18, 22),
        ):
            with self.subTest(missing=name):
                try:
                    frame.Shape = original.cut(
                        Part.makeBox(width, length, 0.2, App.Vector(*origin))
                    )
                    self.doc.recompute()
                    result = bridge_joint_check(self.doc, self.module)
                    self.assertFalse(result["passed"], result)
                    contacts = {row["interface"]: row for row in result["contacts"]}
                    self.assertAlmostEqual(contacts[name]["actual_contact_area_mm2"], 0)
                    self.assertTrue(
                        all(
                            row["passed"]
                            for key, row in contacts.items()
                            if key != name
                        ),
                        result,
                    )
                finally:
                    frame.Shape = original
                    self.doc.recompute()

    def test_support_contact_gaps_are_rejected_without_losing_the_whole_seat(self):
        from gondola.validation.servo_module import bridge_joint_check

        frame = self.doc.PropulsionFixedFrame
        original = frame.Shape.copy()
        for name, point in (
            ("positive_outer_seat", (6, 15, 11.3)),
            ("negative_outer_seat", (-8, -17, 11.3)),
            ("central_bulkhead_support", (-2, -2, 11.3)),
        ):
            with self.subTest(contact=name):
                try:
                    frame.Shape = original.cut(
                        Part.makeBox(2, 2, 0.2, App.Vector(*point))
                    )
                    self.doc.recompute()
                    result = bridge_joint_check(self.doc, self.module)
                    self.assertFalse(result["passed"], result)
                    row = next(
                        row for row in result["contacts"] if row["interface"] == name
                    )
                    self.assertAlmostEqual(
                        row["required_contact_area_mm2"]
                        - row["actual_contact_area_mm2"],
                        4,
                    )
                finally:
                    frame.Shape = original
                    self.doc.recompute()

    def test_each_unilateral_datum_is_required_independently(self):
        from gondola.validation.servo_module import bridge_joint_check

        frame = self.doc.PropulsionFixedFrame
        original = frame.Shape.copy()
        for name, size, point in (
            ("outside_x_datum", (2, 3, 5), (-21.5, -24, 8.4)),
            ("outside_y_datum", (15.6, 1.5, 5), (-19.5, -27.5, 8.4)),
        ):
            with self.subTest(datum=name):
                try:
                    frame.Shape = original.cut(Part.makeBox(*size, App.Vector(*point)))
                    self.doc.recompute()
                    result = bridge_joint_check(self.doc, self.module)
                    self.assertFalse(result["passed"], result)
                    contacts = {row["interface"]: row for row in result["contacts"]}
                    self.assertAlmostEqual(contacts[name]["actual_contact_area_mm2"], 0)
                    self.assertTrue(
                        all(
                            row["passed"]
                            for key, row in contacts.items()
                            if key != name
                        ),
                        result,
                    )
                finally:
                    frame.Shape = original
                    self.doc.recompute()

    def test_changed_parts_clear_every_other_installed_module_part(self):
        from gondola.cad import world_shape

        shapes = {
            obj.Name: world_shape(obj)
            for group in ("printed", "hardware", "references")
            for obj in self.module[group]
        }
        changed = {"PropulsionFixedFrame", "ServoDriveBridge"} | {
            "ServoBridge" + prefix + kind
            for prefix in ("Port", "Starboard")
            for kind in ("Bolt", "Nut")
        }
        for name in changed:
            for other, shape in shapes.items():
                if name != other:
                    with self.subTest(part=name, obstacle=other):
                        self.assertLess(abs(shapes[name].common(shape).Volume), 1e-7)

    def test_mount_fasteners_and_module_keep_the_original_ordered_service_path(self):
        from gondola.validation.servo_module import servo_module_service_check

        result = servo_module_service_check(self.doc, self.module)
        self.assertTrue(result["passed"], result)
        self.assertEqual(
            result["removed_output_gears"], ["PortOutputGear", "StarboardOutputGear"]
        )
        for row in result["part_paths"]:
            self.assertEqual(
                row["waypoints_mm"], [(0, 0, 0), (0, 0, 0.5), (80, 0, 0.5)]
            )
        self.assertTrue(all(row["passed"] for row in result["mount_fastener_release"]))


if __name__ == "__main__":
    unittest.main()
