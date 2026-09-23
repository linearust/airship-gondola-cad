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
        from gondola.contracts import fasteners

        self.assertEqual(len(self.module["printed"]), 3)
        self.assertEqual(len(self.module["hardware"]), 8)
        for obj in self.module["printed"] + self.module["hardware"]:
            self.assertTrue(obj.Shape.isValid(), obj.Name)
            self.assertEqual(len(obj.Shape.Solids), 1, obj.Name)
        for obj in self.module["hardware"]:
            self.assertFalse(obj.PrintPart, obj.Name)
            self.assertNotIn("WASHER", obj.HardwareSKU)
            if "Bolt" in obj.Name:
                self.assertEqual(obj.HardwareSKU, "M2X8_BUTTON_HEAD")
                self.assertEqual(obj.MaterialSelection, fasteners.KIT_MATERIAL)
            else:
                self.assertEqual(obj.HardwareSKU, "M2_HEX_NUT")
                self.assertEqual(obj.MaterialSelection, fasteners.KIT_MATERIAL)
        contract = json.loads(self.module["group"].OpticalMountContract)
        self.assertFalse(contract["holding_torque_verified"])
        self.assertFalse(contract["self_levelling"])
        self.assertFalse(contract["physical_angle_stops_modeled"])

    def test_integral_tower_has_broad_clamped_feet_and_open_device_space(self):
        from gondola.parts import optical_mount, stack_interface

        base = optical_mount.base_shape()
        tower = stack_interface.tower_shape()
        self.assertLess(abs(tower.cut(base).Volume), 1e-5)
        self.assertEqual(set(stack_interface.ANCHOR_CENTRES), {(-24, -24), (24, 24)})
        self.assertAlmostEqual(base.BoundBox.ZMin, -stack_interface.TOWER_HEIGHT)
        self.assertEqual(len(base.Solids), 1)
        # Devices and wiring remain in the open centre, while both complete
        # clamped feet belong to one installed print.
        centre = Part.makeBox(30, 30, 31, App.Vector(-15, -15, -32))
        self.assertLess(abs(base.common(centre).Volume), 1e-5)
        self.assertEqual(sum("Foot" in obj.Name for obj in self.module["hardware"]), 4)

    def test_full_pivot_root_bears_on_the_straight_top_beam(self):
        from gondola.parts import optical_mount, stack_interface

        support = Part.makeBox(
            optical_mount.EAR_THICKNESS,
            2 * optical_mount.EAR_RADIUS,
            0.2,
            App.Vector(
                -optical_mount.EAR_THICKNESS,
                -optical_mount.EAR_RADIUS,
                stack_interface.TOP_BEAM_THICKNESS - 0.2,
            ),
        )
        self.assertLess(abs(support.cut(stack_interface.tower_shape()).Volume), 1e-5)
        self.assertLess(abs(support.cut(optical_mount.base_shape()).Volume), 1e-5)

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
            self.assertAlmostEqual(high - low, 1.6, places=7)
            self.assertAlmostEqual(tip - high, 2.4, places=7)

    def test_backset_post_regression_would_obstruct_the_pitch_screw(self):
        from gondola.cad import world_shape
        from gondola.validation.geometry import intersection_volume

        bad_post = Part.makeBox(2, 2, 12, App.Vector(0, -3.5, -2))
        bad_post.Placement = self.module["roll_stage"].getGlobalPlacement()
        bolt = world_shape(self.doc.getObject("OpticalPitchBolt"))
        self.assertGreater(intersection_volume(bad_post, bolt), 0.1)

    def test_pivot_post_retains_the_full_two_mm_square_section(self):
        from gondola.parts import optical_mount

        shape = optical_mount.roll_bracket_shape()
        section = Part.makeBox(2, 2, 1, App.Vector(0, -2, 4.5))
        self.assertLess(abs(section.cut(shape).Volume), 1e-5)
        broad_section = Part.makeBox(4, 4, 1, App.Vector(-1, -3, 4.5))
        self.assertAlmostEqual(shape.common(broad_section).Volume, 4.0, places=7)


if __name__ == "__main__":
    unittest.main()
