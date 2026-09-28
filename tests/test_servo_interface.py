"""Only the exact servo spline envelope can contain intended horn overlap."""

import math
import unittest
from pathlib import Path

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires FreeCAD")
class ServoSplineInterfaceTests(unittest.TestCase):
    def setUp(self):
        self.axis = App.Vector(0, 1, 0)
        self.origin = App.Vector()
        self.case = Part.makeBox(7, 4, 20, App.Vector(-3.5, -4, -5))
        self.spline = Part.makeCylinder(1.95, 2.7, self.origin, self.axis)
        self.servo = self.case.fuse(self.spline).removeSplitter()
        path = (
            Path(__file__).resolve().parents[1] / "gondola/data/kst_x06_half_arm_1.step"
        )
        self.horn = Part.read(str(path))
        self.horn.rotate(App.Vector(), App.Vector(1, 0, 0), -90)
        # Rear at0.2 gives the sourced2.5mm tooth cavity inside the2.7mm spline.
        self.horn.translate(App.Vector(0, 1.7, 0))

    def test_oem_teeth_overlap_is_bounded_on_both_mirrored_and_rigidly_moved_sides(
        self,
    ):
        from gondola.validation.servo_interface import horn_spline_contact

        root = App.Placement(
            App.Vector(41, -17, 23), App.Rotation(App.Vector(1, 2, 3), 67)
        )
        for turn in (0, 180):
            for moved in (False, True):
                with self.subTest(side_turn=turn, moved_root=moved):
                    frame = App.Placement(
                        App.Vector(12, -3, 8), App.Rotation(App.Vector(0, 0, 1), turn)
                    )
                    if moved:
                        frame = root.multiply(frame)
                    horn, servo = self.horn.copy(), self.servo.copy()
                    horn.Placement = frame.multiply(horn.Placement)
                    servo.Placement = frame.multiply(servo.Placement)
                    before = (horn.Placement.copy(), servo.Placement.copy())
                    result = horn_spline_contact(
                        horn, servo, frame.Base, frame.Rotation.multVec(self.axis)
                    )
                    self.assertTrue(result["passed"], result)
                    self.assertGreater(result["neutral_intersection_mm3"], 0.1)
                    self.assertLess(result["forbidden_overlap_mm3"], 1e-7)
                    self.assertAlmostEqual(result["spline"]["length_mm"], 2.7)
                    self.assertTrue(horn.Placement.isSame(before[0], 1e-9))
                    self.assertTrue(servo.Placement.isSame(before[1], 1e-9))

    def test_missing_wrong_radius_length_or_axis_is_not_a_contact_exemption(self):
        from gondola.validation.servo_interface import sourced_spline_volume

        variants = (
            ("missing", self.case, self.origin, self.axis),
            (
                "wrong radius",
                self.case.fuse(Part.makeCylinder(2.0, 2.7, self.origin, self.axis)),
                self.origin,
                self.axis,
            ),
            (
                "wrong length",
                self.case.fuse(Part.makeCylinder(1.95, 3.1, self.origin, self.axis)),
                self.origin,
                self.axis,
            ),
            ("wrong axis direction", self.servo, self.origin, App.Vector(1, 0, 0)),
            ("wrong axis line", self.servo, App.Vector(0.1, 0, 0), self.axis),
        )
        for label, shape, origin, axis in variants:
            with self.subTest(label=label):
                volume, result = sourced_spline_volume(shape, origin, axis)
                self.assertIsNone(volume)
                self.assertFalse(result["passed"], result)

    def test_duplicate_complete_spline_faces_are_rejected(self):
        from gondola.validation.servo_interface import sourced_spline_volume

        neck = Part.makeCylinder(1, 1, App.Vector(0, 2.7, 0), self.axis)
        second = Part.makeCylinder(1.95, 2.7, App.Vector(0, 3.7, 0), self.axis)
        servo = self.servo.fuse(neck).fuse(second).removeSplitter()
        self.assertEqual(len(servo.Solids), 1)
        volume, result = sourced_spline_volume(servo, self.origin, self.axis)
        self.assertIsNone(volume)
        self.assertFalse(result["passed"])
        self.assertEqual(result["candidate_face_count"], 2)

    def test_partial_cylindrical_face_cannot_exempt_the_missing_half(self):
        from gondola.validation.servo_interface import sourced_spline_volume

        half = Part.makeCylinder(1.95, 2.7, self.origin, self.axis, 180)
        servo = self.case.fuse(half).removeSplitter()
        volume, result = sourced_spline_volume(servo, self.origin, self.axis)
        self.assertIsNone(volume)
        self.assertFalse(result["passed"])
        self.assertEqual(result["candidate_face_count"], 0)

    def test_hollow_spline_cannot_exempt_a_whole_cylinder(self):
        from gondola.validation.servo_interface import sourced_spline_volume

        bored = self.servo.cut(
            Part.makeCylinder(0.5, 2.7, self.origin, self.axis)
        ).removeSplitter()
        volume, result = sourced_spline_volume(bored, self.origin, self.axis)
        self.assertIsNone(volume)
        self.assertFalse(result["passed"])
        self.assertEqual(result["candidate_face_count"], 1)
        self.assertGreater(result["missing_servo_material_mm3"], 1)

    def test_case_lobe_outside_spline_is_not_hidden_by_allowed_tooth_overlap(self):
        from gondola.validation.servo_interface import horn_spline_contact

        lobe = Part.makeBox(1, 4, 1, App.Vector(8, -0.5, -0.5))
        # Join the distant lobe to the case without changing the spline face.
        link = Part.makeBox(6, 1, 1, App.Vector(3, -1, -0.5))
        servo = self.servo.fuse(link).fuse(lobe).removeSplitter()
        result = horn_spline_contact(self.horn, servo, self.origin, self.axis)
        self.assertTrue(result["spline"]["passed"], result)
        self.assertFalse(result["passed"], result)
        self.assertGreater(result["forbidden_overlap_mm3"], 0.1)

    def test_horn_extension_behind_spline_hits_case_and_is_rejected(self):
        from gondola.validation.servo_interface import horn_spline_contact

        extension = Part.makeBox(0.3, 1, 0.3, App.Vector(2.4, -0.3, -0.15))
        horn = self.horn.fuse(extension).removeSplitter()
        self.assertEqual(len(horn.Solids), 1)
        result = horn_spline_contact(horn, self.servo, self.origin, self.axis)
        self.assertFalse(result["passed"], result)
        self.assertGreater(result["forbidden_overlap_mm3"], 0.01)

    def test_invalid_inputs_fail_closed_without_zero_overlap_claim(self):
        from gondola.validation.servo_interface import horn_spline_contact

        for origin, axis in (
            (self.origin, App.Vector()),
            ((math.nan, 0, 0), self.axis),
            (self.origin, (0, math.inf, 0)),
        ):
            with self.subTest(origin=origin, axis=axis):
                result = horn_spline_contact(self.horn, self.servo, origin, axis)
                self.assertFalse(result["passed"], result)
                self.assertIsNone(result["neutral_intersection_mm3"])
                self.assertIsNone(result["forbidden_overlap_mm3"])
        result = horn_spline_contact(Part.Shape(), self.servo, self.origin, self.axis)
        self.assertFalse(result["passed"], result)


@unittest.skipIf(App is None, "Requires FreeCAD")
class AssemblySplineInterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.parts import propulsion

        cls.doc = App.newDocument("AssemblySplineInterface")
        cls.module = propulsion.build_propulsion_module(cls.doc)
        root = cls.doc.addObject("App::Part", "MovedRoot")
        root.addObject(cls.module["group"])
        root.Placement = App.Placement(
            App.Vector(41, -17, 180), App.Rotation(App.Vector(1, 2, 3), 67)
        )
        cls.doc.recompute()

    @classmethod
    def tearDownClass(cls):
        App.closeDocument(cls.doc.Name)

    def pair(self, prefix):
        from gondola.cad import world_shape

        objects = [
            self.doc.getObject(prefix + suffix) for suffix in ("ServoHorn", "Servo")
        ]
        return objects, {obj.Name: world_shape(obj) for obj in objects}

    def pair_module(self, prefix, *extra_names):
        names = {prefix + "ServoHorn", prefix + "Servo", *extra_names}
        return {
            **self.module,
            **{
                category: [obj for obj in self.module[category] if obj.Name in names]
                for category in ("printed", "hardware", "references")
            },
        }

    def test_sampled_tilt_checks_bounded_contact_at_all_49_mirrored_poses(self):
        from gondola.validation.propulsion import tilt_clearance_check

        for prefix in ("Port", "Starboard"):
            pod = self.doc.getObject(prefix + "Pod")
            original = float(pod.Tilt)
            try:
                pod.Tilt = 23
                self.doc.recompute()
                result = tilt_clearance_check(self.doc, self.module, prefix)
                self.assertTrue(result["passed"], result)
                self.assertEqual(float(pod.Tilt), 23)
                self.assertEqual(
                    [row["output_angle_deg"] for row in result["poses"]],
                    [-180 + index * 7.5 for index in range(49)],
                )
                for row in result["poses"]:
                    with self.subTest(side=prefix, angle=row["output_angle_deg"]):
                        self.assertEqual(row["collisions"], [])
                        self.assertEqual(len(row["spline_contacts"]), 1)
                        contact = row["spline_contacts"][0]
                        self.assertTrue(contact["passed"], contact)
                        self.assertGreater(contact["neutral_intersection_mm3"], 0.1)
                        self.assertLess(contact["forbidden_overlap_mm3"], 1e-7)
            finally:
                pod.Tilt = original
                self.doc.recompute()

    def test_sampled_tilt_retains_case_and_horn_protrusion_collisions(self):
        from gondola.cad import placed_shape
        from gondola.validation.horn_coupling import coupling_frame
        from gondola.validation.propulsion import tilt_clearance_check

        for suffix, depth in (("ServoHorn", 1), ("Servo", 2.3)):
            obj = self.doc.getObject("Port" + suffix)
            original = obj.Shape.copy()
            try:
                local = original.copy()
                local.Placement = App.Placement()
                lobe = placed_shape(
                    Part.makeBox(0.3, depth, 0.3, App.Vector(2.4, -0.5, -0.15)),
                    obj.getGlobalPlacement()
                    .inverse()
                    .multiply(coupling_frame(self.doc, "Port")),
                )
                altered = local.fuse(lobe).removeSplitter()
                altered.Placement = original.Placement
                obj.Shape = altered
                self.doc.recompute()
                self.assertTrue(obj.Shape.isValid())
                self.assertEqual(len(obj.Shape.Solids), 1)
                result = tilt_clearance_check(
                    self.doc, self.pair_module("Port"), "Port"
                )
                self.assertFalse(result["passed"], result)
                neutral = next(
                    row for row in result["poses"] if row["output_angle_deg"] == 0
                )
                contact = neutral["spline_contacts"][0]
                self.assertTrue(contact["spline"]["passed"], contact)
                self.assertGreater(contact["forbidden_overlap_mm3"], 0.01)
                self.assertEqual(
                    [(row["moving"], row["fixed"]) for row in neutral["collisions"]],
                    [("PortServoHorn", "PortServo")],
                )
            finally:
                obj.Shape = original
                self.doc.recompute()

    def test_sampled_tilt_rejects_wrong_axis_and_wrong_motion_parent(self):
        from gondola.validation.propulsion import tilt_clearance_check

        servo = self.doc.PortServo
        original = App.Placement(servo.Placement)
        try:
            servo.Placement.Base = original.Base + App.Vector(0.1, 0, 0)
            self.doc.recompute()
            result = tilt_clearance_check(self.doc, self.pair_module("Port"), "Port")
            self.assertFalse(result["passed"], result)
            self.assertTrue(
                all(
                    not row["spline_contacts"][0]["spline"]["passed"]
                    for row in result["poses"]
                )
            )
        finally:
            servo.Placement = original
            self.doc.recompute()
        horn = self.doc.PortServoHorn
        try:
            self.doc.PortServoMount.addObject(horn)
            self.doc.recompute()
            result = tilt_clearance_check(self.doc, self.pair_module("Port"), "Port")
            self.assertFalse(result["passed"], result)
            self.assertEqual(result["poses"], [])
            self.assertIn("fixed mount", result["error"])
        finally:
            self.doc.PortInputDrive.addObject(horn)
            self.doc.recompute()

    def test_sampled_tilt_does_not_exempt_the_opposite_servo(self):
        from gondola.cad import placed_shape, world_shape
        from gondola.validation.propulsion import tilt_clearance_check

        wrong = self.doc.StarboardServo
        original = wrong.Shape.copy()
        try:
            wrong.Shape = placed_shape(
                world_shape(self.doc.PortServo),
                wrong.getParentGeoFeatureGroup().getGlobalPlacement().inverse(),
            )
            self.doc.recompute()
            result = tilt_clearance_check(
                self.doc, self.pair_module("Port", wrong.Name), "Port"
            )
            self.assertFalse(result["passed"], result)
            for row in result["poses"]:
                self.assertTrue(row["spline_contacts"][0]["passed"])
                self.assertEqual(
                    [(hit["moving"], hit["fixed"]) for hit in row["collisions"]],
                    [("PortServoHorn", "StarboardServo")],
                )
        finally:
            wrong.Shape = original
            self.doc.recompute()

    def test_actual_mirrored_oem_interfaces_remain_expected_after_root_transform(self):
        from gondola.validation.assembly import expected_pair, neutral_check

        for prefix in ("Port", "Starboard"):
            objects, shapes = self.pair(prefix)
            for ordered in (objects, objects[::-1]):
                with self.subTest(side=prefix, first=ordered[0].Name):
                    self.assertIsNotNone(
                        expected_pair(*ordered, *(shapes[obj.Name] for obj in ordered))
                    )
                    result = neutral_check(ordered, shapes)
                    self.assertTrue(result["passed"], result)
                    self.assertEqual(result["unexpected"], [])
                    rows = result["intentional_reference_envelopes"]
                    self.assertEqual(len(rows), 1)
                    self.assertGreater(rows[0]["intersection_mm3"], 0.1)

    def test_added_horn_or_case_material_is_not_exempted_with_the_spline_teeth(self):
        from gondola.cad import placed_shape
        from gondola.validation.assembly import expected_pair, neutral_check
        from gondola.validation.horn_coupling import coupling_frame

        for prefix in ("Port", "Starboard"):
            for suffix, depth in (("ServoHorn", 1), ("Servo", 2.3)):
                with self.subTest(side=prefix, altered_part=suffix):
                    objects, shapes = self.pair(prefix)
                    name = prefix + suffix
                    lobe = placed_shape(
                        Part.makeBox(0.3, depth, 0.3, App.Vector(2.4, -0.5, -0.15)),
                        coupling_frame(self.doc, prefix),
                    )
                    shapes[name] = shapes[name].fuse(lobe).removeSplitter()
                    self.assertTrue(shapes[name].isValid())
                    self.assertEqual(len(shapes[name].Solids), 1)
                    self.assertIsNone(
                        expected_pair(*objects, *(shapes[obj.Name] for obj in objects))
                    )
                    result = neutral_check(objects, shapes)
                    self.assertFalse(result["passed"], result)
                    self.assertEqual(result["intentional_reference_envelopes"], [])
                    self.assertEqual(len(result["unexpected"]), 1)
                    self.assertGreater(result["unexpected"][0]["intersection_mm3"], 0.1)

    def test_opposite_side_identity_cannot_claim_a_spline_contact_exemption(self):
        from gondola.validation.assembly import expected_pair, neutral_check

        objects, shapes = self.pair("Port")
        wrong_servo = self.doc.StarboardServo
        # Deliberately put the other side's case in the contacting pose. A
        # zero-overlap cross-side pair would never exercise the exemption gate.
        wrong_shapes = {
            objects[0].Name: shapes[objects[0].Name],
            wrong_servo.Name: shapes[objects[1].Name],
        }
        wrong_pair = [objects[0], wrong_servo]
        self.assertIsNone(
            expected_pair(*wrong_pair, *(wrong_shapes[obj.Name] for obj in wrong_pair))
        )
        result = neutral_check(wrong_pair, wrong_shapes)
        self.assertFalse(result["passed"], result)
        self.assertEqual(result["intentional_reference_envelopes"], [])
        self.assertEqual(len(result["unexpected"]), 1)


if __name__ == "__main__":
    unittest.main()
