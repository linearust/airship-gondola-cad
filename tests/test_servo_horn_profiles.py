"""The supplied OEM half arm must fit and remain serviceable on both sides."""

import unittest

from gondola.contracts import servo_horns

try:
    import FreeCAD as App
except ImportError:
    App = None


class HornProfileContractsTests(unittest.TestCase):
    def test_stock_kst_pilot_holes_are_not_claimed_as_threaded(self):
        kst = servo_horns.profile("KST_X06_HALF_ARM_1")
        self.assertFalse(kst.threaded)
        self.assertEqual(kst.attachment_radii_mm, (6.8, 13.2))
        self.assertEqual(kst.holes, ((4.5, 0.8), (6.8, 1.0), (10.0, 1.0), (13.2, 1.0)))
        self.assertEqual(kst.screw_sku, "M1_4X8_PAN_HEAD_KIT")
        self.assertEqual(kst.screw_length_mm, 8.0)
        self.assertEqual(kst.blade_bottom_mm, 1.5)
        self.assertEqual(kst.arm_thickness_mm, 2.0)
        self.assertEqual(servo_horns.PREPARED_HOLE_DIAMETER_MM, 1.5)

    def test_both_sides_use_the_supplied_half_arm_and_rear_bolt_front_nut_stack(self):
        self.assertEqual(set(servo_horns.PROFILES), {"KST_X06_HALF_ARM_1"})
        for side in ("Port", "Starboard"):
            selected = servo_horns.profile(side=side)
            self.assertEqual(selected.key, "KST_X06_HALF_ARM_1")
            self.assertEqual(selected.sku, "KST_X06_STOCK_HALF_ARM_1")
        self.assertEqual(servo_horns.KST_SCREW_HEAD_DIAMETER_MM, 2.6)
        self.assertEqual(servo_horns.KST_SCREW_HEAD_HEIGHT_MM, 1.0)
        self.assertEqual(servo_horns.NUT_AF_MM, 3.0)
        self.assertEqual(servo_horns.NUT_MIN_AF_MM, 2.9)
        self.assertEqual(servo_horns.NUT_HEIGHT_MM, 1.2)


@unittest.skipIf(App is None, "Requires FreeCAD")
class HornProfileGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.validation.horn_coupling import profile_compatibility_checks

        cls.selection = dict(servo_horns.SELECTED_BY_SIDE)
        cls.rows = profile_compatibility_checks()

    def test_oem_half_arm_passes_same_print_on_both_mirrored_sides(self):
        self.assertEqual(len(self.rows), 1)
        self.assertEqual({r["profile"] for r in self.rows}, set(servo_horns.PROFILES))
        for row in self.rows:
            with self.subTest(profile=row["profile"]):
                self.assertTrue(row["passed"], row)
                self.assertEqual(len(row["registration"]), 2)
                self.assertTrue(all(r["passed"] for r in row["registration"]))
                self.assertTrue(all(r["passed"] for r in row["functional_webs"]))
                self.assertEqual(row["servo_sweep_angles_deg"], list(range(-60, 61, 5)))
                self.assertFalse(row["servo_sweep_overlaps"])
        self.assertEqual(servo_horns.SELECTED_BY_SIDE, self.selection)

    def test_kst_uses_complete_off_bridge_service_sequence(self):
        row = next(r for r in self.rows if r["profile"] == "KST_X06_HALF_ARM_1")
        self.assertEqual(len(row["conditional_service"]), 2)
        for service in row["conditional_service"]:
            self.assertTrue(service["passed"], service)
            self.assertEqual(service["service_mode"], "preassembled_servo_unit")
            self.assertTrue(service["module_removal_passed"])
            self.assertTrue(service["driver_gear_removal"]["passed"])
            self.assertTrue(service["input_stub_removal"]["passed"])
            ear_releases = service["ear_fastener_release"]
            prefix = service["pod"]
            self.assertEqual(
                [release["bolt"] for release in ear_releases],
                [prefix + "ServoEar" + side + "Bolt" for side in ("Lower", "Upper")],
            )
            removed_ears = {
                prefix + "ServoEar" + side + kind
                for side in ("Lower", "Upper")
                for kind in ("Bolt", "Nut")
            }
            self.assertTrue(removed_ears.issubset(service["bench_members"]))
            self.assertTrue(removed_ears.isdisjoint(service["moving_parts"]))
            self.assertTrue(removed_ears.isdisjoint(service["retained_parts"]))
            for release in ear_releases:
                self.assertTrue(release["passed"], release)
                self.assertTrue(release["screw_first_with_nut_held_in_guides"])
                self.assertFalse(release["bolt_retained_in_servo_unit"])
                self.assertTrue(release["bolt_axial_withdrawal"]["passed"])
                self.assertTrue(release["nut_axial_removal"]["passed"])
                self.assertAlmostEqual(release["bolt_withdrawal_travel_mm"], 8.2)
                self.assertAlmostEqual(
                    release["minimum_nut_lift_before_lateral_mm"], 0.7
                )
            # Both upper fasteners remain obstacles during lower-pair removal;
            # only after that checked release may the upper pair be removed.
            for kind in ("Bolt", "Nut"):
                self.assertIn(
                    prefix + "ServoEarUpper" + kind,
                    ear_releases[0]["bolt_axial_withdrawal"]["obstacles"],
                )
                self.assertNotIn(
                    prefix + "ServoEarLower" + kind,
                    ear_releases[1]["bolt_axial_withdrawal"]["obstacles"],
                )
            self.assertEqual(len(service["rear_holding_tool_off_bridge"]), 2)
            releases = service["adapter_clamp_release"]["fasteners"]
            self.assertEqual([r["joint"] for r in releases], ["Far", "Near"])
            for release in releases:
                self.assertTrue(release["front_nut_release"]["passed"])
                self.assertFalse(release["fine_plier_jaw_collisions_mm3"])
                self.assertIn(release["bolt"], release["retained_parts"])
                for suffix in (
                    "Servo",
                    "InputShaftClampBolt",
                    "InputShaftClampNut",
                ):
                    self.assertIn(service["pod"] + suffix, release["retained_parts"])
                self.assertTrue(removed_ears.isdisjoint(release["retained_parts"]))
            self.assertIn(releases[0]["nut"], releases[1]["removed_prior_parts"])
            adapter = service["adapter_release_off_bridge"]
            self.assertTrue(adapter["passed"])
            self.assertIn(service["pod"] + "Servo", adapter["obstacles"])
            self.assertTrue(removed_ears.isdisjoint(adapter["obstacles"]))
            self.assertEqual(len(adapter["retained_clamp_hardware_paths"]), 2)
            self.assertTrue(
                all(row["passed"] for row in adapter["retained_clamp_hardware_paths"])
            )

    def test_kst_front_nuts_cannot_be_removed_from_the_saved_profile(self):
        from gondola.parts import propulsion
        from gondola.validation.horn_coupling import horn_registration_check

        doc = App.newDocument("MissingKSTNutRegression")
        try:
            propulsion.build_propulsion_module(doc)
            doc.recompute()
            doc.removeObject("PortHornGearClampNearNut")
            result = horn_registration_check(doc, "Port")
            self.assertFalse(result["passed"])
            self.assertIn("PortHornGearClampNearNut", result["missing_objects"])
        finally:
            App.closeDocument(doc.Name)


if __name__ == "__main__":
    unittest.main()
