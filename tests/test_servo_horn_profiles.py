"""The all-in-one print must support actual differing hole and hardware patterns."""

import unittest

from gondola.contracts import servo_horns

try:
    import FreeCAD as App
except ImportError:
    App = None


class HornProfileContractsTests(unittest.TestCase):
    def test_stock_kst_pilot_holes_are_not_claimed_as_threaded(self):
        kst = servo_horns.profile("KST_0415_13")
        self.assertFalse(kst.threaded)
        self.assertEqual(kst.attachment_radii_mm, (4.5, 13.2))
        self.assertEqual(sorted(set(d for _, d in kst.holes)), [0.8, 1.0])
        self.assertEqual(kst.screw_sku, "M1_4X6_PAN_HEAD_KIT")
        self.assertEqual(servo_horns.PREPARED_HOLE_DIAMETER_MM, 1.5)

    def test_mixed_default_does_not_require_two_scarce_original_horns(self):
        self.assertEqual(servo_horns.profile(side="Port").key, "PTK_6_6")
        self.assertEqual(servo_horns.profile(side="Starboard").key, "METAL_6_98")
        for side in ("Port", "Starboard"):
            self.assertEqual(
                servo_horns.profile(side=side).screw_sku, "M1_6X5_PAN_HEAD_KIT"
            )


@unittest.skipIf(App is None, "Requires FreeCAD")
class HornProfileGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.validation.horn_coupling import profile_compatibility_checks

        cls.selection = dict(servo_horns.SELECTED_BY_SIDE)
        cls.rows = profile_compatibility_checks()

    def test_all_three_profiles_pass_same_print_on_both_sides(self):
        self.assertEqual({r["profile"] for r in self.rows}, set(servo_horns.PROFILES))
        for row in self.rows:
            with self.subTest(profile=row["profile"]):
                self.assertTrue(row["passed"], row)
                self.assertEqual(len(row["registration"]), 2)
                self.assertFalse(row["servo_sweep_overlaps"])
        self.assertEqual(servo_horns.SELECTED_BY_SIDE, self.selection)

    def test_kst_uses_complete_off_bridge_service_sequence(self):
        row = next(r for r in self.rows if r["profile"] == "KST_0415_13")
        self.assertEqual(len(row["conditional_service"]), 2)
        for service in row["conditional_service"]:
            self.assertTrue(service["passed"], service)
            self.assertEqual(len(service["ear_fastener_release"]), 2)
            self.assertEqual(len(service["rear_holding_tool_off_bridge"]), 2)
            self.assertEqual(len(service["adapter_clamp_release"]["fasteners"]), 2)
            self.assertTrue(service["adapter_release_off_bridge"]["passed"])

    def test_kst_front_nuts_cannot_be_removed_from_the_saved_profile(self):
        from gondola.parts import propulsion
        from gondola.validation.horn_coupling import horn_registration_check

        original = dict(servo_horns.SELECTED_BY_SIDE)
        doc = App.newDocument("MissingKSTNutRegression")
        try:
            servo_horns.SELECTED_BY_SIDE["Port"] = "KST_0415_13"
            propulsion.build_propulsion_module(doc)
            doc.recompute()
            doc.removeObject("PortHornGearClampNearNut")
            result = horn_registration_check(doc, "Port")
            self.assertFalse(result["passed"])
            self.assertIn("PortHornGearClampNearNut", result["missing_objects"])
        finally:
            App.closeDocument(doc.Name)
            servo_horns.SELECTED_BY_SIDE.clear()
            servo_horns.SELECTED_BY_SIDE.update(original)


if __name__ == "__main__":
    unittest.main()
