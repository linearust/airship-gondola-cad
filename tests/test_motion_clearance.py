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

    def test_selected_drive_both_sides_keep_the_reserve_after_axial_play(self):
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
                    self.assertEqual(len(result["fixed_hardware"]), 6)
                    self.assertEqual(len(result["envelope"]["containment"]), 8)

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

    def test_open_release_pockets_preserve_a_substantial_all_angle_stop_bound(self):
        from gondola.validation.motion_clearance import carrier_axial_travel

        doc, _ = self.module()
        for prefix in ("Port", "Starboard"):
            result = carrier_axial_travel(doc, prefix)
            self.assertTrue(result["passed"], result)
            for stop in result["stops"]:
                # AM deliberately leaves the side pockets open. A test that
                # still demanded a complete fixed annulus would refill them.
                self.assertGreater(stop["frame_uncovered_witness_area_mm2"], 0.1)
                self.assertGreaterEqual(
                    stop["all_angles_contact_lower_bound_mm2"],
                    0.25 * stop["witness_area_mm2"],
                )
                self.assertAlmostEqual(stop["travel_mm"], 0.5)

    def test_a_small_remaining_stop_sector_cannot_claim_all_angle_contact(self):
        from gondola.parts.propulsion import PIVOT_HALF_SPAN, PIVOT_Z
        from gondola.validation.motion_clearance import carrier_axial_travel

        doc, _ = self.module()
        frame = doc.PropulsionFixedFrame
        # Keep one quarter of the annular stop, including real neutral contact,
        # while removing the other sectors through every possible cup face.
        remove_right = Part.makeBox(
            8, 10, 16, App.Vector(0, PIVOT_HALF_SPAN + 26.4, PIVOT_Z - 8)
        )
        remove_upper_left = Part.makeBox(
            8, 10, 8, App.Vector(-8, PIVOT_HALF_SPAN + 26.4, PIVOT_Z)
        )
        frame.Shape = frame.Shape.cut(remove_right.fuse(remove_upper_left))
        doc.recompute()
        result = carrier_axial_travel(doc, "Port")
        self.assertFalse(result["passed"], result)
        self.assertTrue(result["stops"][0]["passed"], result)
        self.assertFalse(result["stops"][1]["passed"], result)

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

    def test_a_mount_nut_moved_into_the_motion_reserve_is_rejected(self):
        from gondola.validation.motion_clearance import carrier_metal_clearance_check

        doc, _ = self.module()
        nut = doc.ServoBridgePortNut
        position = nut.Placement
        pivot = doc.PortPod.Placement.Base
        # Put the real fixed nut beside the rotating guard, inside its required
        # reserve. A nearer architecture cannot reuse the old large gap.
        position.Base = pivot + App.Vector(10, 25, 0)
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
                3.7,
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
        from gondola.validation.propulsion import output_bearing_stack_check

        # The fixed bearing hooks still capture the bearing. Increased carrier
        # motion instead consumes its separate clearance from the bearing face.
        bearing = output_bearing_stack_check(doc, "Port", "Negative")
        self.assertFalse(bearing["passed"], bearing)
        self.assertLess(bearing["minimum_carrier_to_bearing_face_gap_mm"], 1.8)
        self.assertTrue(bearing["capture_geometry"]["passed"], bearing)

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
