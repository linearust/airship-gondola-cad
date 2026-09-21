"""Mass accounting must preserve installed quantities and explicit exclusions."""

import json
import types
import unittest

from gondola.contracts.design import SCOPED_LISTED_EQUIPMENT_MASS_G
from gondola.mass_budget import mass_budget


def part(name, volume_mm3, *, print_sku=None, hardware_sku=None, material=None):
    obj = types.SimpleNamespace(
        Name=name, Shape=types.SimpleNamespace(Volume=volume_mm3)
    )
    if print_sku is not None:
        obj.PrintSKU = print_sku
    if hardware_sku is not None:
        obj.HardwareSKU = hardware_sku
    if material is not None:
        obj.MaterialSelection = material
    return obj


class MassBudgetTests(unittest.TestCase):
    def test_counts_actual_instance_volumes_and_groups_by_sku_and_material(self):
        printed = [
            part("Board1", 1000, print_sku="Board"),
            part("Board2", 1500, print_sku="Board"),
        ]
        hardware = [
            part("Nut1", 100, hardware_sku="Nut", material="A2 stainless steel"),
            part("Nut2", 200, hardware_sku="Nut", material="A2 stainless steel"),
            part("Nut3", 100, hardware_sku="Nut", material="Nylon PA66"),
        ]
        report = mass_budget(printed, hardware)
        self.assertEqual(report["printed_part_count"], 2)
        self.assertEqual(report["hardware_part_count"], 3)
        self.assertEqual(report["printed"][0]["quantity"], 2)
        self.assertEqual(report["printed"][0]["total_volume_mm3"], 2500)
        self.assertEqual(len(report["hardware"]), 2)
        self.assertEqual(report["hardware"][0]["instances"], ["Nut1", "Nut2"])
        self.assertEqual(report["hardware"][0]["instance_volumes_mm3"], [100, 200])
        self.assertAlmostEqual(report["current_printed_g"], 2.525)
        self.assertAlmostEqual(report["current_hardware_g"], 2.484)
        self.assertAlmostEqual(report["structure_hardware_g"], 5.009)
        self.assertAlmostEqual(
            report["accounted_subtotal_g"], 5.009 + SCOPED_LISTED_EQUIPMENT_MASS_G
        )
        self.assertEqual(json.loads(json.dumps(report)), report)

    def test_only_supplied_installed_parts_are_counted_and_coupon_is_rejected(self):
        installed = part("InstalledRail", 1000, print_sku="Rail")
        coupon = part("CouponRail", 5000, print_sku="Rail")
        coupon.PrintCategory = "Fit samples"
        report = mass_budget([installed], [])
        self.assertEqual(report["printed_part_count"], 1)
        self.assertEqual(report["printed"][0]["instances"], ["InstalledRail"])
        self.assertAlmostEqual(report["current_printed_g"], 1.01)
        self.assertFalse(report["is_all_up_flight_mass"])
        self.assertTrue(any("Fit coupons" in item for item in report["excluded_items"]))
        with self.assertRaisesRegex(ValueError, "not coupon"):
            mass_budget([installed, coupon], [])

    def test_rejects_unknown_or_ambiguous_materials(self):
        for material in (None, "Nylon", "Aluminium", "A2 or PA66"):
            with self.subTest(material=material):
                obj = part("Bolt", 10, hardware_sku="Bolt", material=material)
                with self.assertRaisesRegex(ValueError, "hardware material"):
                    mass_budget([], [obj])
        with self.assertRaisesRegex(ValueError, "printed material"):
            mass_budget([part("Print", 10, material="PLA")], [])

    def test_rejects_duplicate_instances_and_invalid_volumes(self):
        obj = part("Board", 1000)
        with self.assertRaisesRegex(ValueError, "more than once"):
            mass_budget([obj, obj], [])
        for volume in (0, -1, float("nan"), float("inf")):
            with self.subTest(volume=volume):
                with self.assertRaisesRegex(ValueError, "solid volume"):
                    mass_budget([part("Board", volume)], [])

    def test_current_mass_scope_does_not_embed_a_historical_design(self):
        report = mass_budget([part("Rail", 1000)], [])
        self.assertFalse(report["device_mounting_hardware_included"])
        self.assertIn("not yet dimensioned or counted", report["comparison_limit"])
        self.assertAlmostEqual(report["current_printed_g"], 1.01)
        self.assertEqual(report["current_hardware_g"], 0)
        self.assertAlmostEqual(
            report["accounted_subtotal_g"], 1.01 + SCOPED_LISTED_EQUIPMENT_MASS_G
        )
        self.assertFalse(any(key.startswith("comparison_to_") for key in report))
        self.assertIn("assumption", report["density_assumptions"]["A2"]["basis"])
        self.assertIn("assumption", report["density_assumptions"]["PA66"]["basis"])


if __name__ == "__main__":
    unittest.main()
