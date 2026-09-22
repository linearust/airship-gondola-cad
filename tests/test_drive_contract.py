"""Portable safeguards for the finite purchased-gear substitution contract."""

import json
import math
import unittest
from types import SimpleNamespace

from gondola.contracts.drive import (
    DRIVE_CONFIGURATIONS,
    SELECTED_DRIVE,
    drive_for_document,
)


class DriveContractTests(unittest.TestCase):
    def test_catalog_alternative_replaces_drivers_and_bridge_on_a_common_frame(self):
        baseline = DRIVE_CONFIGURATIONS["60_20"]
        alternative = DRIVE_CONFIGURATIONS["64_20"]
        self.assertEqual(baseline.center_distance_mm, 20)
        self.assertEqual(alternative.center_distance_mm, 21)
        self.assertEqual(alternative.driver.sku, "GEABP0.5-64-3-B-7")
        self.assertEqual(
            baseline.driver.hub_diameter_mm, alternative.driver.hub_diameter_mm
        )
        self.assertAlmostEqual(alternative.input_x_mm / baseline.input_x_mm, 21 / 20)
        self.assertAlmostEqual(
            math.hypot(
                alternative.input_x_mm - baseline.input_x_mm,
                alternative.input_z_mm - baseline.input_z_mm,
            ),
            1,
        )
        self.assertNotIn("mesh_clearance_max_mm", baseline.contract())
        for configuration in (baseline, alternative):
            self.assertEqual(configuration.frame_sku, "PropulsionFixedFrame")
            self.assertEqual(
                configuration.contract()["fixed_frame_print_sku"],
                "PropulsionFixedFrame",
            )
            expected = f"ServoDriveBridge{configuration.driver.teeth}T"
            self.assertEqual(configuration.bridge_sku, expected)
            self.assertEqual(
                configuration.contract()["servo_bridge_print_sku"], expected
            )
            self.assertNotIn("servo_holder_print_sku", configuration.contract())
        self.assertEqual(baseline.contract()["servo_endpoint_for_180_deg"], 60)
        self.assertEqual(alternative.contract()["servo_endpoint_for_180_deg"], 56.25)

    def test_saved_key_alone_cannot_silently_change_ratio(self):
        module = SimpleNamespace(
            GearConfiguration=SELECTED_DRIVE.key,
            DriveContract=json.dumps(SELECTED_DRIVE.contract()),
        )
        doc = SimpleNamespace(getObject=lambda name: module)
        self.assertEqual(drive_for_document(doc), SELECTED_DRIVE)
        module.GearConfiguration = "64_20" if SELECTED_DRIVE.key == "60_20" else "60_20"
        with self.assertRaisesRegex(ValueError, "differs"):
            drive_for_document(doc)
        module.GearConfiguration = "61_20"
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            drive_for_document(doc)

    def test_missing_or_damaged_native_contract_is_rejected(self):
        for module in (
            None,
            SimpleNamespace(GearConfiguration="60_20"),
            SimpleNamespace(GearConfiguration="60_20", DriveContract="{"),
        ):
            with self.subTest(module=module), self.assertRaises(ValueError):
                drive_for_document(SimpleNamespace(getObject=lambda name: module))


if __name__ == "__main__":
    unittest.main()
