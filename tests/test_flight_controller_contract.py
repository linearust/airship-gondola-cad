"""Selected controller identity and unresolved input evidence stay linked."""

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

    def test_official_voltage_conflict_remains_visible_without_changing_battery(self):
        status = project_status()
        evidence = interfaces.flight_controller_contract()["electrical"]
        self.assertEqual(
            evidence["compatibility_status"], "unresolved_official_source_conflict"
        )
        self.assertEqual(evidence["input_claims"]["manual_text"]["cells"], [3, 6])
        self.assertEqual(evidence["input_claims"]["manual_text"]["voltage_v"], [10, 27])
        self.assertEqual(evidence["input_claims"]["port_diagram"]["cells"], [2, 6])
        self.assertEqual(
            evidence["input_claims"]["port_diagram"]["voltage_v"], [5.6, 27]
        )
        self.assertIn("fc_input_power", status["source_discrepancies"])
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
                self.assertEqual(pending["fc_input_power"]["status"], "unverified")
                self.assertFalse(report["production_released"])


if __name__ == "__main__":
    unittest.main()
