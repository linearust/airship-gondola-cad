"""Alternative equipment keeps physical, connector and mass scopes distinct."""

import json
import unittest
from dataclasses import FrozenInstanceError
from itertools import product

from gondola.contracts.design import (
    EXCLUDED_EQUIPMENT,
    SCOPED_LISTED_EQUIPMENT_MASS_G,
    equipment_selection,
    wiring_purchase_plan,
)
from gondola.contracts.equipment_interfaces import (
    DEVICE_CONNECTOR_EVIDENCE,
    MOUNTING_EVIDENCE,
)
from gondola.contracts.equipment_options import (
    NAVIGATION_PROFILES,
    RADIO_PROFILES,
    get_navigation_profile,
    get_radio_profile,
)
from gondola.contracts.optical_sensors import SENSOR_PROFILES


class EquipmentOptionTests(unittest.TestCase):
    def test_default_slots_preserve_pas_and_lr900a(self):
        self.assertEqual(get_navigation_profile().key, "PAS")
        self.assertEqual(get_radio_profile().key, "LR900A")
        self.assertEqual(set(NAVIGATION_PROFILES), {"PAS", "MGA01", "MGF10A"})
        self.assertEqual(set(RADIO_PROFILES), {"LR900A", "LR24FMINI"})

    def test_profiles_are_immutable_and_contracts_are_detached(self):
        for profile in (*NAVIGATION_PROFILES.values(), *RADIO_PROFILES.values()):
            with self.subTest(model=profile.key):
                with self.assertRaises(FrozenInstanceError):
                    profile.mass_g = 0
                contract = profile.contract()
                contract["size_mm"] = (1, 1, 1)
                self.assertNotEqual(profile.size_mm, contract["size_mm"])
                json.dumps(profile.contract(), allow_nan=False)
                self.assertFalse(contract["retention_verified"])
                self.assertFalse(contract["installed_port_datums_verified"])
                self.assertFalse(contract["rf_performance_verified"])

    def test_unknown_or_ground_models_cannot_be_selected_as_onboard(self):
        for getter, keys in (
            (get_navigation_profile, ("both", "MGF10C", "", [])),
            (get_radio_profile, ("both", "LR24F", "LR900F", "", [])),
        ):
            for key in keys:
                with self.subTest(key=key), self.assertRaises(ValueError):
                    getter(key)

    def test_helix_is_separate_from_module_mass_and_has_no_invented_pose(self):
        profile = get_navigation_profile("MGF10A")
        self.assertEqual(profile.mass_g, 6)
        self.assertEqual(profile.external_antenna.mass_g, 15)
        self.assertEqual(profile.external_antenna.diameter_mm, 28)
        self.assertEqual(profile.external_antenna.length_mm, 59.3)
        self.assertAlmostEqual(profile.mass_g + profile.external_antenna.mass_g, 21)
        antenna = profile.contract()["external_antenna"]
        antenna["mass_g"] = 0
        self.assertEqual(profile.external_antenna.mass_g, 15)
        self.assertFalse(any("centre" in key or "position" in key for key in antenna))
        self.assertEqual(
            profile.contract()["external_antenna_installations"],
            ["direct_sma", "remote_sma"],
        )

    def test_pas_hole_frame_is_not_inherited_by_adhesive_gps_choices(self):
        pas = get_navigation_profile()
        left, right = pas.mounting_hole_centres_mm
        self.assertEqual(right[0] - left[0], 23)
        self.assertEqual(left[1], -9.3)
        self.assertEqual(pas.mounting_hole_diameter_mm, 2.2)
        self.assertEqual(pas.connector_band_width_mm, 19)
        for key in ("MGA01", "MGF10A"):
            profile = get_navigation_profile(key)
            self.assertEqual(profile.mounting_hole_centres_mm, ())
            self.assertIsNone(profile.mounting_hole_diameter_mm)
            self.assertEqual(profile.connector_band_width_mm, profile.size_mm[0])
            self.assertEqual(profile.connector_type, "SH1.0-6P")

    def test_radio_alternatives_preserve_distinct_ports_and_power(self):
        lr900 = get_radio_profile("LR900A")
        mini = get_radio_profile("LR24FMINI")
        self.assertEqual(lr900.connector_catalog_key, "JST_GH_4P")
        self.assertEqual(mini.connector_catalog_key, "JST_SH_4P")
        self.assertTrue(lr900.has_usb)
        self.assertFalse(mini.has_usb)
        self.assertEqual(mini.antenna_connector, "IPEX1")
        self.assertEqual(mini.size_mm[2], 5.8)
        self.assertEqual(mini.supply_voltage_v, (4.5, 5.0))
        self.assertEqual(mini.uart_logic_v, 3.3)
        self.assertAlmostEqual(
            (mini.max_average_power_w - lr900.max_average_power_w) / 5, 0.34
        )

    def test_each_supported_combination_counts_devices_and_helix_once(self):
        self.assertEqual(SCOPED_LISTED_EQUIPMENT_MASS_G, 37.032)
        self.assertFalse(any("MG-A01" in item for item in EXCLUDED_EQUIPMENT))
        navigation_models = {profile.model for profile in NAVIGATION_PROFILES.values()}
        radio_models = {profile.model for profile in RADIO_PROFILES.values()}
        for navigation, radio, sensor in product(
            NAVIGATION_PROFILES.values(),
            RADIO_PROFILES.values(),
            SENSOR_PROFILES.values(),
        ):
            with self.subTest(
                navigation=navigation.key, radio=radio.key, sensor=sensor.key
            ):
                equipment = equipment_selection(navigation.key, radio.key, sensor.key)
                self.assertEqual(
                    [
                        (item.model, item.quantity)
                        for item in equipment
                        if item.model in navigation_models
                    ],
                    [(navigation.model, 1)],
                )
                self.assertEqual(
                    [
                        (item.model, item.quantity)
                        for item in equipment
                        if item.model in radio_models
                    ],
                    [(radio.model, 1)],
                )
                self.assertEqual(
                    sum(item.quantity for item in equipment if "MTF-" in item.model), 1
                )
                helix_rows = [
                    item
                    for item in equipment
                    if "helix" in item.model.lower() and item.model != navigation.model
                ]
                self.assertEqual(
                    len(helix_rows), int(navigation.external_antenna is not None)
                )
                if helix_rows:
                    self.assertEqual(helix_rows[0].listed_unit_mass_g, 15)
                    self.assertEqual(helix_rows[0].quantity, 1)
                self.assertEqual(
                    sum(item.listed_unit_mass_g is None for item in equipment), 1
                )

    def test_connector_purchase_counts_follow_selected_cable_ends(self):
        baseline = wiring_purchase_plan()
        self.assertEqual(
            baseline["connector_ends_before_subtracting_included_cables"],
            {"SH1.0-6P": 2, "SH1.0-4P": 2, "GH1.25-4P": 2},
        )
        gps_mini = wiring_purchase_plan("MGF10A", "LR24FMINI", "MTF01P")
        self.assertEqual(
            gps_mini["connector_ends_before_subtracting_included_cables"],
            {"SH1.0-6P": 3, "SH1.0-4P": 3},
        )
        self.assertEqual(len(gps_mini["uart_harnesses"]), 3)
        self.assertIn("I2C", gps_mini["uart_harnesses"][1]["signal_scope"])
        self.assertIn("LR24-F ground", gps_mini["ground_radio"])
        self.assertAlmostEqual(
            gps_mini["radio_power_reference"]["calculated_at_5v_a"], 0.40
        )
        baseline["uart_harnesses"][0]["quantity"] = 20
        self.assertEqual(wiring_purchase_plan()["uart_harnesses"][0]["quantity"], 1)

    def test_all_profiles_have_explicit_unverified_interface_evidence(self):
        for profile in (*NAVIGATION_PROFILES.values(), *RADIO_PROFILES.values()):
            with self.subTest(model=profile.key):
                connector = DEVICE_CONNECTOR_EVIDENCE[profile.interface_key]
                mounting = MOUNTING_EVIDENCE[profile.interface_key]
                self.assertIn(profile.connector_type, connector["documented_types"])
                self.assertIn(
                    profile.connector_catalog_key, connector["catalog_references"]
                )
                self.assertIsNone(connector["installed_port_centres_mm"])
                self.assertFalse(connector["installed_port_datums_verified"])
                self.assertTrue(mounting["unknown"])
                self.assertIn(profile.source, mounting["sources"])
