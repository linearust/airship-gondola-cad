"""Saved geometry must support each input gear without hiding fit defects."""

import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class ExternalInputSupportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.parts.propulsion import build_propulsion_module

        cls.doc = App.newDocument("ExternalInputSupports")
        cls.module = build_propulsion_module(cls.doc)

    @classmethod
    def tearDownClass(cls):
        App.closeDocument(cls.doc.Name)

    def check(self, side="Port"):
        from gondola.validation.propulsion import input_bearing_support_check

        return input_bearing_support_check(self.doc, side)

    def test_both_sides_have_supported_round_journals_and_seated_outer_joints(self):
        for side in ("Port", "Starboard"):
            result = self.check(side)
            self.assertTrue(result["passed"], result)
            self.assertEqual(result["capture"]["bearing_centre_x_mm"], 16)
            self.assertEqual(result["capture"]["bearing_centre_y_mm"], 33)
            self.assertTrue(result["fixed_native_parent"])
            self.assertEqual(result["capture"]["missing_complete_round_journal_mm3"], 0)

    def test_two_cap_pairs_are_aligned_and_deleted_middle_pair_is_absent(self):
        for side, sign in (("Port", 1), ("Starboard", -1)):
            for suffix, x in (("Negative", -5.5), ("Input", 23)):
                bolt = self.doc.getObject(side + "BearingCap" + suffix + "Bolt")
                self.assertAlmostEqual(bolt.Shape.BoundBox.Center.x, sign * x)
                self.assertAlmostEqual(bolt.Shape.BoundBox.Center.y, sign * 33)
            for kind in ("Bolt", "Nut"):
                self.assertIsNone(
                    self.doc.getObject(side + "BearingCapPositive" + kind)
                )

    def test_missing_or_moving_bearing_cannot_claim_support(self):
        bearing = self.doc.PortInputBearing
        parent = bearing.getParentGeoFeatureGroup()
        try:
            self.doc.PortInputDrive.addObject(bearing)
            self.doc.recompute()
            self.assertFalse(self.check()["passed"])
        finally:
            parent.addObject(bearing)
            self.doc.recompute()

    def test_whole_length_flat_or_undersize_journal_is_rejected(self):
        shaft = self.doc.PortInputShaft
        original = shaft.Shape.copy()
        from gondola.parts import servo_coupling as coupling

        try:
            bad = coupling.shaft_frame_shape(coupling._d_section(7.1, 35))
            bad.translate(App.Vector(0, 7.4, 0))
            shaft.Shape = bad
            self.doc.recompute()
            result = self.check()
            self.assertFalse(result["passed"])
            self.assertGreater(
                result["capture"]["missing_complete_round_journal_mm3"], 0
            )
        finally:
            shaft.Shape = original
            self.doc.recompute()

    def test_shifted_bearing_or_unseated_outer_bolt_is_rejected(self):
        for obj in (self.doc.PortInputBearing, self.doc.PortBearingCapInputBolt):
            original = App.Placement(obj.Placement)
            try:
                obj.Placement.Base.z += 0.2
                self.doc.recompute()
                self.assertFalse(self.check()["passed"])
            finally:
                obj.Placement = original
                self.doc.recompute()

    def test_removing_load_web_or_cap_land_is_rejected(self):
        for obj, cut in (
            (
                self.doc.PropulsionFixedFrame,
                Part.makeBox(1, 2, 4, App.Vector(10, 32, 42)),
            ),
            (self.doc.PortBearingCap, Part.makeBox(2, 2, 0.5, App.Vector(20, 30, 50))),
        ):
            original = obj.Shape.copy()
            try:
                obj.Shape = original.cut(cut)
                self.doc.recompute()
                self.assertFalse(self.check()["passed"])
            finally:
                obj.Shape = original
                self.doc.recompute()

    def test_all_cap_nut_pockets_keep_one_point_five_mm_to_every_bearing_seat(self):
        from gondola.validation.bearing_capture import cap_nut_seat_ligament_check

        result = cap_nut_seat_ligament_check(self.doc.PropulsionFixedFrame.Shape)
        self.assertTrue(result["passed"], result)
        self.assertEqual(
            {row["cap_joint"] for row in result["nut_pockets"]},
            {"Negative", "Input"},
        )
        for row in result["nut_pockets"]:
            self.assertEqual(len(row["seat_distances_mm"]), 3)
            self.assertGreaterEqual(min(row["seat_distances_mm"]), 1.5)
            self.assertLess(row["missing_shortest_wall_stock_mm"], 1e-5)

    def test_enlarged_negative_nut_cavity_cannot_approach_a_bearing_seat(self):
        from gondola.validation.bearing_capture import cap_nut_seat_ligament_check

        intrusion = Part.makeBox(3, 5, 1.8, App.Vector(-4, 26.5, 45.7))
        result = cap_nut_seat_ligament_check(
            self.doc.PropulsionFixedFrame.Shape.cut(intrusion)
        )
        negative = next(
            row for row in result["nut_pockets"] if row["cap_joint"] == "Negative"
        )
        self.assertLess(negative["minimum_wall_mm"], 1.5)
        self.assertFalse(result["passed"], result)

    def test_removed_ligament_stock_fails_with_pocket_distance_unchanged(self):
        from gondola.validation.bearing_capture import cap_nut_seat_ligament_check

        frame = self.doc.PropulsionFixedFrame.Shape
        original = cap_nut_seat_ligament_check(frame)
        row = next(
            row for row in original["nut_pockets"] if row["cap_joint"] == "Negative"
        )
        start, end = [App.Vector(*point) for point in row["shortest_wall_segment_mm"]]
        result = cap_nut_seat_ligament_check(
            frame.cut(Part.makeSphere(0.1, (start + end) * 0.5))
        )
        changed = next(
            row for row in result["nut_pockets"] if row["cap_joint"] == "Negative"
        )
        self.assertAlmostEqual(
            changed["minimum_wall_mm"], row["minimum_wall_mm"], places=6
        )
        self.assertGreater(changed["missing_shortest_wall_stock_mm"], 0.19)
        self.assertFalse(result["passed"], result)
