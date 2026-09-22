"""Regressions for continuous carrier/metal clearance and physical axial stops."""

import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class CarrierMotionClearanceTests(unittest.TestCase):
    def module(self, configuration=None):
        from gondola.contracts.drive import SELECTED_DRIVE
        from gondola.parts.propulsion import build_propulsion_module

        doc = App.newDocument("CarrierMotionClearance")
        self.addCleanup(App.closeDocument, doc.Name)
        module = build_propulsion_module(doc, configuration or SELECTED_DRIVE)
        return doc, module

    def test_both_ratios_and_sides_keep_the_reserve_after_axial_play(self):
        from gondola.contracts.drive import DRIVE_CONFIGURATIONS
        from gondola.validation.motion_clearance import carrier_metal_clearance_check

        for configuration in DRIVE_CONFIGURATIONS.values():
            doc, _ = self.module(configuration)
            doc.PortPod.Tilt = 123.4
            doc.StarboardPod.Tilt = -77.2
            doc.recompute()
            for prefix in ("Port", "Starboard"):
                with self.subTest(configuration=configuration.key, side=prefix):
                    result = carrier_metal_clearance_check(doc, prefix)
                    self.assertTrue(result["passed"], result)
                    self.assertAlmostEqual(result["axial_travel"]["negative_mm"], 0.5)
                    self.assertAlmostEqual(result["axial_travel"]["positive_mm"], 0.5)
                    self.assertGreater(result["minimum_clearance_lower_bound_mm"], 1.64)
                    self.assertEqual(len(result["fixed_hardware"]), 4)
                    self.assertEqual(len(result["envelope"]["containment"]), 5)

    def test_arbitrary_parent_rotation_and_current_tilt_preserve_the_proof(self):
        from gondola.validation.motion_clearance import carrier_metal_clearance_check

        doc, module = self.module()
        original = carrier_metal_clearance_check(doc, "Port")
        root = doc.addObject("App::Part", "MovedRoot")
        root.addObject(module["group"])
        root.Placement = App.Placement(
            App.Vector(132, -56, 219), App.Rotation(App.Vector(2, -5, 3), 67)
        )
        module["group"].Placement = App.Placement(
            App.Vector(-13, 8, 41), App.Rotation(App.Vector(5, 2, 1), -38)
        )
        doc.PortPod.Tilt = -139.2
        doc.recompute()
        transformed = carrier_metal_clearance_check(doc, "Port")
        self.assertTrue(transformed["passed"], transformed)
        self.assertAlmostEqual(
            transformed["minimum_clearance_lower_bound_mm"],
            original["minimum_clearance_lower_bound_mm"],
            places=6,
        )

    def test_curved_protrusion_cannot_hide_between_its_inside_vertices(self):
        from gondola.validation.motion_clearance import (
            GUARD_SPHERE_RADIUS_MM,
            carrier_metal_clearance_check,
        )

        doc, _ = self.module()
        # The sphere's polar vertices fit the declaration; its curved equator
        # protrudes. A vertices-only envelope test would accept this change.
        bulge = Part.makeSphere(1, App.Vector(12.5, 0, 24), App.Vector(0, 1, 0))
        self.assertTrue(bulge.Vertexes)
        self.assertTrue(
            all(
                vertex.Point.Length < GUARD_SPHERE_RADIUS_MM
                for vertex in bulge.Vertexes
            )
        )
        doc.PortMotorCarrier.Shape = doc.PortMotorCarrier.Shape.fuse(bulge)
        doc.recompute()
        result = carrier_metal_clearance_check(doc, "Port")
        self.assertFalse(result["passed"])
        carrier = result["envelope"]["containment"][0]
        self.assertGreater(carrier["outside_envelope_mm3"], 0.01)

    def test_a_cap_nut_moved_into_the_motion_reserve_is_rejected(self):
        from gondola.validation.motion_clearance import carrier_metal_clearance_check

        doc, _ = self.module()
        nut = doc.PortOutputBearingCapPositiveNut
        position = nut.Placement
        position.Base.x -= 2
        nut.Placement = position
        doc.recompute()
        result = carrier_metal_clearance_check(doc, "Port")
        self.assertFalse(result["passed"])
        row = next(
            item for item in result["fixed_hardware"] if item["fixed"] == nut.Name
        )
        self.assertLess(row["continuous_clearance_lower_bound_mm"], 1.5)

    def test_removing_a_physical_stop_is_not_hidden_by_the_frame_bounds(self):
        from gondola.parts.propulsion import PIVOT_HALF_SPAN, PIVOT_Z
        from gondola.validation.motion_clearance import carrier_axial_travel

        doc, _ = self.module()
        frame = doc.PropulsionFixedFrame
        frame.Shape = frame.Shape.cut(
            Part.makeCylinder(
                3.2,
                10,
                App.Vector(0, PIVOT_HALF_SPAN + 26, PIVOT_Z),
                App.Vector(0, 1, 0),
            )
        )
        doc.recompute()
        result = carrier_axial_travel(doc, "Port")
        self.assertFalse(result["passed"], result)
        self.assertIsNone(result["maximum_mm"])

    def test_extra_stop_travel_consumes_clearance_even_without_nominal_collision(self):
        from gondola.parts.propulsion import PIVOT_HALF_SPAN, PIVOT_Z
        from gondola.validation.motion_clearance import carrier_metal_clearance_check

        doc, _ = self.module()
        frame = doc.PropulsionFixedFrame
        frame.Shape = frame.Shape.cut(
            Part.makeCylinder(
                4.7,
                1,
                App.Vector(0, PIVOT_HALF_SPAN + 26.5, PIVOT_Z),
                App.Vector(0, 1, 0),
            )
        )
        doc.recompute()
        result = carrier_metal_clearance_check(doc, "Port")
        self.assertTrue(result["axial_travel"]["passed"], result)
        self.assertAlmostEqual(result["axial_travel"]["positive_mm"], 1.5)
        self.assertFalse(result["passed"])
        self.assertLess(result["minimum_clearance_lower_bound_mm"], 1.0)

    def test_shifted_clamp_hardware_must_fit_the_proven_rotating_envelope(self):
        from gondola.validation.motion_clearance import carrier_metal_clearance_check

        doc, _ = self.module()
        nut = doc.PortOutputClampPositiveNut
        position = nut.Placement
        position.Base.x += 20
        nut.Placement = position
        doc.recompute()
        result = carrier_metal_clearance_check(doc, "Port")
        self.assertFalse(result["passed"])
        row = next(
            item
            for item in result["envelope"]["containment"]
            if item["object"] == nut.Name
        )
        self.assertGreater(row["outside_envelope_mm3"], 1)


if __name__ == "__main__":
    unittest.main()
