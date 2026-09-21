"""Native regressions for the independently clamped two-axis optical head."""

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
        self.module["roll_stage"].Roll = 0
        self.module["pitch_stage"].Pitch = 0
        self.parent.Placement = App.Placement()
        self.doc.recompute()

    def test_three_separate_solids_and_eight_purchased_fasteners(self):
        self.assertEqual(len(self.module["printed"]), 3)
        self.assertEqual(len(self.module["hardware"]), 8)
        for obj in self.module["printed"] + self.module["hardware"]:
            self.assertTrue(obj.Shape.isValid(), obj.Name)
            self.assertEqual(len(obj.Shape.Solids), 1, obj.Name)
        for obj in self.module["hardware"]:
            self.assertFalse(obj.PrintPart, obj.Name)
        contract = json.loads(self.module["group"].OpticalMountContract)
        self.assertFalse(contract["holding_torque_verified"])
        self.assertFalse(contract["self_levelling"])
        self.assertFalse(contract["physical_angle_stops_modeled"])

    def test_shared_stack_platform_and_four_holes_are_not_refilled(self):
        from gondola.parts import optical_mount, stack_interface

        base = optical_mount.base_shape()
        platform = stack_interface.platform_shape()
        slab = Part.makeBox(60, 60, 2, App.Vector(-30, -30, 0))
        measured = base.common(slab)
        self.assertLess(abs(platform.cut(measured).Volume), 1e-5)
        self.assertLess(abs(measured.cut(platform).Volume), 1e-5)
        for x, y in itertools.product((-20, 20), repeat=2):
            bore = Part.makeCylinder(1.3, 2, App.Vector(x, y, 0))
            self.assertLess(abs(base.common(bore).Volume), 1e-5)

    def test_native_angles_clamp_independently_and_follow_the_host(self):
        from gondola.cad import world_shape

        roll, pitch = self.module["roll_stage"], self.module["pitch_stage"]
        for requested, expected in (
            (-999, -20),
            (-11, -11),
            (0, 0),
            (13, 13),
            (999, 20),
        ):
            roll.Roll = requested
            self.doc.recompute()
            self.assertTrue(
                roll.Placement.Rotation.isSame(
                    App.Rotation(App.Vector(1, 0, 0), expected), 1e-7
                )
            )
            self.assertTrue(pitch.Placement.Rotation.isSame(App.Rotation(), 1e-7))
        roll.Roll = 0
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
            self.assertTrue(roll.Placement.Rotation.isSame(App.Rotation(), 1e-7))
        before = {
            o.Name: world_shape(o).Solids[0].CenterOfMass
            for o in self.module["printed"] + self.module["hardware"]
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
                obj.Name,
            )

    def test_complete_assembled_head_has_no_volume_collision_at_adjusted_poses(self):
        from gondola.cad import world_shape
        from gondola.parts.optical_mount import set_angles
        from gondola.validation.geometry import intersection_volume

        objects = self.module["printed"] + self.module["hardware"]
        for roll, pitch in itertools.product((-20, -10, 0, 10, 20), repeat=2):
            set_angles(self.doc, roll, pitch)
            shapes = [(o.Name, world_shape(o)) for o in objects]
            for (first, a), (second, b) in itertools.combinations(shapes, 2):
                self.assertLess(
                    intersection_volume(a, b), 1e-5, (roll, pitch, first, second)
                )

    def test_both_bolts_cross_the_complete_nut_and_project_beyond_it(self):
        from gondola.cad import world_shape

        for prefix, axis in (("OpticalRoll", 0), ("OpticalPitch", 1)):
            bolt = world_shape(self.doc.getObject(prefix + "Bolt"))
            nut = world_shape(self.doc.getObject(prefix + "Nut"))
            bounds = nut.BoundBox
            low = (bounds.XMin, bounds.YMin, bounds.ZMin)[axis]
            high = (bounds.XMax, bounds.YMax, bounds.ZMax)[axis]
            tip = (bolt.BoundBox.XMax, bolt.BoundBox.YMax, bolt.BoundBox.ZMax)[axis]
            origin = App.Vector(
                (bounds.XMin + bounds.XMax) / 2,
                (bounds.YMin + bounds.YMax) / 2,
                (bounds.ZMin + bounds.ZMax) / 2,
            )
            origin[axis] = low
            direction = App.Vector(1, 0, 0) if axis == 0 else App.Vector(0, 1, 0)
            core = Part.makeCylinder(0.8, high - low, origin, direction)
            self.assertLess(abs(core.cut(bolt).Volume), 1e-5, prefix)
            self.assertAlmostEqual(tip - high, 1.8, places=7)

    def test_backset_post_regression_would_obstruct_the_pitch_washer(self):
        from gondola.cad import world_shape
        from gondola.validation.geometry import intersection_volume

        bad_post = Part.makeBox(2, 2, 12, App.Vector(0, -3.5, -2))
        bad_post.Placement = self.module["roll_stage"].getGlobalPlacement()
        washer = world_shape(self.doc.getObject("OpticalPitchOuterWasher"))
        self.assertGreater(intersection_volume(bad_post, washer), 0.1)


if __name__ == "__main__":
    unittest.main()
