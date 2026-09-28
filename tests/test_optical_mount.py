"""Native mechanism checks for the compact single-axis optical pedestal."""

import itertools
import json
import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class OpticalMountTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.parts import optical_mount

        cls.doc = App.newDocument("OpticalMountRegression")
        cls.parent = cls.doc.addObject("App::Part", "Host")
        cls.module = optical_mount.build_optical_mount(cls.doc, cls.parent)

    @classmethod
    def tearDownClass(cls):
        App.closeDocument(cls.doc.Name)

    def setUp(self):
        self.module["pitch_stage"].Pitch = 0
        self.parent.Placement = App.Placement()
        self.doc.recompute()

    def test_two_prints_and_three_existing_m2_fastener_pairs(self):
        from gondola.contracts import fasteners

        self.assertEqual(len(self.module["printed"]), 2)
        self.assertEqual(len(self.module["hardware"]), 6)
        self.assertIsNone(self.doc.getObject("OpticalRollStage"))
        self.assertIsNone(self.doc.getObject("OpticalRollBracket"))
        for obj in self.module["printed"] + self.module["hardware"]:
            self.assertTrue(obj.Shape.isValid(), obj.Name)
            self.assertEqual(len(obj.Shape.Solids), 1, obj.Name)
        for obj in self.module["hardware"]:
            self.assertFalse(obj.PrintPart)
            self.assertEqual(
                obj.HardwareSKU,
                "M2X8_BUTTON_HEAD" if "Bolt" in obj.Name else "M2_HEX_NUT",
            )
            self.assertEqual(obj.MaterialSelection, fasteners.KIT_MATERIAL)
        contract = json.loads(self.module["group"].OpticalMountContract)
        self.assertEqual(contract["adjustment_degrees_of_freedom"], 1)
        for key in (
            "holding_torque_verified",
            "self_levelling",
            "physical_angle_stops_modeled",
        ):
            self.assertFalse(contract[key])

    def test_compact_foot_and_straight_upright_are_continuous(self):
        from gondola.parts import optical_interface, optical_mount

        shape = optical_mount.base_shape()
        self.assertLess(abs(optical_interface.foot_shape().cut(shape).Volume), 1e-5)
        self.assertLess(shape.BoundBox.XLength, 11)
        self.assertLessEqual(shape.BoundBox.YLength, 16)
        self.assertLess(shape.BoundBox.ZLength, 26)
        post = Part.makeBox(4, 2, 12, App.Vector(-1, 0, 2))
        self.assertLess(abs(post.cut(shape).Volume), 1e-5)
        self.assertGreater(shape.Volume, 350)

    def test_pitch_limit_is_native_and_every_part_follows_the_host(self):
        from gondola.cad import world_shape

        pitch = self.module["pitch_stage"]
        for requested, expected in (
            (-999, -20),
            (-11, -11),
            (0, 0),
            (13, 13),
            (999, 20),
        ):
            pitch.Pitch = requested
            self.doc.recompute()
            self.assertTrue(
                pitch.Placement.Rotation.isSame(
                    App.Rotation(App.Vector(0, 1, 0), expected), 1e-7
                )
            )
        before = {
            obj.Name: world_shape(obj).Solids[0].CenterOfMass
            for obj in self.module["printed"] + self.module["hardware"]
        }
        shift = App.Vector(37, -9, 3)
        self.parent.Placement.Base = shift
        self.doc.recompute()
        for obj in self.module["printed"] + self.module["hardware"]:
            self.assertLess(
                (
                    world_shape(obj).Solids[0].CenterOfMass - before[obj.Name] - shift
                ).Length,
                1e-7,
            )

    def test_head_and_complete_fasteners_clear_at_all_sampled_angles(self):
        from gondola.cad import world_shape
        from gondola.parts.optical_mount import set_pitch
        from gondola.validation.geometry import intersection_volume

        for pitch in range(-20, 21, 2):
            set_pitch(self.doc, pitch)
            shapes = [
                (obj.Name, world_shape(obj))
                for obj in self.module["printed"] + self.module["hardware"]
            ]
            for (first, a), (second, b) in itertools.combinations(shapes, 2):
                self.assertLess(intersection_volume(a, b), 1e-5, (pitch, first, second))

    def test_pitch_screw_engages_full_nut_and_clearance_holes_are_open(self):
        from gondola.cad import world_shape

        bolt = world_shape(self.doc.OpticalPitchBolt)
        nut = world_shape(self.doc.OpticalPitchNut)
        b = nut.BoundBox
        core = Part.makeCylinder(
            0.8,
            b.YLength,
            App.Vector((b.XMin + b.XMax) / 2, b.YMin, (b.ZMin + b.ZMax) / 2),
            App.Vector(0, 1, 0),
        )
        self.assertLess(abs(core.cut(bolt).Volume), 1e-5)
        self.assertAlmostEqual(b.YLength, 1.6)
        self.assertAlmostEqual(bolt.BoundBox.YMax - b.YMax, 2.4)
        for obj in self.module["printed"]:
            self.assertLess(abs(world_shape(obj).common(core).Volume), 1e-5)

    def test_bad_post_that_crosses_upper_nut_is_detectable(self):
        from gondola.cad import world_shape
        from gondola.validation.geometry import intersection_volume

        bad = Part.makeBox(4, 4, 5, App.Vector(0, 2, 2))
        bad.Placement = self.module["group"].getGlobalPlacement()
        self.assertGreater(
            intersection_volume(bad, world_shape(self.doc.OpticalFootNut1)), 0.1
        )


if __name__ == "__main__":
    unittest.main()
