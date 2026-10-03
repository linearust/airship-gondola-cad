"""Continuous motion and actual opposing stops for the inboard-supported rotors."""

import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class CarrierMotionClearanceTests(unittest.TestCase):
    def module(self):
        from gondola.parts.propulsion import build_propulsion_module

        doc = App.newDocument("CarrierMotionClearance")
        self.addCleanup(App.closeDocument, doc.Name)
        return doc, build_propulsion_module(doc)

    def test_both_sides_keep_reserve_and_half_mm_opposed_stops(self):
        from gondola.validation.motion_clearance import carrier_metal_clearance_check

        doc, _ = self.module()
        doc.PortPod.Tilt = 123.4
        doc.StarboardPod.Tilt = -77.2
        doc.recompute()
        for prefix in ("Port", "Starboard"):
            result = carrier_metal_clearance_check(doc, prefix)
            self.assertTrue(result["passed"], result)
            self.assertAlmostEqual(result["axial_travel"]["negative_mm"], 0.5, places=6)
            self.assertAlmostEqual(result["axial_travel"]["positive_mm"], 0.5, places=6)
            self.assertGreaterEqual(result["minimum_clearance_lower_bound_mm"], 1.5)
            self.assertEqual(
                {row["fixed"] for row in result["fixed_hardware"]},
                {
                    prefix + stem + kind
                    for stem in (
                        "BearingCapNegative",
                        "BearingCapInput",
                        "ServoEarLower",
                        "ServoEarUpper",
                    )
                    for kind in ("Bolt", "Nut")
                },
            )
            self.assertEqual(len(result["fixed_hardware"]), 8)
            self.assertEqual(len(result["envelope"]["containment"]), 6)

    def test_parent_transform_and_tilt_preserve_the_proof(self):
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
        result = carrier_metal_clearance_check(doc, "Port")
        self.assertTrue(result["passed"], result)
        self.assertAlmostEqual(
            result["minimum_clearance_lower_bound_mm"],
            original["minimum_clearance_lower_bound_mm"],
            places=6,
        )

    def test_gear_and_carrier_contacts_bound_opposite_directions(self):
        from gondola.validation.motion_clearance import carrier_axial_travel

        doc, _ = self.module()
        for prefix in ("Port", "Starboard"):
            result = carrier_axial_travel(doc, prefix)
            self.assertTrue(result["passed"], result)
            self.assertEqual(
                {r["moving_stop_part"] for r in result["stops"]},
                {prefix + "MotorCarrier", prefix + "OutputGear"},
            )
            for row in result["stops"]:
                self.assertGreaterEqual(
                    row["all_angles_contact_lower_bound_mm2"],
                    0.25 * row["witness_area_mm2"] - 1e-7,
                )

    def test_removing_all_housing_stop_lands_is_rejected(self):
        from gondola.validation.motion_clearance import carrier_axial_travel

        doc, _ = self.module()
        cutter = Part.makeCylinder(
            4.7, 20.2, App.Vector(0, 23.9, 50), App.Vector(0, 1, 0)
        )
        for obj in (doc.PropulsionFixedFrame, doc.PortBearingCap):
            obj.Shape = obj.Shape.cut(cutter)
        doc.recompute()
        result = carrier_axial_travel(doc, "Port")
        self.assertFalse(result["passed"], result)
        self.assertIsNone(result["maximum_mm"])

    def test_small_remaining_stop_sector_does_not_meet_contact_lower_bound(self):
        from gondola.validation.motion_clearance import carrier_axial_travel

        doc, _ = self.module()
        # Retain only a narrow lower-left cap of each annular stop.
        cutter = Part.makeBox(10, 21, 20, App.Vector(-1.5, 23.5, 40)).fuse(
            Part.makeBox(10, 21, 12, App.Vector(-10, 23.5, 48))
        )
        for obj in (doc.PropulsionFixedFrame, doc.PortBearingCap):
            obj.Shape = obj.Shape.cut(cutter)
        doc.recompute()
        self.assertFalse(carrier_axial_travel(doc, "Port")["passed"])

    def test_extra_stop_travel_is_measured_and_reaches_journal_flat(self):
        from gondola.validation.motion_clearance import carrier_axial_travel
        from gondola.validation.propulsion import output_bearing_stack_check

        doc, _ = self.module()
        cutter = Part.makeCylinder(
            4.7, 1.2, App.Vector(0, 42.9, 50), App.Vector(0, 1, 0)
        )
        for obj in (doc.PropulsionFixedFrame, doc.PortBearingCap):
            obj.Shape = obj.Shape.cut(cutter)
        doc.recompute()
        result = carrier_axial_travel(doc, "Port")
        self.assertTrue(result["passed"], result)
        self.assertGreater(result["negative_mm"], 0.5)
        self.assertFalse(output_bearing_stack_check(doc, "Port", "Outboard")["passed"])

    def test_curved_protrusion_cannot_hide_between_inside_vertices(self):
        from gondola.validation.motion_clearance import (
            GUARD_SPHERE_RADIUS_MM,
            carrier_metal_clearance_check,
        )

        doc, _ = self.module()
        centre = App.Vector(9, 0, 24.5)
        centre.normalize()
        centre *= GUARD_SPHERE_RADIUS_MM - 2
        bulge = Part.makeSphere(3, centre, App.Vector(0, 1, 0))
        self.assertGreater(bulge.common(doc.PortMotorCarrier.Shape).Volume, 0.1)
        self.assertTrue(
            all(v.Point.Length < GUARD_SPHERE_RADIUS_MM for v in bulge.Vertexes)
        )
        doc.PortMotorCarrier.Shape = doc.PortMotorCarrier.Shape.fuse(bulge)
        doc.recompute()
        result = carrier_metal_clearance_check(doc, "Port")
        self.assertFalse(result["passed"])
        self.assertGreater(
            result["envelope"]["containment"][0]["outside_envelope_mm3"], 0.01
        )

    def test_fixed_nut_in_motion_reserve_is_rejected(self):
        from gondola.validation.motion_clearance import carrier_metal_clearance_check

        doc, _ = self.module()
        nut = doc.PortBearingCapNegativeNut
        position = nut.Placement
        position.Base = (
            nut.getParentGeoFeatureGroup()
            .getGlobalPlacement()
            .inverse()
            .multVec(doc.PortPod.Placement.Base + App.Vector(10, 25, 0))
        )
        nut.Placement = position
        doc.recompute()
        result = carrier_metal_clearance_check(doc, "Port")
        self.assertFalse(result["passed"])
        row = next(r for r in result["fixed_hardware"] if r["fixed"] == nut.Name)
        self.assertLess(row["continuous_clearance_lower_bound_mm"], 1.5)

    def test_shifted_jack_hardware_must_fit_rotating_envelope(self):
        from gondola.validation.motion_clearance import carrier_metal_clearance_check

        doc, _ = self.module()
        doc.PortOutputClampNegativeNut.Placement.Base.x += 20
        doc.recompute()
        result = carrier_metal_clearance_check(doc, "Port")
        self.assertFalse(result["passed"])
        row = next(
            r
            for r in result["envelope"]["containment"]
            if r["object"] == "PortOutputClampNegativeNut"
        )
        self.assertGreater(row["outside_envelope_mm3"], 1)


if __name__ == "__main__":
    unittest.main()
