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
    def test_unverified_horns_keep_null_mass_and_do_not_hide_inventory(self):
        horns = [
            part(
                name,
                volume,
                hardware_sku="SuppliedHorn",
                material="Supplied horn material unverified",
            )
            for name, volume in (("PortHorn", 120), ("StarboardHorn", 180))
        ]
        shaft = part(
            "Shaft",
            1000,
            hardware_sku="Rod",
            material="304 stainless steel (seller claim)",
        )
        report = mass_budget([part("Frame", 1000)], [shaft, *horns])
        horn_row = next(
            row for row in report["hardware"] if row["sku"] == "SuppliedHorn"
        )
        self.assertIsNone(horn_row["density_g_cm3"])
        self.assertIsNone(horn_row["estimated_mass_g"])
        self.assertEqual(horn_row["total_volume_mm3"], 300)
        self.assertEqual(report["hardware_part_count"], 3)
        self.assertFalse(report["modeled_hardware_mass_complete"])
        unknown = report["hardware_with_unmeasured_mass"]
        self.assertEqual(len(unknown), 1)
        self.assertEqual(unknown[0]["instances"], ["PortHorn", "StarboardHorn"])
        self.assertEqual(unknown[0]["quantity"], 2)
        self.assertEqual(unknown[0]["material"], "UnverifiedHorn")
        self.assertAlmostEqual(report["current_hardware_g"], 7.9)
        self.assertAlmostEqual(report["structure_hardware_g"], 8.91)
        self.assertAlmostEqual(
            report["accounted_subtotal_g"], 8.91 + SCOPED_LISTED_EQUIPMENT_MASS_G
        )
        self.assertIn("subtotals", report["totals_basis"])
        self.assertIsNone(
            report["density_assumptions"]["UnverifiedHorn"]["density_g_cm3"]
        )
        self.assertEqual(report["density_assumptions"]["SS304"]["density_g_cm3"], 7.9)
        self.assertEqual(json.loads(json.dumps(report, allow_nan=False)), report)

        # A zero known subtotal must not turn unknown parts into zero-mass parts.
        unknown_only = mass_budget([], horns)
        self.assertEqual(unknown_only["current_hardware_g"], 0)
        self.assertFalse(unknown_only["modeled_hardware_mass_complete"])
        self.assertIsNone(unknown_only["hardware"][0]["estimated_mass_g"])
        self.assertEqual(unknown_only["hardware_part_count"], 2)

    def test_sourced_mass_can_resolve_unknown_material_without_inventing_density(self):
        horn = part(
            "Horn",
            120,
            hardware_sku="SuppliedHorn",
            material="Supplied horn material unverified",
        )
        horn.ReferenceMassGrams = 0.3
        horn.ReferenceMassSource = "https://example.test/supplied-horn-datasheet"
        report = mass_budget([], [horn])
        self.assertAlmostEqual(report["current_hardware_g"], 0.3)
        self.assertIsNone(report["hardware"][0]["density_g_cm3"])
        self.assertEqual(
            report["hardware"][0]["mass_basis"], "Published reference mass"
        )
        self.assertTrue(report["modeled_hardware_mass_complete"])
        self.assertEqual(report["hardware_with_unmeasured_mass"], [])
        self.assertFalse(report["is_all_up_flight_mass"])
        horn.ReferenceMassSource = ""
        with self.assertRaisesRegex(ValueError, "Invalid reference mass"):
            mass_budget([], [horn])

    def test_unverified_material_does_not_bypass_solid_volume_validation(self):
        horn = part(
            "Horn",
            0,
            hardware_sku="SuppliedHorn",
            material="Supplied horn material unverified",
        )
        with self.assertRaisesRegex(ValueError, "solid volume"):
            mass_budget([], [horn])

    def test_complete_bearing_reference_mass_replaces_solid_envelope_estimate(self):
        bearings = [
            part(name, 100, hardware_sku="MR63ZZ", material="Bearing steel")
            for name in ("LeftBearing", "RightBearing")
        ]
        for obj in bearings:
            obj.ReferenceMassGrams = 0.27
            obj.ReferenceMassSource = "https://www.nskmicro.co.jp/products/bearing/bearing_size_pdf/single_row_mm.pdf"
        report = mass_budget([], bearings)
        self.assertAlmostEqual(report["current_hardware_g"], 0.54)
        self.assertIsNone(report["hardware"][0]["density_g_cm3"])
        self.assertEqual(report["hardware"][0]["reference_unit_mass_g"], 0.27)
        bearings[1].ReferenceMassGrams = 0.3
        with self.assertRaisesRegex(ValueError, "Conflicting reference masses"):
            mass_budget([], bearings)
        bearings[0].ReferenceMassSource = ""
        with self.assertRaisesRegex(ValueError, "Invalid reference mass"):
            mass_budget([], bearings)

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
        self.assertFalse(report["complete_device_mounting_hardware_included"])
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
