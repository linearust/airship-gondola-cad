"""Optional power supplies preserve real channel and voltage constraints."""

import json
import unittest
from dataclasses import FrozenInstanceError

from gondola.contracts.power_options import (
    POWER_MODULE_PROFILES,
    POWER_PLANS,
    get_power_module_profile,
    get_power_plan,
    power_option_contract,
)


class PowerOptionTests(unittest.TestCase):
    def test_battery_default_does_not_add_optional_boards_or_mass(self):
        plan = get_power_plan().contract()
        self.assertEqual(plan["key"], "BATTERY")
        self.assertEqual(plan["regulator_quantities"], {})
        self.assertEqual(plan["listed_regulator_mass_g"], 0)

    def test_exact_tether_rails_require_two_separately_set_modules(self):
        plan = get_power_plan("TETHER_DUAL_BEC")
        self.assertEqual(plan.nominal_input_voltage_v, 24)
        self.assertEqual(plan.contract()["regulator_quantities"], {"BEC12S_PRO": 2})
        self.assertEqual(plan.contract()["listed_regulator_mass_g"], 10)
        self.assertEqual(
            [branch.output_voltage_v for branch in plan.branches], [8, 5.2]
        )
        self.assertEqual(
            get_power_module_profile("BEC12S_PRO").contract()[
                "independent_output_channels"
            ],
            1,
        )

    def test_svpdb_does_not_claim_a_5v2_setting(self):
        profile = get_power_module_profile("SVPDB_8S")
        self.assertNotIn(5.2, profile.output_choices_v)
        for key in ("TETHER_BEC_SVPDB", "BATTERY_SVPDB"):
            branches = [
                branch
                for branch in get_power_plan(key).branches
                if branch.module_key == "SVPDB_8S"
            ]
            self.assertEqual([branch.output_voltage_v for branch in branches], [5])

    def test_optional_plans_use_supported_nominal_inputs_and_selections(self):
        for plan in POWER_PLANS.values():
            for branch in plan.branches:
                with self.subTest(plan=plan.key, module=branch.module_key):
                    profile = get_power_module_profile(branch.module_key)
                    self.assertIn(branch.output_voltage_v, profile.output_choices_v)
                    lower, upper = profile.input_voltage_v
                    self.assertLessEqual(lower, plan.nominal_input_voltage_v)
                    self.assertLessEqual(plan.nominal_input_voltage_v, upper)
                    self.assertLess(
                        branch.output_voltage_v, plan.nominal_input_voltage_v
                    )

    def test_electrical_pads_are_not_invented_mechanical_holes(self):
        for profile in POWER_MODULE_PROFILES.values():
            contract = profile.contract()
            self.assertEqual(contract["mounting_hole_centres_mm"], ())
            self.assertIsNone(contract["mounting_hole_diameter_mm"])
            self.assertFalse(contract["installed_port_datums_verified"])
            self.assertFalse(contract["installed_load_and_thermal_verified"])
            self.assertFalse(contract["retention_verified"])

    def test_profiles_immutable_contract_detached_and_json_safe(self):
        module = get_power_module_profile("BEC12S_PRO")
        with self.assertRaises(FrozenInstanceError):
            module.mass_g = 0
        contract = power_option_contract()
        contract["modules"]["BEC12S_PRO"]["size_mm"] = (1, 1, 1)
        self.assertEqual(module.size_mm, (35, 24, 5.5))
        json.dumps(power_option_contract(), allow_nan=False)

    def test_unknown_profiles_and_non_scalar_selectors_rejected(self):
        for getter in (get_power_plan, get_power_module_profile):
            for key in ("both", "BEC12S", "", []):
                with self.subTest(getter=getter.__name__, key=key):
                    with self.assertRaises(ValueError):
                        getter(key)


if __name__ == "__main__":
    unittest.main()
