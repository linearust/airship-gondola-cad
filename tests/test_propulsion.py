"""Native CAD regressions; run with the installed FreeCAD Python runtime."""

import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class ContinuousServiceTests(unittest.TestCase):
    def test_midpath_obstacle_is_not_hidden_by_clear_endpoints(self):
        from gondola.cad import translated_shape
        from gondola.validation.geometry import intersection_volume
        from gondola.validation.propulsion import continuous_path

        moving = Part.makeBox(0.1, 1, 1)
        obstacle = Part.makeBox(0.02, 1, 1, App.Vector(5.37, 0, 0))
        self.assertEqual(intersection_volume(moving, obstacle), 0)
        self.assertEqual(
            intersection_volume(translated_shape(moving, x=10), obstacle), 0
        )
        result = continuous_path(
            moving, [(0, 0, 0), (10, 0, 0)], {"thin_wall": obstacle}
        )
        self.assertFalse(result["passed"])
        self.assertGreater(result["segments"][0]["intersection_mm3"]["thin_wall"], 0)

    def test_coaxial_sweep_keeps_a_real_through_bore_open(self):
        from gondola.validation.geometry import intersection_volume, translation_sweep

        sleeve = Part.makeCylinder(2, 2).cut(Part.makeCylinder(1, 2))
        swept, method = translation_sweep(sleeve, (0, 0, 8))
        expected = Part.makeCylinder(2, 10).cut(Part.makeCylinder(1, 10))
        self.assertIn("face-prism", method)
        self.assertLess(abs(expected.cut(swept).Volume), 1e-7)
        self.assertLess(abs(swept.cut(expected).Volume), 1e-7)
        self.assertEqual(intersection_volume(swept, Part.makeCylinder(0.5, 10)), 0)

    def test_transverse_cylinder_uses_a_conservative_envelope(self):
        from gondola.cad import translated_shape
        from gondola.validation.geometry import translation_sweep

        moving = Part.makeCylinder(1, 2)
        swept, method = translation_sweep(moving, (-10, 0, 0))
        self.assertIn("conservative", method)
        for distance in (0, -0.13, -4.57, -10):
            self.assertLess(
                abs(translated_shape(moving, x=distance).cut(swept).Volume), 1e-7
            )

    def test_invalid_displacement_is_rejected(self):
        from gondola.validation.geometry import translation_sweep

        with self.assertRaises(ValueError):
            translation_sweep(Part.makeBox(1, 1, 1), (float("nan"), 0, 0))


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class JournalRetentionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.cad import world_shape
        from gondola.parts import propulsion

        cls.doc = App.newDocument("JournalRetentionRegression")
        cls.module = propulsion.build_propulsion_module(cls.doc)
        cls.frame = world_shape(cls.module["frame"])

    @classmethod
    def tearDownClass(cls):
        App.closeDocument(cls.doc.Name)

    def stack(self, prefix="Port", side=1):
        from gondola.cad import world_shape

        suffix = "Positive" if side > 0 else "Negative"
        sleeve = world_shape(self.doc.getObject(prefix + "JournalSleeve" + suffix))
        hardware = {
            kind: world_shape(self.doc.getObject(prefix + "Journal" + suffix + kind))
            for kind in ("Bolt", "Nut")
        }
        carrier = world_shape(self.doc.getObject(prefix + "MotorCarrier"))
        return sleeve, hardware, carrier

    def test_complete_stack_captures_each_journal_and_turns_freely(self):
        from gondola.validation.propulsion import journal_stack_check

        for prefix in ("Port", "Starboard"):
            for side in (-1, 1):
                with self.subTest(prefix=prefix, side=side):
                    sleeve, hardware, carrier = self.stack(prefix, side)
                    result = journal_stack_check(
                        sleeve, hardware, self.frame, carrier, side
                    )
                    self.assertTrue(result["passed"], result)
                    self.assertAlmostEqual(result["bolt_tip_beyond_nut_mm"], 2.35)
                    self.assertAlmostEqual(result["nut_engagement_length_mm"], 1.2)

    def test_missing_integral_cap_cannot_retain_the_journal(self):
        from gondola.parts import propulsion
        from gondola.validation.propulsion import journal_stack_check

        sleeve, hardware, carrier = self.stack()
        carrier = carrier.cut(
            Part.makeCylinder(
                6.01,
                propulsion.CARRIER_CAP_THICKNESS,
                App.Vector(0, 80 + propulsion.CARRIER_CAP_INNER_Y, propulsion.PIVOT_Z),
                App.Vector(0, 1, 0),
            )
        )
        result = journal_stack_check(sleeve, hardware, self.frame, carrier, 1)
        self.assertFalse(result["passed"])
        self.assertFalse(result["axial_capture"])
        self.assertEqual(result["outward_1mm_blocking_intersection_mm3"], 0)

    def test_no_loose_retainer_and_common_square_nut(self):
        self.assertEqual(len(self.module["printed"]), 7)
        self.assertEqual(len(self.module["hardware"]), 8)
        self.assertEqual(
            {obj.HardwareSKU for obj in self.module["hardware"]},
            {"M2X14_SOCKET_CAP", "M2_SQUARE_NUT_DIN562"},
        )
        self.assertTrue(
            all(len(obj.Shape.Solids) == 1 for obj in self.module["printed"])
        )

    def test_unseated_nut_does_not_pass_on_clearance_alone(self):
        from gondola.cad import translated_shape
        from gondola.validation.propulsion import journal_stack_check

        sleeve, hardware, carrier = self.stack()
        hardware["Nut"] = translated_shape(hardware["Nut"], y=-0.2)
        result = journal_stack_check(sleeve, hardware, self.frame, carrier, 1)
        self.assertFalse(result["passed"])
        self.assertFalse(result["contacts"][-1]["passed"])

    def test_bolt_must_cross_the_full_nut(self):
        from gondola.cad import translated_shape
        from gondola.validation.propulsion import journal_stack_check

        sleeve, hardware, carrier = self.stack()
        hardware["Bolt"] = translated_shape(hardware["Bolt"], y=2.55)
        result = journal_stack_check(sleeve, hardware, self.frame, carrier, 1)
        self.assertFalse(result["passed"])
        self.assertGreater(result["missing_bolt_thread_core_mm3"], 0)


if __name__ == "__main__":
    unittest.main()
