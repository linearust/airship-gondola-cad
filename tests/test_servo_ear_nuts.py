"""Shallow servo-ear capture and screw-first removal with the horn still fitted."""

import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class ServoEarNutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.parts import propulsion

        cls.doc = App.newDocument("ShallowServoEarNuts")
        cls.module = propulsion.build_propulsion_module(cls.doc)

    @classmethod
    def tearDownClass(cls):
        App.closeDocument(cls.doc.Name)

    def test_four_nuts_seat_in_shallow_pockets_with_complete_wall_floors(self):
        from gondola.validation.servo_ear_nuts import servo_ear_nut_check

        for prefix in ("Port", "Starboard"):
            result = servo_ear_nut_check(self.doc, prefix)
            self.assertTrue(result["passed"], result)
            self.assertFalse(result["nut_axially_captive"])
            for row in result["cases"]:
                self.assertEqual(row["capture_depth_mm"], 0.5)
                self.assertEqual(row["retained_wall_floor_mm"], 4.5)
                self.assertGreater(row["required_bearing_area_mm2"], 3)
                sizes = row["nut_size_range"]
                self.assertEqual(sizes["minimum_nut_af_height_mm"], [3.02, 1.05])
                self.assertEqual(sizes["maximum_nut_af_height_mm"], [3.2, 1.3])
                self.assertEqual(len(sizes["maximum_nut_free_insertion"]), 9)
                self.assertEqual(len(sizes["minimum_nut_rotation_stops"]), 18)

    def test_minimum_standard_nut_cannot_be_ignored_when_nominal_nut_still_stops(self):
        from gondola.validation.servo_ear_nuts import _hex, servo_ear_nut_check

        bridge = self.doc.ServoDriveBridge
        original = bridge.Shape.copy()
        mount = self.doc.PortServoMount.Placement.Base
        # AF3.5 still blocks a nominal AF3.2 nut, but clears every orientation
        # of a centred minimum AF3.02 nut (corner diameter approximately3.487).
        enlarged = _hex(3.5, -2.5, 0.5, 7)
        enlarged.translate(mount)
        try:
            bridge.Shape = original.cut(enlarged)
            result = servo_ear_nut_check(self.doc, "Port")
            self.assertFalse(result["passed"])
            upper = result["cases"][1]
            self.assertGreater(upper["nut_30deg_rotation_block_mm3"], 0.01)
            self.assertTrue(
                all(
                    row["passed"]
                    for row in upper["nut_size_range"]["maximum_nut_free_insertion"]
                )
            )
            centred = upper["nut_size_range"]["minimum_nut_rotation_stops"][:2]
            self.assertTrue(all(not row["passed"] for row in centred))
        finally:
            bridge.Shape = original

    def test_maximum_nut_requires_a_clear_approach_not_only_clear_installed_shape(self):
        from gondola.validation.servo_ear_nuts import servo_ear_nut_check

        bridge = self.doc.ServoDriveBridge
        original = bridge.Shape.copy()
        mount = self.doc.PortServoMount.Placement.Base
        obstruction = Part.makeBox(0.2, 0.2, 0.2, mount + App.Vector(1.3, -4, 7.3))
        try:
            bridge.Shape = original.fuse(obstruction)
            result = servo_ear_nut_check(self.doc, "Port")
            self.assertFalse(result["passed"])
            upper = result["cases"][1]
            self.assertAlmostEqual(upper["nut_print_intersection_mm3"], 0)
            fit = upper["nut_size_range"]["maximum_nut_free_insertion"][0]
            self.assertGreater(fit["maximum_nut_insertion_removal_overlap_mm3"], 0.001)
        finally:
            bridge.Shape = original

    def test_missing_internal_floor_fails_even_with_the_nut_seat_intact(self):
        from gondola.validation.servo_ear_nuts import servo_ear_nut_check

        bridge = self.doc.ServoDriveBridge
        original = bridge.Shape.copy()
        mount = self.doc.PortServoMount.Placement.Base
        defect = Part.makeBox(0.2, 0.3, 0.2, mount + App.Vector(1.3, 0, 6.9))
        self.assertAlmostEqual(original.common(defect).Volume, 0.012)
        try:
            bridge.Shape = original.cut(defect)
            result = servo_ear_nut_check(self.doc, "Port")
            self.assertFalse(result["passed"])
            upper = result["cases"][1]
            self.assertAlmostEqual(upper["missing_seat_mm3"], 0)
            self.assertAlmostEqual(upper["missing_floor_mm3"], 0.012)
        finally:
            bridge.Shape = original

    def test_round_recess_cannot_replace_the_hex_rotation_stop(self):
        from gondola.validation.servo_ear_nuts import servo_ear_nut_check

        bridge = self.doc.ServoDriveBridge
        original = bridge.Shape.copy()
        mount = self.doc.PortServoMount.Placement.Base
        defect = Part.makeCylinder(
            2.3, 0.5, mount + App.Vector(0, -2.5, 7), App.Vector(0, 1, 0)
        )
        try:
            bridge.Shape = original.cut(defect)
            result = servo_ear_nut_check(self.doc, "Port")
            self.assertFalse(result["passed"])
            upper = result["cases"][1]
            self.assertAlmostEqual(upper["missing_floor_mm3"], 0)
            self.assertAlmostEqual(upper["nut_30deg_rotation_block_mm3"], 0)
        finally:
            bridge.Shape = original

    def test_nut_must_reach_the_recessed_bearing_plane(self):
        from gondola.validation.servo_ear_nuts import servo_ear_nut_check

        nut = self.doc.StarboardServoEarUpperNut
        original = nut.Shape.copy()
        try:
            moved = original.copy()
            moved.translate(App.Vector(0, 0.1, 0))
            nut.Shape = moved
            result = servo_ear_nut_check(self.doc, "Starboard")
            self.assertFalse(result["passed"])
            self.assertGreater(result["cases"][1]["nut_shape_difference_mm3"], 0.1)
        finally:
            nut.Shape = original

    def test_thin_outer_pocket_rim_is_rejected(self):
        from gondola.validation.servo_ear_nuts import servo_ear_nut_check

        bridge = self.doc.ServoDriveBridge
        original = bridge.Shape.copy()
        mount = self.doc.PortServoMount.Placement.Base
        defect = Part.makeBox(3.4, 0.5, 0.2, mount + App.Vector(-1.7, -2.5, 10))
        self.assertAlmostEqual(original.common(defect).Volume, 0.34)
        try:
            bridge.Shape = original.cut(defect)
            result = servo_ear_nut_check(self.doc, "Port")
            self.assertFalse(result["passed"])
            upper = result["cases"][1]
            self.assertAlmostEqual(upper["missing_outer_rim_mm3"], 0.34)
            self.assertAlmostEqual(upper["missing_floor_mm3"], 0)
        finally:
            bridge.Shape = original

    def test_both_pairs_release_screw_first_with_the_complete_horn_unit_retained(self):
        from gondola.validation.propulsion_service import (
            fastener_service_check,
            module_service_shapes,
            retained_obstacles,
            servo_bench_members,
        )

        shapes, missing = module_service_shapes(self.doc, self.module)
        self.assertEqual(missing, [])
        members = servo_bench_members(self.doc, shapes)
        for prefix in ("Port", "Starboard"):
            removed = {prefix + "DriverGear", prefix + "InputShaft"}
            for side in ("Lower", "Upper"):
                name = prefix + "ServoEar" + side
                pair = {name + "Bolt", name + "Nut"}
                obstacles = retained_obstacles(shapes, removed | pair, members=members)
                result = fastener_service_check(
                    shapes[name + "Bolt"],
                    shapes[name + "Nut"],
                    obstacles,
                    thread_diameter=1.6,
                    guided_nut=True,
                    capture_depth_mm=0.5,
                )
                self.assertTrue(result["passed"], (name, result))
                self.assertTrue(result["screw_first_with_nut_held_in_guides"])
                self.assertFalse(result["bolt_retained_in_servo_unit"])
                self.assertAlmostEqual(
                    result["minimum_nut_lift_before_lateral_mm"], 0.7
                )
                self.assertAlmostEqual(result["bolt_withdrawal_travel_mm"], 8.2)
                self.assertIn(prefix + "HornGearAdapter", obstacles)
                removed.update(pair)


if __name__ == "__main__":
    unittest.main()
