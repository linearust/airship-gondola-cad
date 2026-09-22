"""Portable safeguards for the user-selected, asymmetric purchased-gear pair."""

import json
import unittest
from types import SimpleNamespace

from gondola.contracts.drive import (
    DRIVE_CONFIGURATIONS,
    GEARS,
    SELECTED_DRIVE,
    drive_for_document,
)


class DriveContractTests(unittest.TestCase):
    def test_selected_pair_preserves_bores_and_per_gear_axial_dimensions(self):
        drive = SELECTED_DRIVE
        self.assertEqual(set(DRIVE_CONFIGURATIONS), {"48_16"})
        self.assertEqual(set(GEARS), {16, 48})
        self.assertEqual(drive.key, "48_16")
        self.assertEqual(drive.center_distance_mm, 16)
        self.assertEqual(drive.contract()["angle_ratio"], -3)
        self.assertEqual(drive.contract()["servo_endpoint_for_180_deg"], 60)
        self.assertEqual(drive.contract()["nominal_full_face_overlap_mm"], 3)
        self.assertEqual((drive.driver.bore_mm, drive.output.bore_mm), (3, 3))
        self.assertEqual(
            (drive.driver.face_width_mm, drive.output.face_width_mm), (3, 5)
        )
        self.assertEqual(
            (drive.driver.total_length_mm, drive.output.total_length_mm), (8, 10)
        )
        self.assertEqual(
            (drive.driver.hub_diameter_mm, drive.output.hub_diameter_mm), (12, 6.5)
        )
        self.assertEqual(drive.driver.hub_extension_mm, 5)
        self.assertEqual(drive.output.hub_extension_mm, 5)
        self.assertEqual(drive.frame_sku, "PropulsionFixedFrame")
        self.assertEqual(drive.bridge_sku, "ServoDriveBridge48T")

    def test_source_gaps_are_not_filled_from_the_other_gear(self):
        self.assertIsNone(SELECTED_DRIVE.driver.set_screw_axis_from_hub_end_mm)
        self.assertEqual(SELECTED_DRIVE.output.set_screw_axis_from_hub_end_mm, 2.5)
        self.assertIn("H8", SELECTED_DRIVE.driver.bore_tolerance)
        self.assertIn("Unspecified", SELECTED_DRIVE.output.bore_tolerance)
        for gear in GEARS.values():
            self.assertIsNone(gear.measured_mass_g)
            self.assertTrue(
                gear.item_url.startswith("https://www.aliexpress.com/item/")
            )
            self.assertNotIn("POM", gear.material_claim)

    def test_saved_metadata_cannot_reenable_a_removed_pair_or_change_dimensions(self):
        module = SimpleNamespace(
            GearConfiguration=SELECTED_DRIVE.key,
            DriveContract=json.dumps(SELECTED_DRIVE.contract()),
        )
        doc = SimpleNamespace(getObject=lambda name: module)
        self.assertEqual(drive_for_document(doc), SELECTED_DRIVE)
        for removed_key in ("60_20", "64_20", "61_20"):
            module.GearConfiguration = removed_key
            with (
                self.subTest(key=removed_key),
                self.assertRaisesRegex(ValueError, "Unsupported"),
            ):
                drive_for_document(doc)
        module.GearConfiguration = SELECTED_DRIVE.key
        damaged = SELECTED_DRIVE.contract()
        damaged["output"]["face_width_mm"] = 3
        module.DriveContract = json.dumps(damaged)
        with self.assertRaisesRegex(ValueError, "differs"):
            drive_for_document(doc)

    def test_missing_or_damaged_native_contract_is_rejected(self):
        for module in (
            None,
            SimpleNamespace(GearConfiguration="48_16"),
            SimpleNamespace(GearConfiguration="48_16", DriveContract="{"),
        ):
            with self.subTest(module=module), self.assertRaises(ValueError):
                drive_for_document(SimpleNamespace(getObject=lambda name: module))


if __name__ == "__main__":
    unittest.main()
