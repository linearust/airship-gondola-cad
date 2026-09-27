"""Optional power supplies preserve real channel and voltage constraints."""

import json
import unittest
from dataclasses import FrozenInstanceError

from gondola.contracts.power_options import (
    DEFAULT_OPTIONAL_POWER_PLAN_KEY,
    OPTIONAL_POWER_PLAN_KEYS,
    POWER_MODULE_PROFILES,
    POWER_PLANS,
    PowerPlan,
    RegulatorBranch,
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

    def test_tether_cascades_one_bec_into_one_svpdb(self):
        plan = get_power_plan(DEFAULT_OPTIONAL_POWER_PLAN_KEY)
        contract = plan.contract()
        self.assertEqual(plan.key, "TETHER_BEC_SVPDB")
        self.assertEqual(plan.nominal_input_voltage_v, 24)
        self.assertEqual(
            contract["regulator_quantities"], {"BEC12S_PRO": 1, "SVPDB_8S": 1}
        )
        self.assertEqual(contract["listed_regulator_mass_g"], 9)
        self.assertEqual([branch.output_voltage_v for branch in plan.branches], [8, 5])
        self.assertEqual(
            [row["input_voltage_v"] for row in contract["branches"]], [24, 8]
        )
        self.assertEqual(
            [row["input_from"] for row in contract["branches"]],
            ["source", "branch[0].output"],
        )
        self.assertEqual(
            [row["upstream_branch_index"] for row in contract["branches"]], [None, 0]
        )
        self.assertEqual(
            get_power_module_profile("BEC12S_PRO").contract()[
                "independent_output_channels"
            ],
            1,
        )

    def test_cascade_current_limits_are_shared_not_added(self):
        limits = get_power_plan("TETHER_BEC_SVPDB").contract()["current_limits"]
        self.assertEqual(limits[0]["downstream_branch_indices"], [1])
        self.assertEqual(limits[1]["downstream_branch_indices"], [])
        self.assertEqual(
            [limit["published_continuous_output_current_a"] for limit in limits], [5, 4]
        )
        self.assertEqual(
            [limit["nominal_voltage_times_published_current_w"] for limit in limits],
            [40, 20],
        )
        self.assertNotIn("TETHER_DUAL_BEC", OPTIONAL_POWER_PLAN_KEYS)
        self.assertEqual(
            set(OPTIONAL_POWER_PLAN_KEYS), {"TETHER_BEC_SVPDB", "BATTERY_SVPDB"}
        )
        with self.assertRaises(ValueError):
            get_power_plan("TETHER_DUAL_BEC")

    def test_invalid_cascade_and_unsupported_settings_rejected(self):
        # Self/forward references cannot silently turn the second supply into a
        # direct-source branch; out-of-range upstream settings fail at creation.
        for branches in (
            (RegulatorBranch("SVPDB_8S", 5, "servos", 0),),
            (RegulatorBranch("SVPDB_8S", 5, "servos", -1),),
            (
                RegulatorBranch("BEC12S_PRO", 5.2, "main"),
                RegulatorBranch("SVPDB_8S", 5, "servos", 0),
            ),
            (RegulatorBranch("SVPDB_8S", 5.2, "servos"),),
        ):
            with self.subTest(branches=branches), self.assertRaises(ValueError):
                PowerPlan("INVALID", "test", 24, branches)

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
            for index, branch in enumerate(plan.branches):
                with self.subTest(plan=plan.key, module=branch.module_key):
                    profile = get_power_module_profile(branch.module_key)
                    self.assertIn(branch.output_voltage_v, profile.output_choices_v)
                    lower, upper = profile.input_voltage_v
                    input_v = plan.branch_input_voltage_v(index)
                    self.assertLessEqual(lower, input_v)
                    self.assertLessEqual(input_v, upper)
                    self.assertLess(branch.output_voltage_v, input_v)

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
