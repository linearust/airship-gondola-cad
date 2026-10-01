"""Full circular head support with accepted centring, including edge damage."""

import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class SlotBearingTests(unittest.TestCase):
    def test_shank_clearance_is_not_accepted_as_head_bearing_position(self):
        from gondola.parts import optical_interface, slot_bearing, stack_interface

        fit = slot_bearing.contract(2.9, 1.8)
        self.assertAlmostEqual(fit["full_free_screw_offset_mm"], 0.55)
        self.assertAlmostEqual(
            fit["minimum_transverse_land_at_full_free_offset_mm"], -0.25
        )
        self.assertFalse(fit["full_free_screw_offset_support_qualified"])
        self.assertAlmostEqual(
            fit["minimum_transverse_land_at_accepted_centring_mm"], 0.2
        )
        for installed in (
            optical_interface.interface_contract(),
            stack_interface.clamp_fit_contract(),
        ):
            for key, value in fit.items():
                self.assertEqual(installed[key], value, key)

    def test_both_head_limits_keep_complete_side_caps_on_each_carrier_slot(self):
        from gondola.parts import mounting_plate, slot_bearing

        plate = mounting_plate.shape()
        for centre in ((27, 5), (-27, -5), (27, 19), (-27, -19)):
            result = slot_bearing.check(
                plate, centre, 17, maximum_slot_width=2.9, minimum_screw_diameter=1.8
            )
            self.assertTrue(result["passed"], result)
            self.assertEqual(len(result["bearing_caps"]), 4)
            self.assertEqual(
                {row["head_offset_mm"] for row in result["bearing_caps"]},
                {-0.1, 0.1},
            )
            self.assertGreater(
                min(row["bearing_cap_area_mm2"] for row in result["bearing_caps"]),
                0.2,
            )

    def test_optical_audit_rejects_missing_cap_beyond_old_centre_strip(self):
        from gondola.parts import mounting_plate, optical_mount
        from gondola.validation.optical import _carrier_interface_checks

        doc = App.newDocument("OpticalHeadBearing")
        self.addCleanup(App.closeDocument, doc.Name)
        host = doc.addObject("App::Part", "BatteryEquipmentModule")
        plate = doc.addObject("Part::Feature", "BatteryMount")
        host.addObject(plate)
        plate.Shape = mounting_plate.shape()
        optical_mount.build_optical_mount(doc, host)
        self.assertTrue(_carrier_interface_checks(doc)["passed"])
        plate.Shape = plate.Shape.cut(
            Part.makeBox(0.08, 0.08, 0.1, App.Vector(28.48, 5.65, 17))
        )
        result = _carrier_interface_checks(doc)
        self.assertFalse(result["passed"])
        bearing = next(
            row
            for row in result["witnesses"]
            if row["kind"] == "centred_slot_head_bearing"
        )
        self.assertFalse(bearing["passed"])
        self.assertTrue(
            all(
                row["passed"]
                for row in result["witnesses"]
                if row["kind"] == "transverse_clamp_bearing_land"
            )
        )

    def test_power_audit_rejects_missing_circular_head_support(self):
        from gondola.parts import equipment_mounts, power_mount, stack_interface

        carrier = equipment_mounts.mount_shape("battery").copy()
        carrier.translate(App.Vector(0, 0, -stack_interface.STACK_TOP_Z))
        self.assertTrue(power_mount.attachment_check(carrier)["passed"])
        carrier = carrier.cut(
            Part.makeBox(0.08, 0.08, 0.1, App.Vector(28.48, 19.65, -34))
        )
        result = power_mount.attachment_check(carrier)
        self.assertFalse(result["passed"])
        self.assertFalse(result["feet"][1]["centred_slot_head_bearing"]["passed"])


if __name__ == "__main__":
    unittest.main()
