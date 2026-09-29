"""Selected controller identity and scoped input confirmation stay linked."""

import json
import unittest

from gondola.contracts import equipment_interfaces as interfaces
from gondola.contracts.design import (
    SELECTED_EQUIPMENT,
    hardware_bom_scope,
    project_status,
    release_status,
)


class FlightControllerContractTests(unittest.TestCase):
    def test_selected_controller_replaces_previous_board_once(self):
        controllers = [item for item in SELECTED_EQUIPMENT if "743" in item.model]
        self.assertEqual(len(controllers), 1)
        controller = controllers[0]
        self.assertEqual(controller.model, interfaces.FC_MODEL)
        self.assertEqual(controller.quantity, 1)
        self.assertEqual(controller.listed_unit_mass_g, interfaces.FC_LISTED_MASS_G)
        self.assertIn("45A", controller.model)
        contract = interfaces.flight_controller_contract()
        self.assertEqual(contract["electrical"]["esc_firmware"], "AM32")
        self.assertEqual(tuple(contract["size_mm"]), (36.0, 36.0, 8.0))
        self.assertEqual(contract["hole_pitch_mm"], 25.5)
        self.assertEqual(contract["hole_diameter_mm"], 3.0)

    def test_confirmed_2s_support_preserves_history_without_changing_battery(self):
        status = project_status()
        evidence = interfaces.flight_controller_contract()["electrical"]
        self.assertEqual(evidence["compatibility_status"], "user_confirmed_2s")
        self.assertEqual(evidence["input_claims"]["manual_text"]["cells"], [3, 6])
        self.assertEqual(evidence["input_claims"]["manual_text"]["voltage_v"], [10, 27])
        self.assertEqual(evidence["input_claims"]["port_diagram"]["cells"], [2, 6])
        self.assertEqual(
            evidence["input_claims"]["port_diagram"]["voltage_v"], [5.6, 27]
        )
        confirmation = evidence["selected_input_confirmation"]
        self.assertTrue(confirmation["supports_2s"])
        self.assertEqual(confirmation["confirmed_on"], "2026-09-29")
        self.assertIsNone(confirmation["hardware_revision"])
        self.assertIsNone(confirmation["minimum_input_voltage_v"])
        discrepancy = status["source_discrepancies"]["fc_input_power"]
        self.assertEqual(discrepancy["compatibility_status"], "user_confirmed_2s")
        self.assertEqual(discrepancy["selected_input_confirmation"], confirmation)
        self.assertEqual(
            [
                item.model
                for item in SELECTED_EQUIPMENT
                if item.model.startswith("Tattu")
            ],
            ["Tattu 2S 450mAh 75C XT30 long pack"],
        )
        for output in (
            status,
            release_status(),
            hardware_bom_scope()["release_status"],
        ):
            with self.subTest(output_keys=sorted(output)):
                # JSON round-trip mirrors the public CLI and bundle boundaries.
                report = json.loads(json.dumps(output))
                pending = {
                    item["key"]: item for item in report["unresolved_interfaces"]
                }
                self.assertNotIn("fc_input_power", pending)
                self.assertEqual(pending["fc_installed_power"]["status"], "unverified")
                self.assertFalse(report["production_released"])


if __name__ == "__main__":
    unittest.main()
