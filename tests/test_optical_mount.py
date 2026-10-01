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
        cls.host = cls.doc.addObject("App::Part", "BatteryEquipmentModule")
        cls.module = optical_mount.build_optical_mount(cls.doc, cls.host)
        cls.parent = cls.module["group"]

    @classmethod
    def tearDownClass(cls):
        App.closeDocument(cls.doc.Name)

    def setUp(self):
        self.module["pitch_stage"].Pitch = 0
        self.host.Placement = App.Placement()
        self.doc.recompute()

    def test_two_prints_and_two_common_fastener_pairs(self):
        from gondola.contracts import fasteners

        self.assertEqual(len(self.module["printed"]), 2)
        self.assertEqual(len(self.module["hardware"]), 4)
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

    def test_integral_foot_has_no_offset_arm_or_rail_shoe(self):
        from gondola.parts import optical_interface, optical_mount

        shape = optical_mount.base_shape()
        self.assertLess(abs(optical_interface.foot_shape().cut(shape).Volume), 1e-5)
        self.assertEqual((shape.BoundBox.XLength, shape.BoundBox.YLength), (8, 18))
        # The raised carrier retains a local Z19 pivot. Preserve the complete
        # straight post witness while excluding its intentional clearance bore.
        bore = Part.makeCylinder(1.1, 2, App.Vector(0, -2, 19), App.Vector(0, 1, 0))
        post = Part.makeBox(8, 2, 17, App.Vector(-4, -2, 2)).cut(bore)
        self.assertLess(abs(post.cut(shape).Volume), 1e-5)
        self.assertLess(abs(bore.common(shape).Volume), 1e-5)
        self.assertAlmostEqual(shape.BoundBox.ZMin, -1.2)

    def test_foot_nut_pocket_keeps_printable_end_stock(self):
        from gondola.parts import optical_mount
        from gondola.validation.manufacturing import planar_wall_regions

        shape = optical_mount.base_shape()
        corrected = planar_wall_regions(shape)
        self.assertTrue(
            corrected, "The production floor must remain in the wall screen"
        )
        self.assertTrue(
            all(row["material_thickness_mm"] >= 1.5 - 1e-5 for row in corrected),
            corrected,
        )
        # Reproduce the former 8x16 foot from this exact production solid.
        # Its pocket axes, floor and every other feature remain unchanged.
        trimmed = shape.common(Part.makeBox(20, 16, 40, App.Vector(-10, -8, -5)))
        old_screen = planar_wall_regions(trimmed)
        thin = [row for row in old_screen if row["material_thickness_mm"] < 1.5 - 1e-5]
        self.assertTrue(thin, old_screen)
        self.assertTrue(
            any(abs(row["material_thickness_mm"] - 0.875) < 1e-5 for row in thin)
        )
        self.assertTrue(all(row["interior_samples_mm"] for row in thin))

    def test_actual_base_thickness_matches_every_manufacturing_probe(self):
        from gondola.parts import optical_interface, optical_mount
        from gondola.validation.manufacturing import material_length_on_line

        shape = optical_mount.base_shape()
        for (
            name,
            part,
            start,
            end,
            expected,
        ) in optical_interface.manufacturing_wall_probes():
            self.assertEqual(part, "OpticalMountBase")
            self.assertAlmostEqual(
                material_length_on_line(shape, start, end), expected, places=5, msg=name
            )

    def test_pivot_is_centred_on_foot_and_follows_carrier(self):
        from gondola.parts import optical_mount

        self.assertEqual(optical_mount.PIVOT_CENTRE, (0.0, 0.0, 19.0))
        self.assertEqual(self.module["group"].getParentGeoFeatureGroup(), self.host)
        self.assertAlmostEqual(self.module["group"].Placement.Base.z, 19.0)
        self.assertAlmostEqual(
            self.module["pitch_stage"].getGlobalPlacement().Base.z, 38
        )

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
        self.host.Placement.Base = shift
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

    def test_recessed_pitch_nut_follows_tray_and_minimum_nuts_cannot_spin(self):
        from gondola.parts import optical_mount
        from gondola.validation.optical import _nut_recess_checks

        self.assertEqual(
            self.doc.OpticalPitchNut.getParentGeoFeatureGroup(),
            self.doc.OpticalPitchStage,
        )
        for pitch in (-20, 0, 20):
            optical_mount.set_pitch(self.doc, pitch)
            result = _nut_recess_checks(self.doc)
            self.assertTrue(result["passed"], result)
        tray = self.doc.OpticalSensorTray
        original = tray.Shape.copy()
        try:
            tray.Shape = original.cut(
                Part.makeCylinder(2.7, 0.6, App.Vector(0, 1.5, 0), App.Vector(0, 1, 0))
            )
            self.assertFalse(_nut_recess_checks(self.doc)["passed"])
        finally:
            tray.Shape = original
        foot = self.doc.OpticalMountBase
        original = foot.Shape.copy()
        try:
            foot.Shape = original.cut(
                Part.makeCylinder(2.7, 0.6, App.Vector(0, 5, 1.5))
            )
            self.assertFalse(_nut_recess_checks(self.doc)["passed"])
        finally:
            foot.Shape = original
        self.assertTrue(_nut_recess_checks(self.doc)["passed"])

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
        self.assertAlmostEqual(bolt.BoundBox.YMax - b.YMax, 2.9)
        for obj in self.module["printed"]:
            self.assertLess(abs(world_shape(obj).common(core).Volume), 1e-5)


if __name__ == "__main__":
    unittest.main()
